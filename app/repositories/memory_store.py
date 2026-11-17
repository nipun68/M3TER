"""
In-memory store implementation satisfying BaseStore.
Thread-safe, zero external dependencies, perfect for testing and isolated runtime.
"""
from __future__ import annotations
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import copy
from app.core.entity import utc_now
from app.core.exceptions import (
    ErrAlreadyExists,
    ErrNotFound,
    ErrPlanNotFound,
    ErrFeatureNotFound,
    ErrSubscriptionNotFound,
    ErrSubscriptionCanceled,
    ErrSubscriptionExpired,
    ErrCouponNotFound,
    ErrCouponDepleted,
    ErrInvoiceNotFound,
)
from app.models.plan import Plan, PlanStatus, Period
from app.models.feature import CatalogFeature
from app.models.subscription import Subscription, SubscriptionStatus, Resume
from app.models.meter import UsageEvent
from app.models.entitlement import EntitlementResult
from app.models.invoice import Invoice, InvoiceStatus
from app.models.coupon import Coupon, CouponApplication
from app.models.user import User
from app.repositories.base import BaseStore


class MemoryStore(BaseStore):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.plans: Dict[str, Plan] = {}
        self.features: Dict[str, CatalogFeature] = {}
        self.subscriptions: Dict[str, Subscription] = {}
        self.usage_events: List[UsageEvent] = []
        self.idempotency_keys: set[str] = set()
        self.entitlement_cache: Dict[str, tuple[EntitlementResult, datetime]] = {}
        self.invoices: Dict[str, Invoice] = {}
        self.coupons: Dict[str, Coupon] = {}
        self.coupon_applications: List[CouponApplication] = []
        self.users: Dict[str, User] = {}

    # ── Plan methods ──
    def create_plan(self, p: Plan) -> None:
        with self._lock:
            # Check unique slug within app_id
            for existing in self.plans.values():
                if existing.slug == p.slug and existing.app_id == p.app_id:
                    raise ErrAlreadyExists(f"plan with slug {p.slug!r} already exists in app {p.app_id!r}")
            self.plans[p.id] = copy.deepcopy(p)

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        with self._lock:
            p = self.plans.get(plan_id)
            return copy.deepcopy(p) if p else None

    def get_plan_by_slug(self, slug: str, app_id: str = "default") -> Optional[Plan]:
        with self._lock:
            for p in self.plans.values():
                if p.slug == slug and p.app_id == app_id:
                    return copy.deepcopy(p)
            return None

    def list_plans(self, app_id: str = "default", status: Optional[str] = None) -> List[Plan]:
        with self._lock:
            res = []
            for p in self.plans.values():
                if p.app_id == app_id:
                    if status is None or p.status.value == status or str(p.status) == status:
                        res.append(copy.deepcopy(p))
            res.sort(key=lambda x: x.created_at)
            return res

    def update_plan(self, p: Plan) -> None:
        with self._lock:
            if p.id not in self.plans:
                raise ErrPlanNotFound(f"plan {p.id} not found")
            p.touch()
            self.plans[p.id] = copy.deepcopy(p)

    def delete_plan(self, plan_id: str) -> None:
        with self._lock:
            if plan_id not in self.plans:
                raise ErrPlanNotFound(f"plan {plan_id} not found")
            del self.plans[plan_id]

    def archive_plan(self, plan_id: str) -> None:
        with self._lock:
            if plan_id not in self.plans:
                raise ErrPlanNotFound(f"plan {plan_id} not found")
            self.plans[plan_id].status = PlanStatus.ARCHIVED
            self.plans[plan_id].touch()

    # ── Feature catalog methods ──
    def create_feature(self, f: CatalogFeature) -> None:
        with self._lock:
            for existing in self.features.values():
                if existing.key == f.key and existing.app_id == f.app_id:
                    raise ErrAlreadyExists(f"feature with key {f.key!r} already exists in app {f.app_id!r}")
            self.features[f.id] = copy.deepcopy(f)

    def get_feature(self, feature_id: str) -> Optional[CatalogFeature]:
        with self._lock:
            f = self.features.get(feature_id)
            return copy.deepcopy(f) if f else None

    def get_feature_by_key(self, key: str, app_id: str = "default") -> Optional[CatalogFeature]:
        with self._lock:
            for f in self.features.values():
                if f.key == key and (f.app_id == app_id or f.is_global):
                    return copy.deepcopy(f)
            return None

    def list_features(self, app_id: str = "default") -> List[CatalogFeature]:
        with self._lock:
            res = [copy.deepcopy(f) for f in self.features.values() if f.app_id == app_id or f.is_global]
            res.sort(key=lambda x: x.created_at)
            return res

    def list_global_features(self) -> List[CatalogFeature]:
        with self._lock:
            res = [copy.deepcopy(f) for f in self.features.values() if f.is_global]
            res.sort(key=lambda x: x.created_at)
            return res

    def update_feature(self, f: CatalogFeature) -> None:
        with self._lock:
            if f.id not in self.features:
                raise ErrFeatureNotFound(f"feature {f.id} not found")
            f.touch()
            self.features[f.id] = copy.deepcopy(f)

    def delete_feature(self, feature_id: str) -> None:
        with self._lock:
            if feature_id not in self.features:
                raise ErrFeatureNotFound(f"feature {feature_id} not found")
            del self.features[feature_id]

    def archive_feature(self, feature_id: str) -> None:
        with self._lock:
            if feature_id not in self.features:
                raise ErrFeatureNotFound(f"feature {feature_id} not found")
            self.features[feature_id].status = "archived"
            self.features[feature_id].touch()

    # ── Subscription methods ──
    def create_subscription(self, s: Subscription) -> None:
        with self._lock:
            self.subscriptions[s.id] = copy.deepcopy(s)

    def get_subscription(self, sub_id: str) -> Optional[Subscription]:
        with self._lock:
            s = self.subscriptions.get(sub_id)
            return copy.deepcopy(s) if s else None

    def get_active_subscription(self, tenant_id: str, app_id: str = "default") -> Optional[Subscription]:
        with self._lock:
            # Matches active or trialing
            for s in self.subscriptions.values():
                if s.tenant_id == tenant_id and s.app_id == app_id and s.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING):
                    return copy.deepcopy(s)
            return None

    def list_subscriptions(self, tenant_id: Optional[str] = None, app_id: str = "default") -> List[Subscription]:
        with self._lock:
            res = []
            for s in self.subscriptions.values():
                if (tenant_id is None or s.tenant_id == tenant_id) and s.app_id == app_id:
                    res.append(copy.deepcopy(s))
            res.sort(key=lambda x: x.created_at, reverse=True)
            return res

    def update_subscription(self, s: Subscription) -> None:
        with self._lock:
            if s.id not in self.subscriptions:
                raise ErrSubscriptionNotFound(f"subscription {s.id} not found")
            s.touch()
            self.subscriptions[s.id] = copy.deepcopy(s)

    def cancel_subscription(self, sub_id: str, immediately: bool, now: Optional[datetime] = None) -> datetime:
        with self._lock:
            s = self.subscriptions.get(sub_id)
            if not s:
                raise ErrSubscriptionNotFound(f"subscription {sub_id} not found")
            if s.status == SubscriptionStatus.CANCELED:
                raise ErrSubscriptionCanceled(f"subscription {sub_id} is already canceled")
            if s.status == SubscriptionStatus.EXPIRED:
                raise ErrSubscriptionExpired(f"subscription {sub_id} is expired")

            n = now or utc_now()
            if immediately:
                s.canceled_at = n
                s.cancel_at = n
                s.ended_at = n
                s.status = SubscriptionStatus.CANCELED
                s.touch()
                return n
            else:
                s.cancel_at = s.current_period_end
                s.touch()
                return s.current_period_end

    def pause_subscription(self, sub_id: str, at: datetime) -> bool:
        with self._lock:
            s = self.subscriptions.get(sub_id)
            if not s or s.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING):
                return False
            s.status = SubscriptionStatus.PAUSED
            s.paused_at = at
            s.touch()
            return True

    def resume_subscription(self, sub_id: str, r: Resume) -> bool:
        with self._lock:
            s = self.subscriptions.get(sub_id)
            if not s or s.status != SubscriptionStatus.PAUSED:
                return False
            # Check paused_at precondition
            if r.paused_at is not None and s.paused_at != r.paused_at:
                return False

            s.status = r.status
            if r.period_end:
                if s.cancel_at == s.current_period_end:
                    s.cancel_at = r.period_end
                s.current_period_end = r.period_end
            if r.trial_end:
                s.trial_end = r.trial_end
            if r.stretch:
                s.stretch = r.stretch
            s.paused_at = None
            s.touch()
            return True

    def change_subscription_plan(self, sub_id: str, plan_id: str, quantity: Dict[str, int]) -> bool:
        with self._lock:
            s = self.subscriptions.get(sub_id)
            if not s or s.status in (SubscriptionStatus.CANCELED, SubscriptionStatus.EXPIRED):
                return False
            s.plan_id = plan_id
            s.quantity = dict(quantity or {})
            s.touch()
            return True

    def set_subscription_provider(self, sub_id: str, provider_id: str, provider_name: str) -> None:
        with self._lock:
            s = self.subscriptions.get(sub_id)
            if not s:
                raise ErrSubscriptionNotFound(f"subscription {sub_id} not found")
            s.provider_id = provider_id
            s.provider_name = provider_name
            s.touch()

    # ── Meter methods ──
    def ingest_batch(self, events: List[UsageEvent]) -> None:
        with self._lock:
            for e in events:
                if e.idempotency_key:
                    if e.idempotency_key in self.idempotency_keys:
                        continue  # deduplicate idempotent event
                    self.idempotency_keys.add(e.idempotency_key)
                self.usage_events.append(copy.deepcopy(e))

    def aggregate(self, tenant_id: str, app_id: str, feature_key: str, period: Period, start: Optional[datetime] = None, end: Optional[datetime] = None) -> int:
        with self._lock:
            total = 0
            for e in self.usage_events:
                if e.tenant_id == tenant_id and e.app_id == app_id and e.feature_key == feature_key:
                    if start and e.timestamp < start:
                        continue
                    if end and e.timestamp >= end:
                        continue
                    total += e.quantity
            return total

    def query_usage(self, tenant_id: str, app_id: str, feature_key: Optional[str] = None, start: Optional[datetime] = None, end: Optional[datetime] = None) -> List[UsageEvent]:
        with self._lock:
            res = []
            for e in self.usage_events:
                if e.tenant_id == tenant_id and e.app_id == app_id:
                    if feature_key and e.feature_key != feature_key:
                        continue
                    if start and e.timestamp < start:
                        continue
                    if end and e.timestamp >= end:
                        continue
                    res.append(copy.deepcopy(e))
            return res

    def purge_usage(self, before: datetime) -> int:
        with self._lock:
            orig = len(self.usage_events)
            self.usage_events = [e for e in self.usage_events if e.timestamp >= before]
            return orig - len(self.usage_events)

    # ── Entitlement cache methods ──
    def get_cached_entitlement(self, tenant_id: str, app_id: str, feature_key: str) -> Optional[EntitlementResult]:
        with self._lock:
            key = f"{tenant_id}:{app_id}:{feature_key}"
            entry = self.entitlement_cache.get(key)
            if not entry:
                return None
            res, expires_at = entry
            if utc_now() > expires_at:
                del self.entitlement_cache[key]
                return None
            return copy.deepcopy(res)

    def set_cached_entitlement(self, tenant_id: str, app_id: str, feature_key: str, result: EntitlementResult, ttl_seconds: float) -> None:
        with self._lock:
            key = f"{tenant_id}:{app_id}:{feature_key}"
            expires = utc_now() + timedelta(seconds=ttl_seconds)
            self.entitlement_cache[key] = (copy.deepcopy(result), expires)

    def invalidate_entitlements(self, tenant_id: str, app_id: str) -> None:
        with self._lock:
            prefix = f"{tenant_id}:{app_id}:"
            to_del = [k for k in self.entitlement_cache if k.startswith(prefix)]
            for k in to_del:
                del self.entitlement_cache[k]

    def invalidate_feature_entitlement(self, tenant_id: str, app_id: str, feature_key: str) -> None:
        with self._lock:
            key = f"{tenant_id}:{app_id}:{feature_key}"
            self.entitlement_cache.pop(key, None)

    # ── Invoice methods ──
    def create_invoice(self, inv: Invoice) -> None:
        with self._lock:
            self.invoices[inv.id] = copy.deepcopy(inv)

    def get_invoice(self, inv_id: str) -> Optional[Invoice]:
        with self._lock:
            inv = self.invoices.get(inv_id)
            return copy.deepcopy(inv) if inv else None

    def list_invoices(self, tenant_id: Optional[str] = None, app_id: str = "default") -> List[Invoice]:
        with self._lock:
            res = []
            for inv in self.invoices.values():
                if (tenant_id is None or inv.tenant_id == tenant_id) and inv.app_id == app_id:
                    res.append(copy.deepcopy(inv))
            res.sort(key=lambda x: x.created_at, reverse=True)
            return res

    def update_invoice(self, inv: Invoice) -> None:
        with self._lock:
            if inv.id not in self.invoices:
                raise ErrInvoiceNotFound(f"invoice {inv.id} not found")
            inv.touch()
            self.invoices[inv.id] = copy.deepcopy(inv)

    def get_invoice_by_period(self, tenant_id: str, app_id: str, period_start: datetime, period_end: datetime) -> Optional[Invoice]:
        with self._lock:
            for inv in self.invoices.values():
                if inv.tenant_id == tenant_id and inv.app_id == app_id:
                    if inv.period_start == period_start and inv.period_end == period_end:
                        if inv.status != InvoiceStatus.VOIDED:
                            return copy.deepcopy(inv)
            return None

    def list_pending_invoices(self, app_id: str = "default") -> List[Invoice]:
        with self._lock:
            res = [copy.deepcopy(inv) for inv in self.invoices.values() if inv.app_id == app_id and inv.status == InvoiceStatus.PENDING]
            res.sort(key=lambda x: x.created_at)
            return res

    def mark_invoice_paid(self, inv_id: str, paid_at: datetime, payment_ref: str) -> None:
        with self._lock:
            inv = self.invoices.get(inv_id)
            if not inv:
                raise ErrInvoiceNotFound(f"invoice {inv_id} not found")
            inv.status = InvoiceStatus.PAID
            inv.paid_at = paid_at
            inv.payment_ref = payment_ref
            inv.touch()

    def mark_invoice_voided(self, inv_id: str, reason: str) -> None:
        with self._lock:
            inv = self.invoices.get(inv_id)
            if not inv:
                raise ErrInvoiceNotFound(f"invoice {inv_id} not found")
            inv.status = InvoiceStatus.VOIDED
            inv.voided_at = utc_now()
            inv.void_reason = reason
            inv.touch()

    def set_invoice_provider(self, inv_id: str, provider_id: str, provider_name: str) -> None:
        with self._lock:
            inv = self.invoices.get(inv_id)
            if not inv:
                raise ErrInvoiceNotFound(f"invoice {inv_id} not found")
            inv.provider_id = provider_id
            inv.provider_name = provider_name
            inv.touch()

    # ── Coupon methods ──
    def create_coupon(self, c: Coupon) -> None:
        with self._lock:
            for existing in self.coupons.values():
                if existing.code == c.code and existing.app_id == c.app_id:
                    raise ErrAlreadyExists(f"coupon {c.code} already exists in app {c.app_id}")
            self.coupons[c.id] = copy.deepcopy(c)

    def get_coupon(self, code: str, app_id: str = "default") -> Optional[Coupon]:
        with self._lock:
            code_clean = code.strip().upper()
            for c in self.coupons.values():
                if c.code == code_clean and c.app_id == app_id:
                    return copy.deepcopy(c)
            return None

    def get_coupon_by_id(self, coupon_id: str) -> Optional[Coupon]:
        with self._lock:
            c = self.coupons.get(coupon_id)
            return copy.deepcopy(c) if c else None

    def list_coupons(self, app_id: str = "default") -> List[Coupon]:
        with self._lock:
            res = [copy.deepcopy(c) for c in self.coupons.values() if c.app_id == app_id]
            res.sort(key=lambda x: x.created_at, reverse=True)
            return res

    def update_coupon(self, c: Coupon) -> None:
        with self._lock:
            if c.id not in self.coupons:
                raise ErrCouponNotFound(f"coupon {c.id} not found")
            c.touch()
            self.coupons[c.id] = copy.deepcopy(c)

    def delete_coupon(self, coupon_id: str) -> None:
        with self._lock:
            if coupon_id not in self.coupons:
                raise ErrCouponNotFound(f"coupon {coupon_id} not found")
            del self.coupons[coupon_id]

    def apply_coupon(self, sub_id: str, coupon_id: str) -> None:
        with self._lock:
            for app in self.coupon_applications:
                if app.subscription_id == sub_id and app.coupon_id == coupon_id:
                    return  # Already applied
            self.coupon_applications.append(CouponApplication(coupon_id=coupon_id, subscription_id=sub_id))

    def list_applied_coupons(self, sub_id: str) -> List[Coupon]:
        with self._lock:
            res = []
            for app in self.coupon_applications:
                if app.subscription_id == sub_id:
                    c = self.coupons.get(app.coupon_id)
                    if c:
                        res.append(copy.deepcopy(c))
            return res

    def increment_coupon_redemptions(self, coupon_id: str) -> None:
        with self._lock:
            c = self.coupons.get(coupon_id)
            if not c:
                raise ErrCouponNotFound(f"coupon {coupon_id} not found")
            c.times_redeemed += 1
            c.touch()

    def redeem_coupon(self, sub_id: str, coupon_id: str) -> None:
        with self._lock:
            c = self.coupons.get(coupon_id)
            if not c:
                raise ErrCouponNotFound(f"coupon {coupon_id} not found")
            if c.max_redemptions > 0 and c.times_redeemed >= c.max_redemptions:
                raise ErrCouponDepleted(f"coupon {c.code} max redemptions reached")
            self.apply_coupon(sub_id, coupon_id)
            c.times_redeemed += 1
            c.touch()

    # ── Lifecycle clock methods ──
    def list_due_subscriptions(self, due_before: datetime, statuses: List[str]) -> List[Subscription]:
        with self._lock:
            res = []
            for s in self.subscriptions.values():
                st_val = s.status.value if isinstance(s.status, SubscriptionStatus) else str(s.status)
                if st_val in statuses and s.current_period_end <= due_before:
                    res.append(copy.deepcopy(s))
            return res

    def list_overdue_invoices(self, now: datetime) -> List[Invoice]:
        with self._lock:
            res = []
            for inv in self.invoices.values():
                if inv.status == InvoiceStatus.PENDING and inv.due_date and inv.due_date < now:
                    res.append(copy.deepcopy(inv))
            return res

    def end_subscription_trial(self, sub_id: str, now: datetime) -> bool:
        with self._lock:
            s = self.subscriptions.get(sub_id)
            if not s or s.status != SubscriptionStatus.TRIALING:
                return False
            if s.trial_end and s.trial_end <= now:
                s.status = SubscriptionStatus.ACTIVE
                s.touch()
                return True
            return False

    def enact_subscription_cancel(self, sub_id: str, now: datetime) -> bool:
        with self._lock:
            s = self.subscriptions.get(sub_id)
            if not s or s.status in (SubscriptionStatus.CANCELED, SubscriptionStatus.EXPIRED):
                return False
            if s.cancel_at and s.cancel_at <= now:
                s.status = SubscriptionStatus.CANCELED
                s.canceled_at = s.cancel_at
                s.ended_at = s.cancel_at
                s.touch()
                return True
            return False

    def advance_subscription_period(self, sub_id: str, from_end: datetime, next_start: datetime, next_end: datetime, now: datetime) -> bool:
        with self._lock:
            s = self.subscriptions.get(sub_id)
            if not s or s.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING, SubscriptionStatus.PAST_DUE):
                return False
            if s.current_period_end != from_end or from_end > now or next_end <= from_end:
                return False
            if s.cancel_at and s.cancel_at <= from_end:
                return False

            s.current_period_start = next_start
            s.current_period_end = next_end
            s.touch()
            return True

    def mark_invoice_past_due(self, inv_id: str, now: datetime) -> bool:
        with self._lock:
            inv = self.invoices.get(inv_id)
            if not inv or inv.status != InvoiceStatus.PENDING:
                return False
            if inv.due_date and inv.due_date < now:
                inv.status = InvoiceStatus.PAST_DUE
                inv.touch()
                return True
            return False

    # ── User Authentication ──
    def create_user(self, user: User) -> User:
        with self._lock:
            self.users[user.useremail] = copy.deepcopy(user)
            return copy.deepcopy(user)

    def get_user_by_email(self, email: str) -> Optional[User]:
        with self._lock:
            u = self.users.get(email.strip().lower())
            return copy.deepcopy(u) if u else None
