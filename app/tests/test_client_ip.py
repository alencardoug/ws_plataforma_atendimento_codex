"""Unit tests for shared/http.py's client_ip() — the real-bug correction
found while adding V3's v3.spec.ts (tasks.md T132/analysis.md): the
per-source token-validation rate limiter (V2-2, plan.md §13.1) must key on
the actual originating client, not the reverse proxy's own address, or the
lockout becomes global instead of per-customer."""

from starlette.requests import Request

from customer_care.shared.http import client_ip


def make_request(headers: dict[str, str], client_host: str | None) -> Request:
    scope = {
        "type": "http",
        "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()],
        "client": (client_host, 12345) if client_host else None,
    }
    return Request(scope)


def test_prefers_x_forwarded_for_first_entry() -> None:
    request = make_request({"x-forwarded-for": "203.0.113.7, 172.19.0.4"}, client_host="172.19.0.4")
    assert client_ip(request) == "203.0.113.7"


def test_falls_back_to_direct_peer_when_header_absent() -> None:
    request = make_request({}, client_host="172.19.0.4")
    assert client_ip(request) == "172.19.0.4"


def test_falls_back_to_unknown_when_neither_available() -> None:
    request = make_request({}, client_host=None)
    assert client_ip(request) == "unknown"


def test_distinguishes_two_customers_behind_the_same_proxy() -> None:
    """The bug this fixes: request.client.host alone collapses every
    customer behind one reverse-proxy hop onto the same value."""
    customer_a = make_request({"x-forwarded-for": "203.0.113.7"}, client_host="172.19.0.4")
    customer_b = make_request({"x-forwarded-for": "198.51.100.9"}, client_host="172.19.0.4")
    assert client_ip(customer_a) != client_ip(customer_b)
