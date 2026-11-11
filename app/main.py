"""
Main FastAPI Application Entry Point.
Assembles the complete migrated Python architecture, all billing routes,
and preserves original student and authentication APIs.
"""
from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.dependencies import get_ledger
from app.api.middleware import TenantContextMiddleware
from app.api.routes import (
    auth,
    students,
    plans,
    features,
    subscriptions,
    metering,
    entitlements,
    invoices,
    coupons,
    payments,
    webhooks,
    analytics,
    lifecycle,
)
from app.config.logging import logger
from app.config.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start Ledger background workers
    ledger = get_ledger()
    await ledger.start()
    logger.info("M3TER Billing & Metering Engine started.")
    yield
    # Shutdown: Stop workers and flush buffers
    await ledger.stop()
    logger.info("M3TER Billing Engine shut down cleanly.")


app = FastAPI(
    title="M3TER Engine — Usage-Based Billing & Rating API",
    description="Enterprise Usage-Based Pricing, High-Throughput Metering, Entitlement, and Billing Engine",
    version="1.0.0",
    lifespan=lifespan,
)

# Custom Middleware
app.add_middleware(TenantContextMiddleware)

# Include All API Routers
app.include_router(auth.router)
app.include_router(students.router)
app.include_router(plans.router)
app.include_router(features.router)
app.include_router(subscriptions.router)
app.include_router(metering.router)
app.include_router(entitlements.router)
app.include_router(invoices.router)
app.include_router(coupons.router)
app.include_router(payments.router)
app.include_router(webhooks.router)
app.include_router(analytics.router)
app.include_router(lifecycle.router)

# Mount Static UI Files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    """
    Root endpoint serving the interactive billing and management dashboard.
    Accepts text/html for browser rendering, or JSON when requested by API clients.
    """
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        index_file = static_dir / "index.html"
        if index_file.exists():
            return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse(
        content="<h3>M3TER Usage-Based Billing & Rating Engine is running!</h3><p>Visit <a href='/docs'>/docs</a> for OpenAPI documentation or open in browser for the dashboard.</p>"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
