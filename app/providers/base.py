"""
Payment Provider interface and DTOs reproducing provider/provider.go.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from app.core.entity import utc_now
from app.models.plan import Plan
from app.models.feature import CatalogFeature
from app.models.subscription import Subscription
from app.models.invoice import Invoice


@dataclass
class PaymentMethod:
    id: str
    type: str  # "card", "bank_account"
    last4: str
    brand: str  # "visa", "mastercard"
    expiry_month: int
    expiry_year: int
    is_default: bool
    provider_name: str
    provider_id: str

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "last4": self.last4,
            "brand": self.brand,
            "expiry_month": self.expiry_month,
            "expiry_year": self.expiry_year,
            "is_default": self.is_default,
            "provider_name": self.provider_name,
            "provider_id": self.provider_id,
        }


@dataclass
class WebhookResult:
    event_type: str
    provider_id: str = ""
    entity_type: str = ""  # "invoice", "subscription", "customer"
    entity_id: str = ""
    handled: bool = False
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict:
        return {
            "event_type": self.event_type,
            "provider_id": self.provider_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "handled": self.handled,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SyncResult:
    provider_name: str
    provider_id: str
    entity_type: str
    entity_id: str
    direction: str  # "push" or "pull"
    success: bool
    error: Optional[str] = None


class BasePaymentProvider(ABC):
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def list_payment_methods(self, tenant_id: str) -> List[PaymentMethod]: ...

    @abstractmethod
    def sync_plan(self, p: Plan) -> str: ...

    @abstractmethod
    def sync_feature(self, f: CatalogFeature) -> str: ...

    @abstractmethod
    def sync_subscription(self, s: Subscription) -> str: ...

    @abstractmethod
    def sync_invoice(self, inv: Invoice) -> str: ...

    @abstractmethod
    def handle_webhook(self, payload: bytes, signature_header: Optional[str] = None) -> WebhookResult: ...
