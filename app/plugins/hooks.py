"""
Plugin hooks and extension protocols reproducing plugin/plugin.go.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from datetime import datetime
from app.core.money import Money
from app.models.plan import Plan, PriceTier
from app.models.feature import CatalogFeature
from app.models.subscription import Subscription, Renewal
from app.models.meter import UsageEvent
from app.models.entitlement import EntitlementResult
from app.models.invoice import Invoice
from app.models.coupon import Coupon


@runtime_checkable
class Plugin(Protocol):
    def name(self) -> str: ...


# ── Lifecycle Hooks ──
@runtime_checkable
class OnInitHook(Protocol):
    def on_init(self, ledger: Any) -> None: ...


@runtime_checkable
class OnShutdownHook(Protocol):
    def on_shutdown(self) -> None: ...


# ── Plan Hooks ──
@runtime_checkable
class OnPlanCreatedHook(Protocol):
    def on_plan_created(self, plan: Plan) -> None: ...


@runtime_checkable
class OnPlanUpdatedHook(Protocol):
    def on_plan_updated(self, old_plan: Plan, new_plan: Plan) -> None: ...


@runtime_checkable
class OnPlanArchivedHook(Protocol):
    def on_plan_archived(self, plan_id: str) -> None: ...


# ── Subscription Hooks ──
@runtime_checkable
class OnSubscriptionCreatedHook(Protocol):
    def on_subscription_created(self, sub: Subscription) -> None: ...


@runtime_checkable
class OnSubscriptionChangedHook(Protocol):
    def on_subscription_changed(self, sub: Subscription, old_plan: Plan, new_plan: Plan) -> None: ...


@runtime_checkable
class OnSubscriptionCanceledHook(Protocol):
    def on_subscription_canceled(self, sub: Subscription) -> None: ...


@runtime_checkable
class OnSubscriptionCancelScheduledHook(Protocol):
    def on_subscription_cancel_scheduled(self, sub: Subscription) -> None: ...


@runtime_checkable
class OnSubscriptionTrialEndedHook(Protocol):
    def on_subscription_trial_ended(self, sub: Subscription) -> None: ...


@runtime_checkable
class OnSubscriptionRenewedHook(Protocol):
    def on_subscription_renewed(self, renewal: Renewal) -> None: ...


# ── Usage / Metering Hooks ──
@runtime_checkable
class OnUsageIngestedHook(Protocol):
    def on_usage_ingested(self, events: List[UsageEvent]) -> None: ...


@runtime_checkable
class OnUsageFlushedHook(Protocol):
    def on_usage_flushed(self, count: int, elapsed_ms: float) -> None: ...


# ── Entitlement Hooks ──
@runtime_checkable
class OnEntitlementCheckedHook(Protocol):
    def on_entitlement_checked(self, result: EntitlementResult) -> None: ...


@runtime_checkable
class OnQuotaExceededHook(Protocol):
    def on_quota_exceeded(self, tenant_id: str, feature_key: str, used: int, limit: int) -> None: ...


@runtime_checkable
class OnSoftLimitReachedHook(Protocol):
    def on_soft_limit_reached(self, tenant_id: str, feature_key: str, used: int, limit: int) -> None: ...


# ── Invoice Hooks ──
@runtime_checkable
class OnInvoiceGeneratedHook(Protocol):
    def on_invoice_generated(self, inv: Invoice) -> None: ...


@runtime_checkable
class OnInvoicePaidHook(Protocol):
    def on_invoice_paid(self, inv: Invoice) -> None: ...


@runtime_checkable
class OnInvoiceVoidedHook(Protocol):
    def on_invoice_voided(self, inv: Invoice, reason: str) -> None: ...


@runtime_checkable
class OnInvoicePastDueHook(Protocol):
    def on_invoice_past_due(self, inv: Invoice) -> None: ...


# ── Strategy Protocols ──
@runtime_checkable
class PricingStrategy(Protocol):
    def strategy_name(self) -> str: ...
    def compute(self, tiers: List[PriceTier], usage: int, included: int, currency: str) -> Money: ...


@runtime_checkable
class UsageAggregator(Protocol):
    def aggregator_name(self) -> str: ...
    def aggregate(self, events: List[UsageEvent]) -> int: ...


@runtime_checkable
class TaxCalculator(Protocol):
    def calculate_tax(self, net_amount: Money, tenant_id: str) -> Optional[Money]: ...
