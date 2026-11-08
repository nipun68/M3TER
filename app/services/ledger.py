"""
The Ledger Engine reproducing *ledger.Ledger from ledger.go.
Integrates plans, feature catalog, subscriptions, metering, entitlements,
invoices, coupons, payment providers, and plugins into a unified Python billing engine.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from app.config.logging import logger
from app.core.entity import utc_now
from app.core.exceptions import (
    ErrAlreadyExists,
    ErrCouponInvalid,
    ErrInvalidInput,
    ErrInvalidPricing,
    ErrNotFound,
    ErrPlanArchived,
    ErrPlanNotFound,
    ErrSubscriptionCanceled,
    ErrSubscriptionExpired,
    ErrSubscriptionNotFound,
    ErrUnavailable,
)
from app.core.id import new_id, PREFIX_INVOICE, PREFIX_LINE_ITEM
from app.core.money import Money, zero
from app.models.coupon import Coupon, CouponType
from app.models.entitlement import EntitlementResult
from app.models.feature import CatalogFeature
from app.models.invoice import Invoice, InvoiceStatus, LineItem, LineItemType
from app.models.meter import UsageEvent
from app.models.plan import FeatureType, Period, Plan, PlanFeature, PlanStatus, PriceTier
from app.models.subscription import Resume, Stretch, Subscription, SubscriptionStatus
from app.plugins.registry import PluginRegistry
from app.providers.base import BasePaymentProvider, PaymentMethod, WebhookResult
from app.repositories.base import BaseStore
from app.services.lifecycle import LifecycleEngine, LifecycleReport, next_period
from app.services.metering_buffer import MeteringBuffer
from app.services.pricing_engine import compute_overage, validate_tiers


class Ledger:
    def __init__(
        self,
        store: BaseStore,
        plugins: Optional[PluginRegistry] = None,
        meter_batch_size: int = 100,
        meter_flush_interval_seconds: float = 5.0,
        entitlement_cache_ttl_seconds: float = 30.0,
        clock: Optional[callable] = None,
    ) -> None:
        self.store = store
        self.plugins = plugins or PluginRegistry()
        self.clock = clock or utc_now
        self.entitlement_cache_ttl = entitlement_cache_ttl_seconds

        self.meter_buffer = MeteringBuffer(
            store=self.store,
            plugins=self.plugins,
            batch_size=meter_batch_size,
            flush_interval_seconds=meter_flush_interval_seconds,
        )
        self.lifecycle_engine = LifecycleEngine(store=self.store, plugins=self.plugins)
        self._providers: Dict[str, BasePaymentProvider] = {}

    def now(self) -> datetime:
        return self.clock()

    def register_provider(self, provider: BasePaymentProvider) -> None:
        self._providers[provider.name()] = provider
        logger.info(f"Registered payment provider: {provider.name()}")

    def has_providers(self) -> bool:
        return bool(self._providers)

    def get_provider(self, name: str) -> Optional[BasePaymentProvider]:
        return self._providers.get(name)

    async def start(self) -> None:
        # Initialize plugins
        self.plugins.emit_init(self)
        await self.meter_buffer.start()
        logger.info("Ledger engine started.")

    async def stop(self) -> None:
        await self.meter_buffer.stop()
        logger.info("Ledger engine stopped.")

    # ──────────────────────────────────────────────────
    # Plan Operations
    # ──────────────────────────────────────────────────
    def create_plan(self, plan: Plan) -> Plan:
        self.store.create_plan(plan)
        self.plugins.emit_plan_created(plan)
        return plan

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        return self.store.get_plan(plan_id)

    def get_plan_by_slug(self, slug: str, app_id: str = "default") -> Optional[Plan]:
        return self.store.get_plan_by_slug(slug, app_id)

    def list_plans(self, app_id: str = "default", status: Optional[str] = None) -> List[Plan]:
        return self.store.list_plans(app_id, status)

    def update_plan(self, plan: Plan) -> Plan:
        self.store.update_plan(plan)
        return plan

    def archive_plan(self, plan_id: str) -> None:
        self.store.archive_plan(plan_id)

    def activate_plan(self, plan_id: str) -> Plan:
        p = self.store.get_plan(plan_id)
        if not p:
            raise ErrPlanNotFound(f"plan {plan_id} not found")
        p.status = PlanStatus.ACTIVE
        self.store.update_plan(p)
        return p

    def delete_plan(self, plan_id: str) -> None:
        self.store.delete_plan(plan_id)

    # ──────────────────────────────────────────────────
    # Feature Catalog Operations
    # ──────────────────────────────────────────────────
    def create_feature(self, feature: CatalogFeature) -> CatalogFeature:
        self.store.create_feature(feature)
        return feature

    def get_feature(self, feature_id: str) -> Optional[CatalogFeature]:
        return self.store.get_feature(feature_id)

    def get_feature_by_key(self, key: str, app_id: str = "default") -> Optional[CatalogFeature]:
        return self.store.get_feature_by_key(key, app_id)

    def list_features(self, app_id: str = "default") -> List[CatalogFeature]:
        return self.store.list_features(app_id)

    def update_feature(self, feature: CatalogFeature) -> CatalogFeature:
        self.store.update_feature(feature)
        return feature

    def delete_feature(self, feature_id: str) -> None:
        self.store.delete_feature(feature_id)

    def archive_feature(self, feature_id: str) -> None:
        self.store.archive_feature(feature_id)

    # ──────────────────────────────────────────────────
    # Subscription Management
    # ──────────────────────────────────────────────────
    def create_subscription(
        self,
        tenant_id: str,
        plan_id: str,
        app_id: str = "default",
        quantity: Optional[Dict[str, int]] = None,
        trial_days: Optional[int] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Subscription:
        p = self.store.get_plan(plan_id)
        if not p:
            raise ErrPlanNotFound(f"plan {plan_id} not found")
        if p.status == PlanStatus.ARCHIVED:
            raise ErrPlanArchived(f"plan {plan_id} is archived")

        now = self.now()
        t_days = p.trial_days if trial_days is None else trial_days
        status = SubscriptionStatus.TRIALING if t_days > 0 else SubscriptionStatus.ACTIVE

        # Calculate period end
        b_period = p.pricing.billing_period if p.pricing else Period.MONTHLY
        _, period_end = next_period(now, now, b_period)

        trial_start = now if t_days > 0 else None
        trial_end = now + timedelta(days=t_days) if t_days > 0 else None

        sub = Subscription(
            tenant_id=tenant_id,
            plan_id=plan_id,
            status=status,
            current_period_start=now,
            current_period_end=period_end,
            trial_start=trial_start,
            trial_end=trial_end,
            app_id=app_id,
            metadata=metadata or {},
            quantity=quantity or {},
            created_at=now,
            updated_at=now,
        )
        self.store.create_subscription(sub)
        self.plugins.emit_subscription_created(sub)
        return sub

    def get_subscription(self, sub_id: str) -> Optional[Subscription]:
        return self.store.get_subscription(sub_id)

    def get_active_subscription(self, tenant_id: str, app_id: str = "default") -> Optional[Subscription]:
        return self.store.get_active_subscription(tenant_id, app_id)

    def list_subscriptions(self, tenant_id: Optional[str] = None, app_id: str = "default") -> List[Subscription]:
        return self.store.list_subscriptions(tenant_id, app_id)

    def cancel_subscription(self, sub_id: str, immediately: bool = False) -> Subscription:
        now = self.now()
        self.store.cancel_subscription(sub_id, immediately=immediately, now=now)
        sub = self.store.get_subscription(sub_id)
        if sub and immediately:
            self.plugins.emit_subscription_canceled(sub)
        return sub

    def change_plan(self, sub_id: str, new_plan_id: str, quantity: Optional[Dict[str, int]] = None) -> Subscription:
        p = self.store.get_plan(new_plan_id)
        if not p:
            raise ErrPlanNotFound(f"plan {new_plan_id} not found")
        if p.status == PlanStatus.ARCHIVED:
            raise ErrPlanArchived(f"plan {new_plan_id} is archived")

        sub = self.store.get_subscription(sub_id)
        if not sub:
            raise ErrSubscriptionNotFound(f"subscription {sub_id} not found")
        if sub.status in (SubscriptionStatus.CANCELED, SubscriptionStatus.EXPIRED):
            raise ErrSubscriptionCanceled(f"cannot change plan for {sub.status} subscription")

        qty = sub.quantity if quantity is None else quantity
        self.store.change_subscription_plan(sub_id, new_plan_id, qty)
        # Invalidate cached entitlements on plan change
        self.store.invalidate_entitlements(sub.tenant_id, sub.app_id)
        return self.store.get_subscription(sub_id)

    def pause_subscription(self, sub_id: str) -> Subscription:
        now = self.now()
        ok = self.store.pause_subscription(sub_id, at=now)
        if not ok:
            sub = self.store.get_subscription(sub_id)
            if not sub:
                raise ErrSubscriptionNotFound(f"subscription {sub_id} not found")
            raise ErrInvalidInput(f"cannot pause subscription in {sub.status} status")
        return self.store.get_subscription(sub_id)

    def resume_subscription(self, sub_id: str) -> Subscription:
        sub = self.store.get_subscription(sub_id)
        if not sub:
            raise ErrSubscriptionNotFound(f"subscription {sub_id} not found")
        if sub.status != SubscriptionStatus.PAUSED:
            raise ErrInvalidInput(f"subscription {sub_id} is not paused")

        now = self.now()
        paused_at = sub.paused_at or sub.updated_at
        pause_duration = now - paused_at

        # Move period end forward by pause duration
        new_period_end = sub.current_period_end + pause_duration
        new_trial_end = sub.trial_end + pause_duration if sub.trial_end else None

        # Check if trial is still running
        new_status = SubscriptionStatus.TRIALING if (new_trial_end and now < new_trial_end) else SubscriptionStatus.ACTIVE

        stretch = Stretch(
            start=sub.current_period_start,
            end=new_period_end,
            original_end=sub.current_period_end,
            floor=sub.stretch.floor if sub.stretch else None,
        )

        r = Resume(
            paused_at=sub.paused_at,
            status=new_status,
            period_end=new_period_end,
            trial_end=new_trial_end,
            stretch=stretch,
        )
        self.store.resume_subscription(sub_id, r)
        return self.store.get_subscription(sub_id)

    # ──────────────────────────────────────────────────
    # Usage Metering
    # ──────────────────────────────────────────────────
    def meter(self, tenant_id: str, feature_key: str, quantity: int = 1, app_id: str = "default") -> None:
        event = UsageEvent(
            tenant_id=tenant_id,
            app_id=app_id,
            feature_key=feature_key,
            quantity=quantity,
            timestamp=self.now(),
        )
        self.meter_buffer.enqueue_sync(event)
        # Invalidate cached entitlement for this feature
        self.store.invalidate_feature_entitlement(tenant_id, app_id, feature_key)

    def meter_with_key(self, tenant_id: str, feature_key: str, idempotency_key: str, quantity: int = 1, app_id: str = "default") -> None:
        event = UsageEvent(
            tenant_id=tenant_id,
            app_id=app_id,
            feature_key=feature_key,
            quantity=quantity,
            timestamp=self.now(),
            idempotency_key=idempotency_key,
        )
        self.meter_buffer.enqueue_sync(event)
        self.store.invalidate_feature_entitlement(tenant_id, app_id, feature_key)

    # ──────────────────────────────────────────────────
    # Entitlements & Quotas
    # ──────────────────────────────────────────────────
    def entitled(self, tenant_id: str, feature_key: str, app_id: str = "default") -> EntitlementResult:
        res, _ = self._check_entitlement(tenant_id, feature_key, app_id=app_id, strict=False)
        return res

    def check(self, tenant_id: str, feature_key: str, app_id: str = "default", strict: bool = True) -> EntitlementResult:
        res, _ = self._check_entitlement(tenant_id, feature_key, app_id=app_id, strict=strict)
        return res

    def remaining(self, tenant_id: str, feature_key: str, app_id: str = "default") -> int:
        res = self.entitled(tenant_id, feature_key, app_id)
        return res.remaining

    def _check_entitlement(self, tenant_id: str, feature_key: str, app_id: str, strict: bool) -> Tuple[EntitlementResult, str]:
        # 1. Check cache
        cached = self.store.get_cached_entitlement(tenant_id, app_id, feature_key)
        if cached:
            return cached, "cached"

        # 2. Lookup active subscription
        sub = self.store.get_active_subscription(tenant_id, app_id)
        if not sub:
            res = EntitlementResult(allowed=False, feature=feature_key, reason="no active subscription")
            return res, "no_access"

        # 3. Lookup plan
        p = self.store.get_plan(sub.plan_id)
        if not p:
            res = EntitlementResult(allowed=False, feature=feature_key, reason="plan not found")
            return res, "no_access"

        # 4. Lookup feature in plan
        feat = p.find_feature(feature_key)
        if not feat:
            res = EntitlementResult(allowed=False, feature=feature_key, reason="feature not in plan")
            return res, "no_access"

        # Boolean feature
        if feat.type == FeatureType.BOOLEAN:
            allowed = feat.limit > 0
            res = EntitlementResult(allowed=allowed, feature=feature_key, limit=feat.limit)
            self.store.set_cached_entitlement(tenant_id, app_id, feature_key, res, self.entitlement_cache_ttl)
            return res, "boolean"

        # Metered feature
        used = self.store.aggregate(
            tenant_id=tenant_id,
            app_id=app_id,
            feature_key=feature_key,
            period=feat.period,
            start=sub.current_period_start,
            end=sub.current_period_end,
        )
        remaining_quota = max(0, feat.limit - used) if feat.limit >= 0 else -1

        if feat.limit == -1:
            res = EntitlementResult(allowed=True, feature=feature_key, used=used, limit=-1, remaining=-1)
        elif used < feat.limit:
            res = EntitlementResult(allowed=True, feature=feature_key, used=used, limit=feat.limit, remaining=remaining_quota)
        elif feat.soft_limit:
            res = EntitlementResult(allowed=True, feature=feature_key, used=used, limit=feat.limit, remaining=0, soft_limit=True, reason="over soft limit")
        else:
            res = EntitlementResult(allowed=False, feature=feature_key, used=used, limit=feat.limit, remaining=0, reason="quota exceeded")
            self.plugins.emit_quota_exceeded(tenant_id, feature_key, used, feat.limit)

        self.store.set_cached_entitlement(tenant_id, app_id, feature_key, res, self.entitlement_cache_ttl)
        return res, "metered"

    # ──────────────────────────────────────────────────
    # Invoicing
    # ──────────────────────────────────────────────────
    def generate_invoice(
        self,
        sub_id: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> Invoice:
        sub = self.store.get_subscription(sub_id)
        if not sub:
            raise ErrSubscriptionNotFound(f"subscription {sub_id} not found")

        p = self.store.get_plan(sub.plan_id)
        if not p:
            raise ErrPlanNotFound(f"plan {sub.plan_id} not found")

        p_start = period_start or sub.current_period_start
        p_end = period_end or sub.current_period_end

        # Check existing live invoice for period
        existing = self.store.get_invoice_by_period(sub.tenant_id, sub.app_id, p_start, p_end)
        if existing and existing.status != InvoiceStatus.VOIDED:
            raise ErrAlreadyExists(f"invoice {existing.id} already covers period {p_start} to {p_end}")

        currency = p.currency.lower()
        inv = Invoice(
            tenant_id=sub.tenant_id,
            subscription_id=sub.id,
            status=InvoiceStatus.DRAFT,
            currency=currency,
            subtotal=zero(currency),
            tax_amount=zero(currency),
            discount_amount=zero(currency),
            credit_amount=zero(currency),
            total=zero(currency),
            period_start=p_start,
            period_end=p_end,
            app_id=sub.app_id,
            line_items=[],
        )

        # 1. Base Subscription Fee
        if p.pricing and p.pricing.base_amount.is_positive():
            base = Money(p.pricing.base_amount.amount, currency)
            inv.line_items.append(LineItem(
                invoice_id=inv.id,
                description="Base subscription fee",
                quantity=1,
                unit_amount=base,
                amount=base,
                type=LineItemType.BASE,
            ))
            inv.subtotal = inv.subtotal.checked_add(base)

        # 2. Metered Usage Overages
        tiers = p.pricing.tiers if p.pricing else []
        for feat in p.features:
            if feat.type != FeatureType.METERED or feat.limit < 0:
                continue

            feat_tiers = [t for t in tiers if t.feature_key == feat.key]
            validate_tiers(feat_tiers, currency)

            # Usage aggregation
            used = self.store.aggregate(
                tenant_id=sub.tenant_id,
                app_id=sub.app_id,
                feature_key=feat.key,
                period=feat.period,
                start=p_start,
                end=p_end,
            )
            billable = used - feat.limit
            if billable <= 0:
                continue

            # Check pricing strategy plugin
            strat_name = feat.metadata.get("pricing_strategy") or (p.metadata.get("pricing_strategy") if p.metadata else None)
            strat = self.plugins.get_pricing_strategy(strat_name) if strat_name else None

            if strat:
                amount = strat.compute(feat_tiers, used, feat.limit, currency)
            else:
                amount = compute_overage(feat_tiers, used, feat.limit, currency)

            if amount.is_positive():
                inv.line_items.append(LineItem(
                    invoice_id=inv.id,
                    feature_key=feat.key,
                    description=f"{feat.name} overage",
                    quantity=billable,
                    unit_amount=zero(currency),
                    amount=amount,
                    type=LineItemType.OVERAGE,
                ))
                inv.subtotal = inv.subtotal.checked_add(amount)

        # 3. Seat Charges
        for feat in p.features:
            if feat.type != FeatureType.SEAT:
                continue
            seats = sub.quantity.get(feat.key, 0)
            if seats <= 0:
                continue

            feat_tiers = [t for t in tiers if t.feature_key == feat.key]
            validate_tiers(feat_tiers, currency)
            amount = compute_overage(feat_tiers, seats, 0, currency)
            if amount.is_positive():
                inv.line_items.append(LineItem(
                    invoice_id=inv.id,
                    feature_key=feat.key,
                    description=feat.name,
                    quantity=seats,
                    unit_amount=zero(currency),
                    amount=amount,
                    type=LineItemType.SEAT,
                ))
                inv.subtotal = inv.subtotal.checked_add(amount)

        # 4. Plan Credit Pools
        credit_total = zero(currency)
        for pool in p.credits:
            pool_cap = Money(pool.amount.amount, currency)
            pool_usage = zero(currency)
            for li in inv.line_items:
                if li.type == LineItemType.OVERAGE and li.feature_key in pool.feature_keys:
                    pool_usage = pool_usage.checked_add(li.amount)

            applied_credit = pool_cap.min(pool_usage)
            if applied_credit.is_positive():
                inv.line_items.append(LineItem(
                    invoice_id=inv.id,
                    description=f"Usage credit ({pool.key})",
                    quantity=1,
                    unit_amount=applied_credit.negate(),
                    amount=applied_credit.negate(),
                    type=LineItemType.CREDIT,
                ))
                credit_total = credit_total.checked_add(applied_credit)

        inv.credit_amount = credit_total

        # 5. Coupons & Discounts
        discount_base = inv.subtotal.checked_subtract(inv.credit_amount)
        discount_total = zero(currency)
        applied_coupons = self.store.list_applied_coupons(sub.id)

        for c in applied_coupons:
            if c.type == CouponType.PERCENTAGE:
                if c.percentage < 0 or c.percentage > 100:
                    raise ErrCouponInvalid(f"coupon {c.code} percentage out of range")
                c_amount = discount_base.checked_percent(c.percentage)
            elif c.type == CouponType.AMOUNT:
                if c.amount.amount < 0:
                    raise ErrCouponInvalid(f"coupon {c.code} has negative amount")
                c_amount = Money(c.amount.amount, currency)
            else:
                continue

            if c_amount.is_positive():
                inv.line_items.append(LineItem(
                    invoice_id=inv.id,
                    description=f"Discount {c.code}",
                    quantity=1,
                    unit_amount=c_amount.negate(),
                    amount=c_amount.negate(),
                    type=LineItemType.DISCOUNT,
                ))
                discount_total = discount_total.checked_add(c_amount)

        inv.discount_amount = discount_total

        # Clamped Net Amount
        net = discount_base.checked_subtract(discount_total)
        if net.is_negative():
            net = zero(currency)

        # 6. Tax Calculation
        tax_total = zero(currency)
        for tc in self.plugins.get_tax_calculators():
            tax_val = tc.calculate_tax(net, sub.tenant_id)
            if tax_val and tax_val.is_positive():
                tax_total = tax_total.checked_add(Money(tax_val.amount, currency))

        inv.tax_amount = tax_total
        if tax_total.is_positive():
            inv.line_items.append(LineItem(
                invoice_id=inv.id,
                description="Tax",
                quantity=1,
                unit_amount=tax_total,
                amount=tax_total,
                type=LineItemType.TAX,
            ))

        # Total = Net + Tax
        inv.total = net.checked_add(tax_total)

        # Save invoice
        self.store.create_invoice(inv)
        self.plugins.emit_invoice_generated(inv)
        return inv

    def finalize_invoice(self, inv_id: str) -> Invoice:
        inv = self.store.get_invoice(inv_id)
        if not inv:
            raise ErrNotFound(f"invoice {inv_id} not found")
        inv.status = InvoiceStatus.PENDING
        inv.due_date = self.now() + timedelta(days=30)
        self.store.update_invoice(inv)
        return inv

    def mark_invoice_paid(self, inv_id: str, payment_ref: str = "") -> Invoice:
        inv = self.store.get_invoice(inv_id)
        if not inv:
            raise ErrNotFound(f"invoice {inv_id} not found")
        paid_at = self.now()
        self.store.mark_invoice_paid(inv_id, paid_at, payment_ref)
        inv.status = InvoiceStatus.PAID
        inv.paid_at = paid_at
        inv.payment_ref = payment_ref
        self.plugins.emit_invoice_paid(inv)
        return inv

    def mark_invoice_voided(self, inv_id: str, reason: str = "") -> Invoice:
        self.store.mark_invoice_voided(inv_id, reason)
        inv = self.store.get_invoice(inv_id)
        return inv

    # ──────────────────────────────────────────────────
    # Coupons
    # ──────────────────────────────────────────────────
    def create_coupon(self, coupon: Coupon) -> Coupon:
        self.store.create_coupon(coupon)
        return coupon

    def apply_coupon(self, sub_id: str, coupon_code: str, app_id: str = "default") -> None:
        c = self.store.get_coupon(coupon_code, app_id)
        if not c:
            raise ErrNotFound(f"coupon {coupon_code} not found")
        if not c.is_valid(self.now()):
            raise ErrCouponInvalid(f"coupon {coupon_code} is expired or depleted")
        self.store.redeem_coupon(sub_id, c.id)

    def list_applied_coupons(self, sub_id: str) -> List[Coupon]:
        return self.store.list_applied_coupons(sub_id)
