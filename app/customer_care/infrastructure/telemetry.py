"""013: optional, explicit Langfuse observations. No business objects or SDK hooks.

Initialize at process startup. Payload factories run only while enabled and
inside the fail-open boundary. SDK exceptions never repeat or suppress business
work. The OpenTelemetry context is used only while creating an observation;
it never encloses application code or automatically records an exception.
"""

import atexit
import logging
import math
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from customer_care.shared.settings import get_settings

Payload = Callable[[], dict[str, Any]]
_client: Any = None
_tracer: Any = None
_initialized = False
_owners = 0
_initialization_lock = threading.Lock()
_current: ContextVar["Observation | None"] = ContextVar("customer_care_observation", default=None)
_origin: ContextVar[str | None] = ContextVar("customer_care_execution_origin", default=None)
SHUTDOWN_TIMEOUT_SECONDS = 5.0
_OBSERVATION_NAMES = frozenset({
    "n5.process_turn", "rag.retrieve", "ai.answer", "ai.clinical_rerank",
    "ai.date_intent", "ai.n5_free", "ai.embedding", "autonomy.decision",
    "autonomy.pending_opened", "autonomy.pending_resolved", "message.sent",
})


def enabled() -> bool:
    try:
        settings = get_settings()
        return settings.langfuse_tracing_enabled and settings.ai_provider != "deterministic-test"
    except Exception:
        return False


def _plain(value: Any) -> Any:
    """Copy only explicit JSON values. Never repr/serialize arbitrary objects."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) in (list, tuple):
        return [_plain(item) for item in value]
    if type(value) is dict and all(type(key) is str for key in value):
        return {key: _plain(item) for key, item in value.items()}
    raise TypeError("Telemetry requires explicit JSON fields")


class _SDKLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Exporter errors may contain response bodies, headers or credentials.
        record.msg = "Optional telemetry SDK diagnostic (details suppressed)"
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


def initialize() -> None:
    global _client, _tracer, _initialized, _owners
    if not enabled():
        return
    with _initialization_lock:
        if _initialized:
            if _client is not None:
                _owners += 1
            return
        _initialized = True
        try:
            from customer_care.infrastructure.langfuse_probe import cloud_url

            settings = get_settings()
            base_url = cloud_url(settings)
            if not settings.langfuse_public_key or not settings.langfuse_secret_key:
                return
            public_key = settings.langfuse_public_key.get_secret_value()
            secret_key = settings.langfuse_secret_key.get_secret_value()
            if not public_key or not secret_key:
                return

            from langfuse import Langfuse
            from opentelemetry.sdk.trace import TracerProvider

            # A private provider avoids global instrumentation and its atexit
            # shutdown; only the lifecycle below may wait for telemetry.
            _tracer = TracerProvider(shutdown_on_exit=False)
            for name, logger in list(logging.Logger.manager.loggerDict.items()):
                if isinstance(logger, logging.Logger) and name.startswith(("langfuse", "opentelemetry")):
                    logger.addFilter(_SDKLogFilter())
            _client = Langfuse(
                public_key=public_key, secret_key=secret_key, base_url=base_url,
                environment=settings.langfuse_tracing_environment,
                release="customer-care-013", tracing_enabled=True, sample_rate=1.0,
                timeout=3, flush_at=64, flush_interval=1.0, debug=False,
                tracer_provider=_tracer,
                # This private tracer exports only explicit app observations.
                should_export_span=lambda span: span.name in _OBSERVATION_NAMES,
            )
            # SDK 4.15.1 registers an unbounded queue.join at process exit.
            # Its exact callback is version-checked by the adapter tests.
            if _client._resources is not None:
                atexit.unregister(_client._resources.shutdown)
            _owners = 1
        except Exception:
            _client = None


def shutdown() -> None:
    global _client, _owners
    with _initialization_lock:
        _owners = max(0, _owners - 1)
        if _owners:
            return
        client, tracer = _client, _tracer
        _client = None
    if client is None:
        return

    def finish() -> None:
        try:
            client.shutdown()
        except Exception:
            pass
        finally:
            try:
                if tracer is not None:
                    tracer.shutdown()
            except Exception:
                pass

    try:
        worker = threading.Thread(target=finish, name="customer-care-telemetry-shutdown", daemon=True)
        worker.start()
        worker.join(timeout=SHUTDOWN_TIMEOUT_SECONDS)
    except Exception:
        pass


@contextmanager
def execution_origin(value: str) -> Iterator[None]:
    token = _origin.set(value)
    try:
        yield
    finally:
        _origin.reset(token)


@contextmanager
def correlation(identity: Payload) -> Iterator[None]:
    """Group an explicit manual/pre-turn operation without adding a span."""
    context = Observation()
    if _client is None or not enabled():
        yield
        return
    try:
        values = _plain(identity())
        context.trace_id = values.pop("trace_id", None) or uuid4().hex
        context.session_id = values.pop("session_id", None)
        context.metadata = values
    except Exception:
        pass
    token = _current.set(context)
    try:
        yield
    finally:
        _current.reset(token)


class Observation:
    def __init__(self) -> None:
        self.raw: Any = None
        self.trace_id: str | None = None
        self.session_id: str | None = None
        self.metadata: dict[str, Any] = {}

    def update(self, payload: Payload) -> None:
        if self.raw is None or not enabled():
            return
        try:
            values = _plain(payload())
            self.metadata.update(values.pop("metadata", {}))
            self.raw.update(**values, metadata=self.metadata)
        except Exception:
            pass

    def error(self, error: BaseException) -> None:
        if "error_class" in self.metadata:
            return
        self.update(lambda: {"level": "ERROR", "status_message": type(error).__name__, "metadata": {"error_class": type(error).__name__}})


_NOOP = Observation()


@contextmanager
def observe(name: str, payload: Payload | None = None, *, identity: Payload | None = None, kind: str = "span") -> Iterator[Observation]:
    if _client is None or not enabled():
        yield _NOOP
        return
    observation = Observation()
    parent = _current.get() if identity is None else None
    try:
        values = _plain(payload()) if payload else {}
        identification = _plain(identity()) if identity else {}
        observation.trace_id = identification.pop("trace_id", None) or (parent.trace_id if parent else uuid4().hex)
        observation.session_id = identification.pop("session_id", None) or (parent.session_id if parent else None)
        observation.metadata = {
            **(parent.metadata if parent else {}),
            "simulated": True, "schema_version": 1, "purpose": name,
            **({"execution_origin": _origin.get()} if _origin.get() else {}),
            **identification, **values.pop("metadata", {}),
        }
        from langfuse import propagate_attributes

        # No business code inside an SDK context manager (including error
        # handling). An SDK __enter__/__exit__ failure cannot eat its result.
        trace_name = "n5.process_turn" if "turn_id" in observation.metadata else observation.metadata.get("operation_purpose", name)
        with propagate_attributes(session_id=observation.session_id, trace_name=trace_name):
            if parent and parent.raw is not None:
                observation.raw = parent.raw.start_observation(name=name, as_type=kind, metadata=observation.metadata, **values)
            else:
                observation.raw = _client.start_observation(
                    name=name, as_type=kind, trace_context={"trace_id": observation.trace_id},
                    metadata=observation.metadata, **values,
                )
    except Exception:
        # Even if propagation exit failed after creation, finish that span.
        pass
    token = _current.set(observation)
    try:
        yield observation
    except BaseException as error:
        observation.error(error)
        raise
    finally:
        _current.reset(token)
        try:
            if observation.raw is not None:
                observation.raw.end()
        except Exception:
            pass


def current() -> Observation:
    return _current.get() or _NOOP


def score(name: str, value: float | str, *, key: str, timestamp: str, data_type: str, trace_id: str | None = None) -> None:
    if _client is None or not enabled():
        return
    try:
        observation = current()
        _client.create_score(
            name=name, value=value, trace_id=trace_id or observation.trace_id,
            score_id=str(uuid5(NAMESPACE_URL, f"customer-care/013/{key}/{name}")),
            timestamp=datetime.fromisoformat(timestamp).astimezone(UTC), data_type=data_type,
            metadata={"schema_version": 1, "simulated": True},
        )
    except Exception:
        pass


def turn_scores(path: str, fallback_reason: str | None = None) -> None:
    """Emit the decision before a freeform call, even if that call fails."""
    try:
        context = current()
        turn_id, timestamp = context.metadata["turn_id"], context.metadata["turn_created_at"]
        score("n5.path", path, key=turn_id, timestamp=timestamp, data_type="CATEGORICAL")
        score("n5.fallback_started", float(path == "freeform_fallback"), key=turn_id, timestamp=timestamp, data_type="BOOLEAN")
        if fallback_reason:
            score("n5.fallback_reason", fallback_reason, key=turn_id, timestamp=timestamp, data_type="CATEGORICAL")
    except Exception:
        pass
