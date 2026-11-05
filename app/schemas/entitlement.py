"""
Pydantic schemas for Entitlement checks.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class EntitlementCheckSchema(BaseModel):
    tenant_id: str
    feature_key: str
    app_id: str = "default"


class EntitlementResponseSchema(BaseModel):
    allowed: bool
    feature: str
    used: int = 0
    limit: int = 0
    remaining: int = 0
    soft_limit: bool = False
    reason: Optional[str] = None
