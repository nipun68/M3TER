"""
FastAPI dependency injection utilities.
"""
from __future__ import annotations
from typing import Optional
from fastapi import Header, HTTPException, Request, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config.settings import settings
from app.config.logging import logger
from app.core.security import decode_access_token
from app.core.tenant_context import set_current_tenant, set_current_app
from app.plugins.registry import PluginRegistry
from app.plugins.audit_plugin import AuditPlugin
from app.providers.mock_provider import MockPaymentProvider
from app.providers.stripe_provider import StripePaymentProvider
from app.repositories.base import BaseStore
from app.repositories.memory_store import MemoryStore
from app.repositories.mongo_store import MongoStore
from app.services.ledger import Ledger

bearer_scheme = HTTPBearer(auto_error=False)

# Singleton instances
_store: Optional[BaseStore] = None
_ledger: Optional[Ledger] = None


def get_store() -> BaseStore:
    global _store
    if _store is None:
        try:
            mongo = MongoStore(uri=settings.MONGO_URI)
            if mongo.ping():
                mongo.migrate()
                _store = mongo
                logger.info("Using MongoDB Atlas store.")
            else:
                _store = MemoryStore()
                logger.info("MongoDB ping failed. Falling back to MemoryStore.")
        except Exception as e:
            logger.warning(f"Could not connect to MongoDB: {e}. Using MemoryStore.")
            _store = MemoryStore()
    return _store


def get_ledger() -> Ledger:
    global _ledger
    if _ledger is None:
        store = get_store()
        plugins = PluginRegistry()
        plugins.register(AuditPlugin())

        ledger = Ledger(
            store=store,
            plugins=plugins,
            meter_batch_size=settings.METER_BATCH_SIZE,
            meter_flush_interval_seconds=settings.METER_FLUSH_INTERVAL_SECONDS,
            entitlement_cache_ttl_seconds=settings.ENTITLEMENT_CACHE_TTL_SECONDS,
        )

        # Register providers
        if settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET:
            stripe_prov = StripePaymentProvider(
                api_key=settings.STRIPE_SECRET_KEY,
                webhook_secret=settings.STRIPE_WEBHOOK_SECRET
            )
            ledger.register_provider(stripe_prov)
        else:
            ledger.register_provider(MockPaymentProvider("stripe"))
            ledger.register_provider(MockPaymentProvider("mock"))

        _ledger = ledger
    return _ledger


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)) -> dict:
    """Validates JWT bearer token, reproducing Express.js authMiddleware."""
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Token missing")

    try:
        payload = decode_access_token(credentials.credentials, secret_key=settings.JWT_SECRET_KEY)
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def resolve_tenant(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_app_id: Optional[str] = Header(None, alias="X-App-ID"),
) -> str:
    tenant = x_tenant_id or "default_tenant"
    app_id = x_app_id or "default"
    set_current_tenant(tenant)
    set_current_app(app_id)
    return tenant
