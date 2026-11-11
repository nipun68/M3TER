"""
Billing analytics and metrics overview routes.
"""
from __future__ import annotations
from typing import Dict
from fastapi import APIRouter, Depends, Query
from app.api.dependencies import get_ledger
from app.models.invoice import InvoiceStatus
from app.models.subscription import SubscriptionStatus
from app.services.ledger import Ledger

router = APIRouter(prefix="/analytics", tags=["Billing Analytics"])


@router.get("/summary")
def get_billing_summary(
    app_id: str = Query("default"),
    ledger: Ledger = Depends(get_ledger),
) -> Dict:
    plans = ledger.list_plans(app_id=app_id)
    subs = ledger.list_subscriptions(app_id=app_id)
    invoices = ledger.store.list_invoices(app_id=app_id)

    active_subs = sum(1 for s in subs if s.status == SubscriptionStatus.ACTIVE)
    trial_subs = sum(1 for s in subs if s.status == SubscriptionStatus.TRIALING)
    past_due_subs = sum(1 for s in subs if s.status == SubscriptionStatus.PAST_DUE)

    paid_invoices = sum(1 for i in invoices if i.status == InvoiceStatus.PAID)
    pending_invoices = sum(1 for i in invoices if i.status == InvoiceStatus.PENDING)

    return {
        "app_id": app_id,
        "total_plans": len(plans),
        "total_subscriptions": len(subs),
        "active_subscriptions": active_subs,
        "trialing_subscriptions": trial_subs,
        "past_due_subscriptions": past_due_subs,
        "total_invoices": len(invoices),
        "paid_invoices": paid_invoices,
        "pending_invoices": pending_invoices,
    }
