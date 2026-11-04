"""
Pydantic schemas for Metering.
"""
from __future__ import annotations
from typing import Dict, Optional
from pydantic import BaseModel, Field


class UsageEventSchema(BaseModel):
    tenant_id: str
    feature_key: str
    quantity: int = Field(default=1, description="Quantity of events consumed")
    app_id: str = "default"
    idempotency_key: Optional[str] = Field(default=None, description="Unique key for deduplication")
    metadata: Dict[str, str] = Field(default_factory=dict)


class UsageEventResponseSchema(BaseModel):
    id: str
    tenant_id: str
    app_id: str
    feature_key: str
    quantity: int
    timestamp: str
    idempotency_key: Optional[str] = None
    metadata: Dict[str, str]
