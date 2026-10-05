"""Request correlation, consistent error envelopes and structured request logs."""
import json
import logging
import time
from uuid import uuid4
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger("nwis.api")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())


def install(app):
    def error(request, status, code, detail):
        return JSONResponse(status_code=status, content={"detail": detail,
            "error": {"code": code, "message": detail, "request_id": request.state.request_id}},
            headers={"X-Request-ID": request.state.request_id})

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        response = error(request, exc.status_code, f"HTTP_{exc.status_code}", exc.detail)
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error(request, 422, "VALIDATION_ERROR", "Request validation failed")

    @app.middleware("http")
    async def request_log(request, call_next):
        request.state.request_id = uuid4().hex
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled request error request_id=%s", request.state.request_id)
            response = error(request, 500, "INTERNAL_ERROR", "Internal application error")
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
        from .config import get_settings
        if get_settings().demo_mode:
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https://tile.openstreetmap.org; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'"
        logger.info(json.dumps({"request_id": request.state.request_id, "method": request.method,
            "path": request.url.path, "status": response.status_code,
            "duration_ms": round((time.monotonic()-started)*1000, 2)}))
        return response
