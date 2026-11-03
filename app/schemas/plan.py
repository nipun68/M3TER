"""
Pydantic schemas for Billing Plans and Pricing.
"""
from __future__ import annotations
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class MoneySchema(BaseModel):
    amount: int = Field(default=0, description="Amount in minor units (cents/pence)")
    currency: str = Field(default="usd", description="ISO lowercase currency code")
    display: Optional[str] = None


class PriceTierSchema(BaseModel):
    feature_key: str
    type: str = Field(default="graduated", description="graduated, volume, flat")
    up_to: int = Field(default=0, description="Upper bound; 0 or -1 means unbounded")
    unit_amount: MoneySchema = Field(default_factory=lambda: MoneySchema(amount=0, currency="usd"))
    flat_amount: MoneySchema = Field(default_factory=lambda: MoneySchema(amount=0, currency="usd"))
    priority: int = 0


class CreditPoolSchema(BaseModel):
    key: str
    amount: MoneySchema
    feature_keys: List[str] = Field(default_factory=list)


class PlanFeatureSchema(BaseModel):
    id: Optional[str] = None
    catalog_id: Optional[str] = None
    key: str
    name: str
    type: str = Field(default="boolean", description="metered, boolean, seat")
    limit: int = Field(default=0, description="Included limit, -1 for unlimited")
    period: str = Field(default="monthly", description="monthly, yearly, none")
    soft_limit: bool = False
    metadata: Dict[str, str] = Field(default_factory=dict)


class PricingSchema(BaseModel):
    id: Optional[str] = None
    base_amount: MoneySchema = Field(default_factory=lambda: MoneySchema(amount=0, currency="usd"))
    billing_period: str = Field(default="monthly", description="monthly, yearly, none")
    tiers: List[PriceTierSchema] = Field(default_factory=list)


class PlanCreateSchema(BaseModel):
    name: str
    slug: str
    description: str = ""
    currency: str = "usd"
    trial_days: int = 0
    features: List[PlanFeatureSchema] = Field(default_factory=list)
    pricing: Optional[PricingSchema] = None
    credits: List[CreditPoolSchema] = Field(default_factory=list)
    app_id: str = "default"
    metadata: Dict[str, str] = Field(default_factory=dict)


class PlanResponseSchema(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    currency: str
    status: str
    trial_days: int
    features: List[PlanFeatureSchema]
    pricing: Optional[PricingSchema] = None
    credits: List[CreditPoolSchema]
    app_id: str
    provider_id: Optional[str] = None
    provider_name: Optional[str] = None
    metadata: Dict[str, str]
    created_at: str
    updated_at: str
