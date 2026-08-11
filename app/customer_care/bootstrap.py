from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from customer_care.anonymous_access.router import router as anonymous_router
from customer_care.ai.router import router as ai_router
from customer_care.auth.router import router as auth_router
from customer_care.infrastructure.database import check_database
from customer_care.operator_workspace.router import router as operator_router
from customer_care.rag.router import router as rag_router
from customer_care.shared.http import RequestContextMiddleware
from customer_care.shared.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Customer Care AI V1 API",
        version="1.0.0",
    )
    application.add_middleware(RequestContextMiddleware)
    api_prefix = settings.api_root_path.rstrip("/")
    application.include_router(anonymous_router, prefix=api_prefix)
    application.include_router(auth_router, prefix=api_prefix)
    application.include_router(operator_router, prefix=api_prefix)
    application.include_router(rag_router, prefix=api_prefix)
    application.include_router(ai_router, prefix=api_prefix)

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        detail: dict[str, object] = exc.detail if isinstance(exc.detail, dict) else {"code": "HTTP_ERROR", "message": str(exc.detail)}
        detail["request_id"] = getattr(request.state, "request_id", None)
        return JSONResponse(status_code=exc.status_code, content=detail, headers=exc.headers)

    @application.get("/health", tags=["Runtime"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/ready", tags=["Runtime"])
    def readiness() -> dict[str, str]:
        check_database()
        return {"status": "ready"}

    return application
