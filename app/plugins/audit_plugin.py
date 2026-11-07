"""
Audit trail plugin recording billing lifecycle and operational events.
"""
from __future__ import annotations
from typing import Any, Dict, List
from datetime import datetime
from app.core.entity import utc_now
from app.config.logging import logger
from app.plugins.hooks import (
    Plugin,
    OnPlanCreatedHook,
    OnSubscriptionCreatedHook,
    OnSubscriptionCanceledHook,
    OnInvoiceGeneratedHook,
    OnInvoicePaidHook,
)


class AuditPlugin(Plugin, OnPlanCreatedHook, OnSubscriptionCreatedHook, OnSubscriptionCanceledHook, OnInvoiceGeneratedHook, OnInvoicePaidHook):
    def __init__(self) -> None:
        self.audit_log: List[Dict[str, Any]] = []

    def name(self) -> str:
        return "audit_hook"

    def _record(self, action: str, details: Dict[str, Any]) -> None:
        entry = {
            "action": action,
            "timestamp": utc_now().isoformat(),
            "details": details,
        }
        self.audit_log.append(entry)
        logger.info(f"AUDIT: {action} - {details}")

    def on_plan_created(self, plan: Any) -> None:
        self._record("plan.created", {"plan_id": plan.id, "slug": plan.slug})

    def on_subscription_created(self, sub: Any) -> None:
        self._record("subscription.created", {"sub_id": sub.id, "tenant_id": sub.tenant_id, "plan_id": sub.plan_id})

    def on_subscription_canceled(self, sub: Any) -> None:
        self._record("subscription.canceled", {"sub_id": sub.id, "tenant_id": sub.tenant_id})

    def on_invoice_generated(self, inv: Any) -> None:
        self._record("invoice.generated", {"inv_id": inv.id, "tenant_id": inv.tenant_id, "total": str(inv.total)})

    def on_invoice_paid(self, inv: Any) -> None:
        self._record("invoice.paid", {"inv_id": inv.id, "payment_ref": inv.payment_ref})
