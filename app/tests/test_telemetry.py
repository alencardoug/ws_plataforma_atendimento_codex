"""LF-2 contracts: no-op, exactly-once business work, context and bounded exit."""

import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from customer_care.infrastructure import telemetry


class RecordingClient:
    def __init__(self, failure=None):
        self.failure = failure
        self.spans = []
        self.scores = []

    def start_observation(self, **kwargs):
        if self.failure == "entry":
            raise RuntimeError("secret-in-entry-error")
        span = RecordingSpan(self, kwargs)
        self.spans.append(span)
        return span

    def create_score(self, **kwargs):
        if self.failure == "score":
            raise RuntimeError("secret-in-score-error")
        self.scores.append(kwargs)


class RecordingSpan:
    def __init__(self, client, values):
        self.client, self.values = client, values
        self.ended = False

    def start_observation(self, **kwargs):
        kwargs["parent"] = self.values["name"]
        kwargs["trace_context"] = self.values.get("trace_context")
        return self.client.start_observation(**kwargs)

    def update(self, **kwargs):
        if self.client.failure == "update":
            raise RuntimeError("secret-in-update-error")
        # Retain a serialized copy, like an exporter queue must do.
        self.values.update(json.loads(json.dumps(kwargs)))

    def end(self):
        self.ended = True
        if self.client.failure == "end":
            raise RuntimeError("secret-in-end-error")


@pytest.fixture
def recording(monkeypatch):
    client = RecordingClient()

    @contextmanager
    def propagate(**kwargs):
        if client.failure == "propagate_enter":
            raise RuntimeError("secret-in-propagation-error")
        yield
        if client.failure == "propagate_exit":
            raise RuntimeError("secret-in-propagation-error")

    monkeypatch.setitem(sys.modules, "langfuse", SimpleNamespace(propagate_attributes=propagate))
    monkeypatch.setattr(telemetry, "enabled", lambda: True)
    monkeypatch.setattr(telemetry, "_client", client)
    return client


@pytest.mark.parametrize("flag,provider", [("false", "openai"), ("bad-flag", "openai"), ("false", "deterministic-test"), ("true", "deterministic-test")])
def test_disabled_application_never_imports_sdk_or_starts_network_threads(flag, provider):
    code = '''
import importlib.abc, socket, sys, threading
class ForbidSDK(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname.split(".")[0] in {"langfuse", "opentelemetry"}:
            raise AssertionError("SDK imported while disabled")
def forbidden(*args, **kwargs):
    raise AssertionError("disabled telemetry executed a side effect")
sys.meta_path.insert(0, ForbidSDK())
socket.socket.connect = forbidden
threading.Thread.start = forbidden
from customer_care.bootstrap import create_app
from customer_care.infrastructure import telemetry
telemetry.initialize()
with telemetry.observe("n5.process_turn", forbidden, identity=forbidden) as span:
    span.update(forbidden)
telemetry.score("n5.sent", 1, key="id", timestamp="bad", data_type="BOOLEAN")
telemetry.shutdown()
assert create_app().title == "Customer Care AI V1 API"
assert telemetry.current().raw is None
assert not any(n.startswith(("langfuse", "opentelemetry")) for n in sys.modules)
'''
    env = dict(os.environ, LANGFUSE_TRACING_ENABLED=flag, AI_PROVIDER=provider, LANGFUSE_PUBLIC_KEY="", LANGFUSE_SECRET_KEY="")
    result = subprocess.run([sys.executable, "-c", code], env=env, text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("failure", [None, "entry", "propagate_enter", "propagate_exit", "update", "end", "score"])
@pytest.mark.parametrize("business_fails", [False, True])
def test_sdk_failure_preserves_exactly_one_call_and_original_exception(recording, failure, business_fails):
    recording.failure = failure
    calls = []
    original = ValueError("business-error-with-a-secret")

    def business():
        with telemetry.observe("ai.answer", lambda: {"input": "synthetic"}) as span:
            calls.append(1)
            span.update(lambda: {"output": "synthetic result"})
            telemetry.score("test", 1, key="id", timestamp="2026-09-10T00:00:00+00:00", data_type="BOOLEAN")
            if business_fails:
                raise original
            return "unchanged-result"

    if business_fails:
        with pytest.raises(ValueError) as caught:
            business()
        assert caught.value is original
    else:
        assert business() == "unchanged-result"
    assert calls == [1]
    assert telemetry.current().raw is None
    assert "secret" not in json.dumps([span.values for span in recording.spans])


def test_payload_construction_cannot_affect_business_or_serialize_objects(recording):
    class SecretObject:
        def __repr__(self):
            raise AssertionError("must never inspect arbitrary objects")

    with telemetry.observe("ai.answer", lambda: {"input": SecretObject()}) as span:
        span.update(lambda: {"output": SecretObject()})
    assert not recording.spans
    with telemetry.observe("ai.answer", lambda: {"input": ["synthetic"]}) as span:
        span.update(lambda: {"metadata": {"request": SecretObject()}})
        span.update(lambda: {"output": "allowed"})
    assert recording.spans[0].values["output"] == "allowed"
    assert "request" not in recording.spans[0].values["metadata"]


def test_parallel_turns_and_manual_calls_do_not_share_context(recording):
    barrier = threading.Barrier(2)
    ids = [uuid4().hex, uuid4().hex]

    def turn(trace_id):
        with telemetry.execution_origin("customer_poll"):
            with telemetry.observe("n5.process_turn", identity=lambda: {"trace_id": trace_id, "session_id": trace_id}):
                barrier.wait(timeout=5)
                with telemetry.observe("ai.answer"):
                    assert telemetry.current().trace_id == trace_id
                # Explicit identity detaches manual work from the turn.
                with telemetry.observe("rag.retrieve", identity=lambda: {"session_id": trace_id}):
                    assert telemetry.current().trace_id != trace_id
        assert telemetry.current().raw is None

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(turn, ids))
    for trace_id in ids:
        children = [s for s in recording.spans if s.values.get("trace_context") == {"trace_id": trace_id}]
        assert {s.values["name"] for s in children} == {"n5.process_turn", "ai.answer"}
    assert all(s.ended for s in recording.spans)


def test_scores_keep_original_identity_and_timestamp_on_replay(recording):
    for day in ("2026-09-10", "2026-09-11"):
        # Arrival order/day do not supply the event time.
        telemetry.score("n5.pending_outcome", "SENT", key="pending", timestamp="2026-09-10T01:02:03.123456+00:00", data_type="CATEGORICAL", trace_id="trace")
        telemetry.score("n5.pending_opened", 1, key="pending", timestamp="2026-09-10T01:02:00+00:00", data_type="BOOLEAN", trace_id="trace")
    assert recording.scores[:2] == recording.scores[2:]
    assert recording.scores[0]["score_id"] != recording.scores[1]["score_id"]
    assert recording.scores[0]["timestamp"].isoformat() == "2026-09-10T01:02:03.123456+00:00"


def test_shutdown_has_a_deadline_even_when_sdk_flush_never_returns(monkeypatch):
    release = threading.Event()
    finished = threading.Event()

    def shutdown():
        release.wait(timeout=5)
        finished.set()

    monkeypatch.setattr(telemetry, "_client", SimpleNamespace(shutdown=shutdown))
    monkeypatch.setattr(telemetry, "_tracer", None)
    monkeypatch.setattr(telemetry, "SHUTDOWN_TIMEOUT_SECONDS", 0.03)
    started = time.monotonic()
    try:
        telemetry.shutdown()
        assert time.monotonic() - started < 0.5
        assert telemetry._client is None
    finally:
        release.set()
        assert finished.wait(timeout=2)


def test_initialization_failure_is_noop_and_does_not_repeat_startup(monkeypatch):
    from pydantic import SecretStr

    calls = []

    def unavailable(**kwargs):
        calls.append(1)
        raise RuntimeError("must-not-log-initialization-secret")

    monkeypatch.setattr(telemetry, "_initialized", False)
    monkeypatch.setattr(telemetry, "_client", None)
    monkeypatch.setattr(telemetry, "_tracer", None)
    monkeypatch.setattr(telemetry, "_owners", 0)
    monkeypatch.setattr(telemetry, "get_settings", lambda: SimpleNamespace(
        ai_provider="openai", langfuse_tracing_enabled=True, langfuse_base_url="https://cloud.langfuse.com", langfuse_host="",
        langfuse_public_key=SecretStr("pk-synthetic"), langfuse_secret_key=SecretStr("sk-synthetic"), langfuse_tracing_environment="local-test"))
    monkeypatch.setitem(sys.modules, "langfuse", SimpleNamespace(Langfuse=unavailable))
    telemetry.initialize()
    telemetry.initialize()
    assert calls == [1] and telemetry._client is None
    with telemetry.observe("ai.answer") as span:
        assert span.raw is None
    telemetry.shutdown()


@pytest.mark.parametrize("failure", ["flush", "export"])
def test_export_or_flush_failure_cannot_undo_completed_business(recording, monkeypatch, failure):
    calls = []

    def unavailable():
        raise RuntimeError("must-not-log-exporter-secret")

    monkeypatch.setattr(telemetry, "_owners", 1)
    monkeypatch.setattr(telemetry, "_tracer", SimpleNamespace(shutdown=unavailable))
    recording.shutdown = unavailable
    if failure == "export":
        recording.failure = "end"
    with telemetry.observe("ai.answer"):
        calls.append("business-committed")
    telemetry.shutdown()
    assert calls == ["business-committed"] and telemetry._client is None


@pytest.mark.parametrize("operation", ["generate", "rerank_clinical", "extract_date_intent", "generate_ungoverned"])
def test_provider_captures_actual_request_usage_and_parsed_output_without_reasoning(recording, operation):
    from datetime import date

    from customer_care.ai.providers import OpenAIGenerationProvider

    payloads = {"generate": '{"status":"ANSWER","draft_text":"Resposta.","used_hit_ids":[]}',
                "rerank_clinical": '{"chosen":"B"}', "extract_date_intent": '{"weekday":2}', "generate_ungoverned": "Texto livre."}
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(model="gpt-5-mini", usage=SimpleNamespace(
            prompt_tokens=100, completion_tokens=30,
            prompt_tokens_details=SimpleNamespace(cached_tokens=20),
            completion_tokens_details=SimpleNamespace(reasoning_tokens=10)),
            choices=[SimpleNamespace(message=SimpleNamespace(content=payloads[operation], reasoning_content="forbidden-reasoning"))],
            raw_headers={"authorization": "forbidden-token"})

    provider = object.__new__(OpenAIGenerationProvider)
    provider.model = "gpt-5-mini"
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    history = [{"role": "customer", "content": "Pergunta sintética"}]
    args = {"generate": (history, [], "prompt"), "rerank_clinical": ("pergunta", "resposta"),
            "extract_date_intent": ("quarta", date(2026, 9, 10)), "generate_ungoverned": (history, "prompt")}
    getattr(provider, operation)(*args[operation])
    assert len(calls) == len(recording.spans) == 1
    observed = recording.spans[0].values
    assert observed["input"] == calls[0]["messages"]
    assert observed["output"] == payloads[operation]
    assert observed["usage_details"] == {"input": 80, "input_cached_tokens": 20, "output": 20, "output_reasoning_tokens": 10}
    assert "parsed_result" in observed["metadata"]
    assert "forbidden" not in json.dumps(observed)
    assert "cost_details" not in observed
    if operation == "generate_ungoverned":
        assert observed["input"] == [{"role": "system", "content": "prompt"}, {"role": "user", "content": "Pergunta sintética"}]
        assert observed["model_parameters"] == {}


def test_embeddings_capture_only_one_billable_operation_and_keep_order(recording):
    from customer_care.knowledge.embeddings import OpenAIEmbeddingProvider

    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(model="text-embedding-3-small", usage=SimpleNamespace(prompt_tokens=7),
                               data=[SimpleNamespace(index=1, embedding=[3.0, 4.0]), SimpleNamespace(index=0, embedding=[1.0, 2.0])])

    provider = object.__new__(OpenAIEmbeddingProvider)
    provider.model, provider.dimension = "text-embedding-3-small", 2
    provider.client = SimpleNamespace(embeddings=SimpleNamespace(create=create))
    assert provider.embed(["primeiro", "segundo"]) == [[1.0, 2.0], [3.0, 4.0]]
    assert len(calls) == len(recording.spans) == 1
    observed = recording.spans[0].values
    assert observed["input"] == calls[0]["input"]
    assert observed["as_type"] == "embedding"
    assert observed["usage_details"] == {"input": 7}
    assert observed["output"] == {"vector_count": 2, "dimensions": [2, 2]}


@pytest.mark.parametrize("export_failure", [False, True])
def test_native_sdk_exports_nested_safe_spans_without_patching_openai_or_network(export_failure):
    code = '''
import atexit, json, os, socket, sys
from openai.resources.chat.completions import Completions
from openai.resources.embeddings import Embeddings
chat_create, embed_create = Completions.create, Embeddings.create
import langfuse
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry import trace
from customer_care.infrastructure import telemetry

class Exporter(InMemorySpanExporter):
    def export(self, spans):
        result = super().export(spans)
        if os.environ["TEST_LF_EXPORT_FAILURE"] == "true":
            raise RuntimeError("must-not-log-async-export-secret")
        return result
exporter = Exporter()
native = langfuse.Langfuse
langfuse.Langfuse = lambda **kw: native(**kw, span_exporter=exporter)
removed = []
unregister = atexit.unregister
def remove(callback):
    removed.append(callback)
    unregister(callback)
atexit.unregister = remove
def forbid(*args, **kwargs):
    raise AssertionError("telemetry performed unexpected network")
socket.socket.connect = forbid
telemetry.initialize()
assert telemetry._client is not None
client = telemetry._client
telemetry.initialize()
telemetry.shutdown()
assert telemetry._client is client  # nested lifespans do not shut down the owner
assert client._resources.shutdown in removed
assert Completions.create is chat_create and Embeddings.create is embed_create
assert "langfuse.openai" not in sys.modules
assert isinstance(trace.get_tracer_provider(), trace.ProxyTracerProvider)
with telemetry.observe("n5.process_turn", identity=lambda: {"trace_id": "a" * 32, "session_id": "synthetic-session"}):
    try:
        with telemetry.observe("ai.answer", lambda: {"input": [{"role": "user", "content": "synthetic"}], "model": "gpt-5-mini"}, kind="generation") as span:
            span.update(lambda: {"output": "answer", "usage_details": {"input": 3, "output": 1}})
            raise ValueError("do-not-export-this-secret")
    except ValueError:
        pass
telemetry.shutdown()
spans = exporter.get_finished_spans()
assert len(spans) == 2, len(spans)
child, parent = spans
assert child.parent.span_id == parent.context.span_id
assert child.context.trace_id == parent.context.trace_id == int("a" * 32, 16)
assert all(s.attributes["session.id"] == "synthetic-session" for s in spans)
assert child.attributes["langfuse.observation.status_message"] == "ValueError"
assert not any(s.events for s in spans)
assert "do-not-export-this-secret" not in json.dumps([dict(s.attributes) for s in spans])
assert child.attributes["langfuse.observation.usage_details"] == '{"input": 3, "output": 1}'
print("native_sdk_containment_ok")
'''
    env = dict(os.environ, AI_PROVIDER="openai", LANGFUSE_TRACING_ENABLED="true", LANGFUSE_PUBLIC_KEY="pk-lf-synthetic-test",
               LANGFUSE_SECRET_KEY="sk-lf-synthetic-test", LANGFUSE_BASE_URL="https://cloud.langfuse.com", LANGFUSE_HOST="",
               TEST_LF_EXPORT_FAILURE=str(export_failure).lower())
    result = subprocess.run([sys.executable, "-c", code], env=env, text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "native_sdk_containment_ok" in result.stdout
    assert "must-not-log-async-export-secret" not in result.stderr
