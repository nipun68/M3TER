"""
Unit tests for Lifecycle Clock engine reproducing lifecycle_test.go.
"""
from datetime import datetime, timezone, timedelta
from app.models.invoice import Invoice, InvoiceStatus
from app.models.plan import Plan, Pricing, Period
from app.models.subscription import SubscriptionStatus
from app.repositories.memory_store import MemoryStore
from app.services.ledger import Ledger
from app.services.lifecycle import next_period, anchor_day, shift_months


def test_anchor_day_and_short_months():
    # Jan 31 to Feb 28 -> next period in March must recover 31st!
    start = datetime(2026, 1, 31, 12, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)

    # anchorDay should recover 31
    assert anchor_day(start, end) == 31

    next_s, next_e = next_period(start, end, Period.MONTHLY)
    assert next_s == end
    # Next end must land on March 31!
    assert next_e == datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)


def test_lifecycle_advance_flow():
    store = MemoryStore()
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ledger = Ledger(store=store, clock=lambda: t0)

    # 1. Plan with 14-day trial
    plan = Plan(name="Pro", slug="pro", trial_days=14, pricing=Pricing(billing_period=Period.MONTHLY))
    ledger.create_plan(plan)

    # 2. Subscription starting in trial
    sub = ledger.create_subscription("t1", plan.id)
    assert sub.status == SubscriptionStatus.TRIALING
    trial_end = sub.trial_end

    # 3. Fast-forward clock 15 days (trial expires)
    t1 = t0 + timedelta(days=15)
    ledger.clock = lambda: t1
    report = ledger.lifecycle_engine.advance(t1)

    assert sub.id in report.trials_ended
    refreshed_sub = ledger.get_subscription(sub.id)
    assert refreshed_sub.status == SubscriptionStatus.ACTIVE

    # 4. Schedule cancellation at period end
    ledger.cancel_subscription(sub.id, immediately=False)
    assert refreshed_sub.status == SubscriptionStatus.ACTIVE

    # 5. Fast forward clock past period end (e.g. 35 days later)
    t2 = t0 + timedelta(days=35)
    ledger.clock = lambda: t2
    report2 = ledger.lifecycle_engine.advance(t2)

    assert sub.id in report2.cancels_enacted
    ended_sub = ledger.get_subscription(sub.id)
    assert ended_sub.status == SubscriptionStatus.CANCELED
