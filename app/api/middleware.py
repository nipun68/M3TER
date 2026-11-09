"""
Custom middleware for tenant isolation, request tracing, and security headers.
"""
from __future__ import annotations
import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.config.logging import logger
from app.core.tenant_context import set_current_tenant, set_current_app


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tenant_id = request.headers.get("X-Tenant-ID") or request.query_params.get("tenant_id")
        app_id = request.headers.get("X-App-ID") or request.query_params.get("app_id") or "default"

        set_current_tenant(tenant_id)
        set_current_app(app_id)

        start_time = time.time()
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"Unhandled server error: {e}", exc_info=True)
            return Response(
                content='{"error": "Internal server error"}',
                status_code=500,
                media_type="application/json"
            )

        duration_ms = (time.time() - start_time) * 1000.0
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
        if tenant_id:
            response.headers["X-Tenant-ID"] = tenant_id

        return response
