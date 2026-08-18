import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("customer_care.http")


def client_ip(request: Request) -> str:
    """The real originating client address, trusting exactly one reverse
    proxy hop (local docker-compose's nginx, or Firebase Hosting's `/api/**`
    rewrite to Cloud Run in production — both are same-origin proxies with
    no other hop in front of them, per `DEPLOYMENT.md`).

    `request.client.host` alone is wrong here: it is the immediate TCP peer,
    which behind either proxy is always that proxy's own single address —
    every real customer collapses onto one shared value. That was found as
    a real bug (V3 tasks.md T132/analysis.md, correcting V2 plan.md §13.1):
    it makes the per-source token-validation lockout (`rate_limit.py`)
    global instead of per-customer, so one attacker's lockout denies every
    legitimate customer, not just themselves.

    Both proxies are configured to *set* (not append/trust-passthrough)
    `X-Forwarded-For` from their own view of the connecting peer — nginx via
    `proxy_set_header X-Forwarded-For $remote_addr` (`frontend/nginx.conf`),
    Cloud Run's edge doing the equivalent for Firebase Hosting's rewrite —
    so trusting this header's first entry is safe in this topology. It is
    not safe to trust a client-supplied value directly, so this must never
    be relied on if the app is ever placed behind additional/different
    proxying without revisiting this assumption.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        logger.info(
            "request_completed method=%s path=%s status=%s duration_ms=%s request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            round((time.perf_counter() - started) * 1000),
            request_id,
        )
        return response
