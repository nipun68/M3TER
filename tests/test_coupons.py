"""
Unit tests for Coupons, expiration, and redemptions.
"""
from datetime import datetime, timezone, timedelta
import pytest
from app.core.exceptions import ErrCouponInvalid, ErrCouponDepleted
from app.core.money import usd
from app.models.coupon import Coupon, CouponType
from app.models.plan import Plan
from app.repositories.memory_store import MemoryStore
from app.services.ledger import Ledger


def test_coupon_redemption_and_limits():
    store = MemoryStore()
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    ledger = Ledger(store=store, clock=lambda: now)

    plan = Plan(name="Basic", slug="basic")
    ledger.create_plan(plan)
    sub1 = ledger.create_subscription("t1", plan.id)
    sub2 = ledger.create_subscription("t2", plan.id)

    # Coupon with max_redemptions = 1
    cpn = Coupon(
        code="ONETIME",
        name="Single Use",
        type=CouponType.AMOUNT,
        amount=usd(1000),
        max_redemptions=1,
    )
    ledger.create_coupon(cpn)

    # First redemption succeeds
    ledger.apply_coupon(sub1.id, "ONETIME")
    saved_cpn = ledger.store.get_coupon_by_id(cpn.id)
    assert saved_cpn.times_redeemed == 1

    # Second redemption on another subscription fails with ErrCouponInvalid (depleted)
    with pytest.raises(ErrCouponInvalid):
        ledger.apply_coupon(sub2.id, "ONETIME")


def test_coupon_expiration():
    store = MemoryStore()
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    ledger = Ledger(store=store, clock=lambda: now)

    plan = Plan(name="Basic", slug="basic")
    ledger.create_plan(plan)
    sub = ledger.create_subscription("t1", plan.id)

    # Expired coupon
    expired_cpn = Coupon(
        code="EXPIRED",
        percentage=50,
        valid_until=now - timedelta(days=1),
    )
    ledger.create_coupon(expired_cpn)

    with pytest.raises(ErrCouponInvalid):
        ledger.apply_coupon(sub.id, "EXPIRED")
