"""
Pydantic schemas for Coupons.
"""
from __future__ import annotations
from typing import Dict, Optional
from pydantic import BaseModel, Field
from app.schemas.plan import MoneySchema


class CouponCreateSchema(BaseModel):
    code: str
    name: str = ""
    type: str = Field(default="percentage", description="percentage or amount")
    amount: Optional[MoneySchema] = None
    percentage: int = 0
    currency: str = "usd"
    max_redemptions: int = 0
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    app_id: str = "default"
    metadata: Dict[str, str] = Field(default_factory=dict)


class CouponApplySchema(BaseModel):
    subscription_id: str
    code: str
    app_id: str = "default"


class CouponResponseSchema(BaseModel):
    id: str
    code: str
    name: str
    type: str
    amount: MoneySchema
    percentage: int
    currency: str
    max_redemptions: int
    times_redeemed: int
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    app_id: str
    metadata: Dict[str, str]
    created_at: str
    updated_at: str
