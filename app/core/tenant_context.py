"""
Tenant and Application scope context management replicating scope.go.
"""
from __future__ import annotations
import contextvars
from typing import Optional


_tenant_context: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("tenant_id", default=None)
_app_context: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("app_id", default="default")


def get_current_tenant() -> Optional[str]:
    return _tenant_context.get()


def set_current_tenant(tenant_id: Optional[str]) -> contextvars.Token:
    return _tenant_context.set(tenant_id)


def reset_current_tenant(token: contextvars.Token) -> None:
    _tenant_context.reset(token)


def get_current_app() -> str:
    return _app_context.get() or "default"


def set_current_app(app_id: Optional[str]) -> contextvars.Token:
    return _app_context.set(app_id or "default")


def reset_current_app(token: contextvars.Token) -> None:
    _app_context.reset(token)
