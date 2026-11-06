"""
Mock payment provider for deterministic testing and offline sandbox operation.
"""
from __future__ import annotations
import json
from typing import Dict, List, Optional
from app.models.plan import Plan
from app.models.feature import CatalogFeature
from app.models.subscription import Subscription
from app.models.invoice import Invoice
from app.providers.base import BasePaymentProvider, PaymentMethod, WebhookResult


class MockPaymentProvider(BasePaymentProvider):
    def __init__(self, name: str = "mock") -> None:
        self._name = name
        self.synced_plans: Dict[str, str] = {}
        self.synced_invoices: Dict[str, str] = {}

    def name(self) -> str:
        return self._name

    def list_payment_methods(self, tenant_id: str) -> List[PaymentMethod]:
        return [
            PaymentMethod(
                id=f"pm_mock_{tenant_id}",
                type="card",
                last4="4242",
                brand="visa",
                expiry_month=12,
                expiry_year=2030,
                is_default=True,
                provider_name=self._name,
                provider_id=f"pm_mock_{tenant_id}"
            )
        ]

    def sync_plan(self, p: Plan) -> str:
        pid = f"mock_plan_{p.id}"
        self.synced_plans[p.id] = pid
        return pid

    def sync_feature(self, f: CatalogFeature) -> str:
        return f"mock_feat_{f.id}"

    def sync_subscription(self, s: Subscription) -> str:
        return f"mock_sub_{s.id}"

    def sync_invoice(self, inv: Invoice) -> str:
        pid = f"mock_inv_{inv.id}"
        self.synced_invoices[inv.id] = pid
        return pid

    def handle_webhook(self, payload: bytes, signature_header: Optional[str] = None) -> WebhookResult:
        try:
            data = json.loads(payload.decode("utf-8"))
            event_type = data.get("type", "test.event")
            event_obj = data.get("data", {}).get("object", {})
            metadata = event_obj.get("metadata", {})
            ledger_inv_id = metadata.get("ledger_invoice_id") or data.get("entity_id", "")
            entity_type = "invoice" if (ledger_inv_id or "invoice" in event_type) else data.get("entity_type", "")
            return WebhookResult(
                event_type=event_type,
                provider_id=data.get("id", "evt_mock"),
                entity_type=entity_type,
                entity_id=ledger_inv_id,
                handled=True,
            )
        except Exception as e:
            return WebhookResult(event_type="unknown", handled=False, error=str(e))
