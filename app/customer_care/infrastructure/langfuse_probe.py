"""LF-1 only: one synthetic completion and score, without database access.

Run in a fresh process, under a hard deadline (SDK flush has no timeout):
    timeout --kill-after=5s 90s python -m customer_care.infrastructure.langfuse_probe
Never import/call this diagnostic from application startup or request handlers.
"""

import json
import logging
import math
import time
from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from customer_care.shared.settings import Settings, get_settings

PROBE_NAME = "lf1.sdk_probe"
SCORE_NAME = "lf1.exact_answer"
CLOUD_URLS = {"https://cloud.langfuse.com", "https://us.cloud.langfuse.com", "https://jp.cloud.langfuse.com"}


def cloud_url(settings: Settings) -> str:
    urls = {value.strip().rstrip("/") for value in (settings.langfuse_base_url, settings.langfuse_host) if value and value.strip()}
    if len(urls) != 1 or not urls.issubset(CLOUD_URLS):
        raise ValueError("Configure one explicit Langfuse Cloud region; BASE_URL and HOST must agree")
    return urls.pop()


def _persisted_proof(api: Any, trace_id: str, score_id: str, expected_cost: float, expected_usage: dict[str, int]) -> dict[str, Any]:
    """Read back persisted data; flush alone does not prove ingestion."""
    import httpx

    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        try:
            response = api.get(f"/api/public/traces/{trace_id}", timeout=min(3.0, max(0.01, deadline - time.monotonic())))
        except (httpx.TimeoutException, httpx.NetworkError):
            time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
            continue
        if response.status_code in {404, 502, 503, 504}:
            time.sleep(1.0)
            continue
        response.raise_for_status()
        trace = response.json()
        generations = [item for item in trace["observations"] if item["type"] == "GENERATION"]
        scores = [item for item in trace["scores"] if item["id"] == score_id and item["name"] == SCORE_NAME]
        if len(generations) > 1 or len(scores) > 1:
            raise RuntimeError("Duplicate generation or score in probe")
        if not generations or not scores or trace.get("totalCost") is None:
            time.sleep(1.0)
            continue
        generation = generations[0]
        usage = generation.get("usageDetails") or {}
        cost = generation.get("calculatedTotalCost")
        if cost is None or not usage:
            time.sleep(1.0)
            continue
        if not math.isclose(cost, expected_cost, rel_tol=1e-6, abs_tol=1e-12) or not math.isclose(trace["totalCost"], expected_cost, rel_tol=1e-6, abs_tol=1e-12):
            raise RuntimeError("Cloud cost differs from the provider usage and verified Standard prices")
        # Langfuse normalizes OpenAI details into disjoint token buckets.
        if sum(value for key, value in usage.items() if key.startswith("input")) != expected_usage["input"]:
            raise RuntimeError("Cloud input usage differs from provider")
        if sum(value for key, value in usage.items() if key.startswith("output")) != expected_usage["output"]:
            raise RuntimeError("Cloud output usage differs from provider")
        if scores[0]["value"] != 1 or trace.get("sessionId") != trace_id:
            raise RuntimeError("Cloud score/session does not match the synthetic probe")
        return {
            "status": "persisted",
            "trace_id": trace_id,
            "trace_path": trace["htmlPath"],
            "generation_id": generation["id"],
            "model": generation["model"],
            "model_id": generation.get("modelId"),
            "usage": usage,
            "cost_usd": cost,
            "score_id": score_id,
            "score_name": SCORE_NAME,
            "score_value": scores[0]["value"],
        }
    raise TimeoutError("Trace, cost and score not queryable within 30 seconds after flush")


def run_probe(settings: Settings) -> dict[str, Any]:
    if not settings.langfuse_tracing_enabled or settings.ai_provider == "deterministic-test":
        return {"status": "disabled"}
    base_url = cloud_url(settings)
    if not all(secret and secret.get_secret_value() for secret in (settings.langfuse_public_key, settings.langfuse_secret_key, settings.openai_api_key)):
        raise ValueError("Probe credentials missing")
    if settings.ai_generation_model != "gpt-5-mini":
        raise ValueError("LF-1 prices and proof cover gpt-5-mini only")
    assert settings.langfuse_public_key is not None and settings.langfuse_secret_key is not None

    # All optional SDK imports and resources come AFTER both gates.
    import httpx
    from langfuse import Langfuse, propagate_attributes
    from opentelemetry.trace import StatusCode

    from customer_care.ai.providers import create_langfuse_probe_client

    public_key = settings.langfuse_public_key.get_secret_value()
    secret_key = settings.langfuse_secret_key.get_secret_value()
    langfuse = Langfuse(
        public_key=public_key, secret_key=secret_key, base_url=base_url,
        environment="local-test", release="lf1-sdk-4.15.1", tracing_enabled=True,
        sample_rate=1.0, timeout=3, flush_at=8, flush_interval=1.0, debug=False,
        # SDK errors may include credential fragments. This success-only
        # diagnostic drops error spans; the application's error adapter is LF-2.
        should_export_span=lambda span: span.status.status_code != StatusCode.ERROR,
    )
    trace_id = uuid4().hex
    started_at = datetime.now(timezone.utc)
    score_id = str(uuid5(NAMESPACE_URL, f"customer-care/{trace_id}/{SCORE_NAME}"))
    metadata = {"simulated": True, "schema_version": 1, "purpose": "lf1_sdk_probe"}
    # Retain safe correlation if verification times out: inspect this trace
    # instead of repeating a billable completion merely to recover its ID.
    print(json.dumps({"status": "started", "trace_id": trace_id, "score_id": score_id, "score_timestamp": started_at.isoformat()}), flush=True)
    try:
        with langfuse.start_as_current_observation(name=PROBE_NAME, trace_context={"trace_id": trace_id}, metadata=metadata) as span:
            with propagate_attributes(session_id=trace_id, metadata=metadata):
                with create_langfuse_probe_client() as client:
                    response = client.chat.completions.create(
                        model="gpt-5-mini", service_tier="default", reasoning_effort="minimal",
                        max_completion_tokens=128,
                        messages=[{"role": "user", "content": "Quanto é 1 + 1? Responda somente com o algarismo, sem explicações."}],
                    )
                answer = response.choices[0].message.content
                if answer is None or answer.strip() != "2" or response.usage is None:
                    raise RuntimeError("Synthetic completion did not meet the probe criterion")
                usage = response.usage
                cached = usage.prompt_tokens_details.cached_tokens if usage.prompt_tokens_details else 0
                expected_cost = ((usage.prompt_tokens - (cached or 0)) * 0.25 + (cached or 0) * 0.025 + usage.completion_tokens * 2.0) / 1_000_000
                print(json.dumps({"status": "generated", "trace_id": trace_id, "provider_usage": {"input": usage.prompt_tokens, "output": usage.completion_tokens, "cached_input": cached or 0}, "expected_cost_usd": expected_cost}), flush=True)
                span.update(output={"answer": answer.strip()})
        langfuse.create_score(
            name=SCORE_NAME, value=1.0, data_type="BOOLEAN", trace_id=trace_id,
            score_id=score_id, timestamp=started_at, metadata=metadata,
            comment="Fixed synthetic arithmetic probe; not an N5 quality assessment.",
        )
        langfuse.flush()
        with httpx.Client(base_url=base_url, auth=(public_key, secret_key), timeout=3.0, follow_redirects=False) as api:
            result = _persisted_proof(api, trace_id, score_id, expected_cost, {"input": usage.prompt_tokens, "output": usage.completion_tokens})
        result["trace_url"] = base_url + result.pop("trace_path")
        result["score_timestamp"] = started_at.isoformat()
        return result
    finally:
        langfuse.shutdown()


def main() -> int:
    # This standalone process emits only the selected result or error class;
    # third-party diagnostics can contain response bodies or credential fragments.
    logging.disable(logging.CRITICAL)
    try:
        result = run_probe(get_settings())
    except Exception as error:
        print(json.dumps({"status": "failed", "error_type": type(error).__name__}))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
