"""
Pydantic schemas for Invoices and Line Items.
"""
from __future__ import annotations
from typing import Dict, List, Optional
from pydantic import BaseModel
from app.schemas.plan import MoneySchema


class LineItemResponseSchema(BaseModel):
    id: str
    invoice_id: str
    feature_key: Optional[str] = None
    description: str
    quantity: int
    unit_amount: MoneySchema
    amount: MoneySchema
    type: str
    metadata: Dict[str, str]


class InvoiceGenerateRequestSchema(BaseModel):
    subscription_id: str
    period_start: Optional[str] = None
    period_end: Optional[str] = None


class InvoiceResponseSchema(BaseModel):
    id: str
    tenant_id: str
    subscription_id: str
    status: str
    currency: str
    subtotal: MoneySchema
    tax_amount: MoneySchema
    discount_amount: MoneySchema
    credit_amount: MoneySchema
    total: MoneySchema
    line_items: List[LineItemResponseSchema]
    period_start: str
    period_end: str
    due_date: Optional[str] = None
    paid_at: Optional[str] = None
    voided_at: Optional[str] = None
    void_reason: Optional[str] = None
    payment_ref: Optional[str] = None
    provider_id: Optional[str] = None
    provider_name: Optional[str] = None
    app_id: str
    metadata: Dict[str, str]
    created_at: str
    updated_at: str
