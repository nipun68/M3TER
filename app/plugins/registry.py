"""
Plugin Registry providing isolated hook execution and strategy resolution.
Ensures plugin errors are safely logged without crashing core billing operations.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from app.config.logging import logger
from app.plugins.hooks import (
    Plugin,
    OnInitHook,
    OnShutdownHook,
    OnPlanCreatedHook,
    OnPlanUpdatedHook,
    OnPlanArchivedHook,
    OnSubscriptionCreatedHook,
    OnSubscriptionChangedHook,
    OnSubscriptionCanceledHook,
    OnSubscriptionCancelScheduledHook,
    OnSubscriptionTrialEndedHook,
    OnSubscriptionRenewedHook,
    OnUsageIngestedHook,
    OnUsageFlushedHook,
    OnEntitlementCheckedHook,
    OnQuotaExceededHook,
    OnSoftLimitReachedHook,
    OnInvoiceGeneratedHook,
    OnInvoicePaidHook,
    OnInvoiceVoidedHook,
    OnInvoicePastDueHook,
    PricingStrategy,
    UsageAggregator,
    TaxCalculator,
)


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: Dict[str, Plugin] = {}
        self._pricing_strategies: Dict[str, PricingStrategy] = {}
        self._usage_aggregators: Dict[str, UsageAggregator] = {}
        self._tax_calculators: List[TaxCalculator] = []

    def register(self, p: Plugin) -> None:
        name = p.name()
        self._plugins[name] = p
        if isinstance(p, PricingStrategy):
            self._pricing_strategies[p.strategy_name()] = p
        if isinstance(p, UsageAggregator):
            self._usage_aggregators[p.aggregator_name()] = p
        if isinstance(p, TaxCalculator):
            self._tax_calculators.append(p)
        logger.info(f"Registered plugin: {name}")

    def get_pricing_strategy(self, name: str) -> Optional[PricingStrategy]:
        return self._pricing_strategies.get(name)

    def get_usage_aggregator(self, name: str) -> Optional[UsageAggregator]:
        return self._usage_aggregators.get(name)

    def get_tax_calculators(self) -> List[TaxCalculator]:
        return list(self._tax_calculators)

    # ── Safe Hook Dispatchers ──
    def emit_init(self, ledger: Any) -> None:
        for p in self._plugins.values():
            if isinstance(p, OnInitHook):
                try:
                    p.on_init(ledger)
                except Exception as e:
                    logger.error(f"Plugin {p.name()} on_init error: {e}")

    def emit_plan_created(self, plan: Any) -> None:
        for p in self._plugins.values():
            if isinstance(p, OnPlanCreatedHook):
                try:
                    p.on_plan_created(plan)
                except Exception as e:
                    logger.error(f"Plugin {p.name()} on_plan_created error: {e}")

    def emit_subscription_created(self, sub: Any) -> None:
        for p in self._plugins.values():
            if isinstance(p, OnSubscriptionCreatedHook):
                try:
                    p.on_subscription_created(sub)
                except Exception as e:
                    logger.error(f"Plugin {p.name()} on_subscription_created error: {e}")

    def emit_subscription_canceled(self, sub: Any) -> None:
        for p in self._plugins.values():
            if isinstance(p, OnSubscriptionCanceledHook):
                try:
                    p.on_subscription_canceled(sub)
                except Exception as e:
                    logger.error(f"Plugin {p.name()} on_subscription_canceled error: {e}")

    def emit_subscription_renewed(self, renewal: Any) -> None:
        for p in self._plugins.values():
            if isinstance(p, OnSubscriptionRenewedHook):
                try:
                    p.on_subscription_renewed(renewal)
                except Exception as e:
                    logger.error(f"Plugin {p.name()} on_subscription_renewed error: {e}")

    def emit_usage_flushed(self, count: int, elapsed_ms: float) -> None:
        for p in self._plugins.values():
            if isinstance(p, OnUsageFlushedHook):
                try:
                    p.on_usage_flushed(count, elapsed_ms)
                except Exception as e:
                    logger.error(f"Plugin {p.name()} on_usage_flushed error: {e}")

    def emit_quota_exceeded(self, tenant_id: str, feature_key: str, used: int, limit: int) -> None:
        for p in self._plugins.values():
            if isinstance(p, OnQuotaExceededHook):
                try:
                    p.on_quota_exceeded(tenant_id, feature_key, used, limit)
                except Exception as e:
                    logger.error(f"Plugin {p.name()} on_quota_exceeded error: {e}")

    def emit_invoice_generated(self, inv: Any) -> None:
        for p in self._plugins.values():
            if isinstance(p, OnInvoiceGeneratedHook):
                try:
                    p.on_invoice_generated(inv)
                except Exception as e:
                    logger.error(f"Plugin {p.name()} on_invoice_generated error: {e}")

    def emit_invoice_paid(self, inv: Any) -> None:
        for p in self._plugins.values():
            if isinstance(p, OnInvoicePaidHook):
                try:
                    p.on_invoice_paid(inv)
                except Exception as e:
                    logger.error(f"Plugin {p.name()} on_invoice_paid error: {e}")
