"""
Invoice and Line Item domain models reproducing invoice/models.go.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from app.core.entity import Entity, utc_now
from app.core.id import new_id, PREFIX_INVOICE, PREFIX_LINE_ITEM
from app.core.money import Money, zero


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    PAID = "paid"
    PAST_DUE = "past_due"
    VOIDED = "voided"


class LineItemType(str, Enum):
    BASE = "base"
    USAGE = "usage"
    OVERAGE = "overage"
    SEAT = "seat"
    CREDIT = "credit"
    DISCOUNT = "discount"
    TAX = "tax"


@dataclass
class LineItem:
    id: str = field(default_factory=lambda: new_id(PREFIX_LINE_ITEM))
    invoice_id: str = ""
    feature_key: Optional[str] = None
    description: str = ""
    quantity: int = 1
    unit_amount: Money = field(default_factory=lambda: zero("usd"))
    amount: Money = field(default_factory=lambda: zero("usd"))
    type: LineItemType = LineItemType.BASE
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "feature_key": self.feature_key,
            "description": self.description,
            "quantity": self.quantity,
            "unit_amount": self.unit_amount.to_dict(),
            "amount": self.amount.to_dict(),
            "type": self.type.value if isinstance(self.type, LineItemType) else str(self.type),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict, default_currency: str = "usd") -> LineItem:
        u_amt = d.get("unit_amount")
        amt = d.get("amount")
        return cls(
            id=d.get("id", new_id(PREFIX_LINE_ITEM)),
            invoice_id=d.get("invoice_id", ""),
            feature_key=d.get("feature_key"),
            description=d.get("description", ""),
            quantity=int(d.get("quantity", 1)),
            unit_amount=Money.from_dict(u_amt) if isinstance(u_amt, dict) else zero(default_currency),
            amount=Money.from_dict(amt) if isinstance(amt, dict) else zero(default_currency),
            type=LineItemType(d.get("type", LineItemType.BASE.value)),
            metadata=dict(d.get("metadata", {})),
        )


@dataclass
class Invoice(Entity):
    id: str = field(default_factory=lambda: new_id(PREFIX_INVOICE))
    tenant_id: str = ""
    subscription_id: str = ""
    status: InvoiceStatus = InvoiceStatus.DRAFT
    currency: str = "usd"
    subtotal: Money = field(default_factory=lambda: zero("usd"))
    tax_amount: Money = field(default_factory=lambda: zero("usd"))
    discount_amount: Money = field(default_factory=lambda: zero("usd"))
    credit_amount: Money = field(default_factory=lambda: zero("usd"))
    total: Money = field(default_factory=lambda: zero("usd"))
    line_items: List[LineItem] = field(default_factory=list)
    period_start: datetime = field(default_factory=utc_now)
    period_end: datetime = field(default_factory=utc_now)
    due_date: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    voided_at: Optional[datetime] = None
    void_reason: Optional[str] = None
    payment_ref: Optional[str] = None
    provider_id: Optional[str] = None
    provider_name: Optional[str] = None
    app_id: str = "default"
    metadata: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "subscription_id": self.subscription_id,
            "status": self.status.value if isinstance(self.status, InvoiceStatus) else str(self.status),
            "currency": self.currency,
            "subtotal": self.subtotal.to_dict(),
            "tax_amount": self.tax_amount.to_dict(),
            "discount_amount": self.discount_amount.to_dict(),
            "credit_amount": self.credit_amount.to_dict(),
            "total": self.total.to_dict(),
            "line_items": [li.to_dict() for li in self.line_items],
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "voided_at": self.voided_at.isoformat() if self.voided_at else None,
            "void_reason": self.void_reason,
            "payment_ref": self.payment_ref,
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "app_id": self.app_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> Invoice:
        def parse_dt(v):
            if v is None:
                return None
            return datetime.fromisoformat(v) if isinstance(v, str) else v

        curr = d.get("currency", "usd").lower()
        line_items = [LineItem.from_dict(li, curr) for li in d.get("line_items", [])]
        return cls(
            id=d.get("id", new_id(PREFIX_INVOICE)),
            tenant_id=d.get("tenant_id", ""),
            subscription_id=d.get("subscription_id", ""),
            status=InvoiceStatus(d.get("status", InvoiceStatus.DRAFT.value)),
            currency=curr,
            subtotal=Money.from_dict(d.get("subtotal", {})),
            tax_amount=Money.from_dict(d.get("tax_amount", {})),
            discount_amount=Money.from_dict(d.get("discount_amount", {})),
            credit_amount=Money.from_dict(d.get("credit_amount", {})),
            total=Money.from_dict(d.get("total", {})),
            line_items=line_items,
            period_start=parse_dt(d.get("period_start")) or utc_now(),
            period_end=parse_dt(d.get("period_end")) or utc_now(),
            due_date=parse_dt(d.get("due_date")),
            paid_at=parse_dt(d.get("paid_at")),
            voided_at=parse_dt(d.get("voided_at")),
            void_reason=d.get("void_reason"),
            payment_ref=d.get("payment_ref"),
            provider_id=d.get("provider_id"),
            provider_name=d.get("provider_name"),
            app_id=d.get("app_id", "default"),
            metadata=dict(d.get("metadata", {})),
            created_at=parse_dt(d.get("created_at")) or utc_now(),
            updated_at=parse_dt(d.get("updated_at")) or utc_now(),
        )
