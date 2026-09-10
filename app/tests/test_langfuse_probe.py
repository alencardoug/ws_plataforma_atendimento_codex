"""LF-1 containment checks; no provider, Cloud or database traffic."""

import os
import subprocess
import sys

import httpx
import pytest

from customer_care.infrastructure.langfuse_probe import _persisted_proof, cloud_url
from customer_care.shared.settings import Settings


@pytest.mark.parametrize("flag,provider", [("false", "openai"), ("invalid-flag", "openai"), ("false", "deterministic-test"), ("true", "deterministic-test")])
def test_disabled_probe_and_deterministic_provider_need_no_sdk_network_or_threads(flag: str, provider: str) -> None:
    # A fresh interpreter catches eager SDK imports, even when another test
    # has already imported the provider or optional dependency.
    code = '''
import importlib.abc
import socket
import sys
import threading

class ForbidOptionalSDK(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname.split(".")[0] in {"langfuse", "opentelemetry"}:
            raise AssertionError("disabled path imported telemetry SDK")

def forbidden(*args, **kwargs):
    raise AssertionError("disabled path started network or a thread")

sys.meta_path.insert(0, ForbidOptionalSDK())
socket.socket.connect = forbidden
threading.Thread.start = forbidden
from customer_care.infrastructure.langfuse_probe import run_probe
from customer_care.shared.settings import get_settings
from customer_care.ai.providers import DeterministicTestGenerationProvider, create_langfuse_probe_client
from customer_care.knowledge.embeddings import DeterministicTestEmbeddingProvider

assert run_probe(get_settings()) == {"status": "disabled"}
try:
    create_langfuse_probe_client()
except RuntimeError as error:
    assert str(error) == "Langfuse probe disabled"
else:
    raise AssertionError("probe created a client")
result = DeterministicTestGenerationProvider().generate([{"role": "customer", "content": "Oi"}], [], "test")
assert result.status == "ANSWER"
assert result.draft_text == "Oi, tudo bem? Como posso ajudar?"
assert len(DeterministicTestEmbeddingProvider(dimension=8).embed(["synthetic"])[0]) == 8
assert not any(name.startswith(("langfuse", "opentelemetry")) for name in sys.modules)
'''
    environment = dict(os.environ, LANGFUSE_TRACING_ENABLED=flag, AI_PROVIDER=provider, LANGFUSE_PUBLIC_KEY="", LANGFUSE_SECRET_KEY="", LANGFUSE_BASE_URL="", LANGFUSE_HOST="")
    result = subprocess.run([sys.executable, "-c", code], env=environment, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("base,host", [("https://cloud.langfuse.com/", None), (None, "https://cloud.langfuse.com"), ("https://cloud.langfuse.com", "https://cloud.langfuse.com/")])
def test_region_can_use_either_environment_name(base: str | None, host: str | None) -> None:
    settings = Settings(langfuse_base_url=base, langfuse_host=host)
    assert cloud_url(settings) == "https://cloud.langfuse.com"


@pytest.mark.parametrize("base,host", [(None, None), ("https://cloud.langfuse.com", "https://us.cloud.langfuse.com"), ("https://credential-fragment@cloud.langfuse.com", None), ("http://localhost:3000", None)])
def test_invalid_region_is_rejected_without_echoing_configuration(base: str | None, host: str | None) -> None:
    settings = Settings(langfuse_base_url=base, langfuse_host=host)
    with pytest.raises(ValueError, match="Configure one explicit Langfuse Cloud region") as caught:
        cloud_url(settings)
    assert "credential-fragment" not in str(caught.value)


def test_ingestion_read_retries_timeout_without_repeating_a_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("customer_care.infrastructure.langfuse_probe.time.sleep", lambda _: None)
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            raise httpx.ReadTimeout("temporary read failure", request=request)
        if len(requests) == 2:
            return httpx.Response(404)
        return httpx.Response(200, json={
            "sessionId": "trace", "htmlPath": "/project/test/traces/trace", "totalCost": 0.00005825,
            "observations": [{"type": "GENERATION", "id": "generation", "model": "gpt-5-mini", "calculatedTotalCost": 0.00005825,
                              "usageDetails": {"input": 70, "input_cached_tokens": 30, "output": 5, "output_reasoning_tokens": 15, "total": 120}}],
            "scores": [{"id": "score", "name": "lf1.exact_answer", "value": 1}],
        })

    with httpx.Client(base_url="https://cloud.langfuse.com", transport=httpx.MockTransport(handle)) as api:
        result = _persisted_proof(api, "trace", "score", 0.00005825, {"input": 100, "output": 20})
    assert result["status"] == "persisted"
    assert len(requests) == 3
    assert all(request.method == "GET" and request.url.path == "/api/public/traces/trace" for request in requests)


def test_read_retry_keeps_the_total_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    elapsed = [0.0]
    monkeypatch.setattr("customer_care.infrastructure.langfuse_probe.time.monotonic", lambda: elapsed[0])
    monkeypatch.setattr("customer_care.infrastructure.langfuse_probe.time.sleep", lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds))

    def unavailable(request: httpx.Request) -> httpx.Response:
        elapsed[0] += 3.0
        raise httpx.ReadTimeout("temporary read failure", request=request)

    with httpx.Client(base_url="https://cloud.langfuse.com", transport=httpx.MockTransport(unavailable)) as api:
        with pytest.raises(TimeoutError, match="within 30 seconds"):
            _persisted_proof(api, "trace", "score", 0.1, {"input": 1, "output": 1})
    assert elapsed[0] <= 31.0
