"""
Pydantic schemas for Subscriptions.
"""
from __future__ import annotations
from typing import Dict, Optional
from pydantic import BaseModel, Field


class SubscriptionCreateSchema(BaseModel):
    tenant_id: str
    plan_id: str
    app_id: str = "default"
    quantity: Dict[str, int] = Field(default_factory=dict, description="Seats or quantity per feature")
    trial_days: Optional[int] = None
    metadata: Dict[str, str] = Field(default_factory=dict)


class SubscriptionChangePlanSchema(BaseModel):
    plan_id: str
    quantity: Optional[Dict[str, int]] = None


class SubscriptionResponseSchema(BaseModel):
    id: str
    tenant_id: str
    plan_id: str
    status: str
    current_period_start: str
    current_period_end: str
    trial_start: Optional[str] = None
    trial_end: Optional[str] = None
    canceled_at: Optional[str] = None
    cancel_at: Optional[str] = None
    ended_at: Optional[str] = None
    paused_at: Optional[str] = None
    app_id: str
    provider_id: Optional[str] = None
    provider_name: Optional[str] = None
    metadata: Dict[str, str]
    quantity: Dict[str, int]
    created_at: str
    updated_at: str
