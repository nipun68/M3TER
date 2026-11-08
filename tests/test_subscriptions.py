"""
Unit tests for Subscription management and lifecycle transitions.
"""
from datetime import datetime, timezone, timedelta
import pytest
from app.core.exceptions import ErrSubscriptionNotFound, ErrSubscriptionCanceled
from app.core.money import usd
from app.models.plan import Plan, Pricing, Period
from app.models.subscription import SubscriptionStatus
from app.repositories.memory_store import MemoryStore
from app.services.ledger import Ledger


def test_subscription_creation_and_trials():
    store = MemoryStore()
    ledger = Ledger(store=store)

    plan = Plan(name="Basic", slug="basic", trial_days=7)
    ledger.create_plan(plan)

    sub = ledger.create_subscription(tenant_id="tenant_1", plan_id=plan.id)
    assert sub.status == SubscriptionStatus.TRIALING
    assert sub.trial_start is not None
    assert sub.trial_end is not None
    assert (sub.trial_end - sub.trial_start).days == 7


def test_cancellation_scheduled_vs_immediate():
    store = MemoryStore()
    ledger = Ledger(store=store)

    plan = Plan(name="Basic", slug="basic", trial_days=0)
    ledger.create_plan(plan)

    # 1. Scheduled cancellation
    sub1 = ledger.create_subscription(tenant_id="t1", plan_id=plan.id)
    sub1_canceled = ledger.cancel_subscription(sub1.id, immediately=False)
    assert sub1_canceled.status == SubscriptionStatus.ACTIVE  # Keeps running until period end
    assert sub1_canceled.cancel_at == sub1.current_period_end

    # 2. Immediate cancellation
    sub2 = ledger.create_subscription(tenant_id="t2", plan_id=plan.id)
    sub2_canceled = ledger.cancel_subscription(sub2.id, immediately=True)
    assert sub2_canceled.status == SubscriptionStatus.CANCELED
    assert sub2_canceled.canceled_at is not None


def test_pause_and_resume_with_stretch():
    store = MemoryStore()
    fixed_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ledger = Ledger(store=store, clock=lambda: fixed_time)

    plan = Plan(name="Basic", slug="basic", trial_days=0)
    ledger.create_plan(plan)

    sub = ledger.create_subscription(tenant_id="t1", plan_id=plan.id)
    orig_period_end = sub.current_period_end

    # Pause at 2026-01-05 (4 days later)
    pause_time = datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc)
    ledger.clock = lambda: pause_time
    paused = ledger.pause_subscription(sub.id)
    assert paused.status == SubscriptionStatus.PAUSED

    # Resume at 2026-01-15 (10-day pause)
    resume_time = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    ledger.clock = lambda: resume_time
    resumed = ledger.resume_subscription(sub.id)
    assert resumed.status == SubscriptionStatus.ACTIVE

    # Period end moved forward by 10 days
    assert resumed.current_period_end == orig_period_end + timedelta(days=10)
    assert resumed.stretch is not None
    assert resumed.stretch.original_end == orig_period_end
