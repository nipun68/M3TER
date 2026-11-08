"""
Lifecycle clock engine reproducing lifecycle.go and lifecycle_worker.go.
Accurately advances subscription periods with anchor day calculation,
enacts due cancellations, ends trials, and marks overdue invoices past due.
"""
from __future__ import annotations
import calendar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from app.config.logging import logger
from app.core.entity import utc_now
from app.models.plan import Period, Plan
from app.models.subscription import Subscription, SubscriptionStatus, BillingPeriod, Renewal
from app.plugins.registry import PluginRegistry
from app.repositories.base import BaseStore


RUNNING_STATUSES = [
    SubscriptionStatus.ACTIVE.value,
    SubscriptionStatus.TRIALING.value,
    SubscriptionStatus.PAST_DUE.value,
]

CANCELLABLE_STATUSES = [
    SubscriptionStatus.ACTIVE.value,
    SubscriptionStatus.TRIALING.value,
    SubscriptionStatus.PAST_DUE.value,
    SubscriptionStatus.PAUSED.value,
]


def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def anchor_day(start: datetime, end: datetime) -> int:
    """
    Recovers the day of the month a subscription renews on.
    Handles short months (e.g. Feb 28 -> Mar 31).
    """
    d = end.day
    if d == days_in_month(end.year, end.month) and start.day > d:
        return start.day
    return end.day


def shift_months(from_dt: datetime, months: int, day: int) -> datetime:
    """
    Returns the datetime 'months' after from_dt, on 'day', clamped to the month's last day.
    """
    total_months = from_dt.month - 1 + months
    new_year = from_dt.year + total_months // 12
    new_month = total_months % 12 + 1
    max_days = days_in_month(new_year, new_month)
    clamped_day = min(day, max_days)
    return from_dt.replace(
        year=new_year,
        month=new_month,
        day=clamped_day,
        tzinfo=timezone.utc
    )


def next_period(start: datetime, end: datetime, period: Period) -> Tuple[datetime, datetime]:
    """Calculates the next billing period [next_start, next_end)."""
    months = 12 if period == Period.YEARLY else 1
    target_day = anchor_day(start, end)
    next_start = end
    next_end = shift_months(end, months, target_day)
    return next_start, next_end


@dataclass
class LifecycleReport:
    periods_advanced: List[str] = field(default_factory=list)
    cancels_enacted: List[str] = field(default_factory=list)
    trials_ended: List[str] = field(default_factory=list)
    invoices_past_due: List[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.periods_advanced or self.cancels_enacted or self.trials_ended or self.invoices_past_due)


class LifecycleEngine:
    def __init__(self, store: BaseStore, plugins: PluginRegistry) -> None:
        self.store = store
        self.plugins = plugins

    def advance(self, now: Optional[datetime] = None) -> LifecycleReport:
        """
        Executes one full lifecycle step:
        1. Advance ended periods
        2. Enact due cancellations
        3. End due trials
        4. Mark overdue invoices past due
        """
        n = now or utc_now()
        report = LifecycleReport()

        report.periods_advanced = self.advance_periods(n)
        report.cancels_enacted = self.enact_cancels(n)
        report.trials_ended = self.end_trials(n)
        report.invoices_past_due = self.mark_invoices_past_due(n)

        if not report.is_empty:
            logger.info(
                f"Lifecycle Advance report: periods={len(report.periods_advanced)}, "
                f"cancels={len(report.cancels_enacted)}, trials={len(report.trials_ended)}, "
                f"past_due_invoices={len(report.invoices_past_due)}"
            )
        return report

    def advance_periods(self, now: datetime) -> List[str]:
        advanced: List[str] = []
        due_subs = self.store.list_due_subscriptions(due_before=now, statuses=RUNNING_STATUSES)

        for sub in due_subs:
            plan = self.store.get_plan(sub.plan_id)
            if not plan or not plan.pricing or plan.pricing.billing_period == Period.NONE:
                continue

            b_period = plan.pricing.billing_period
            cur_start = sub.current_period_start
            cur_end = sub.current_period_end
            ended_periods: List[BillingPeriod] = []

            # Walk forward until the period contains now or scheduled cancellation
            walk_start, walk_end = cur_start, cur_end
            max_catch_up = 1200
            steps = 0

            while walk_end <= now and steps < max_catch_up:
                ended_periods.append(BillingPeriod(start=walk_start, end=walk_end))
                walk_start, walk_end = next_period(walk_start, walk_end, b_period)
                steps += 1
                if sub.cancel_at and walk_end > sub.cancel_at:
                    break

            if ended_periods:
                # Conditional write in store
                applied = self.store.advance_subscription_period(
                    sub_id=sub.id,
                    from_end=cur_end,
                    next_start=walk_start,
                    next_end=walk_end,
                    now=now,
                )
                if applied:
                    advanced.append(sub.id)
                    sub.current_period_start = walk_start
                    sub.current_period_end = walk_end
                    self.plugins.emit_subscription_renewed(
                        Renewal(subscription=sub, ended=ended_periods)
                    )

        return advanced

    def enact_cancels(self, now: datetime) -> List[str]:
        enacted: List[str] = []
        # Find subscriptions whose cancel_at has arrived
        subs = self.store.list_subscriptions()
        for s in subs:
            if s.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING, SubscriptionStatus.PAST_DUE, SubscriptionStatus.PAUSED):
                if s.cancel_at and s.cancel_at <= now:
                    if self.store.enact_subscription_cancel(s.id, now):
                        enacted.append(s.id)
                        s.status = SubscriptionStatus.CANCELED
                        s.canceled_at = s.cancel_at
                        self.plugins.emit_subscription_canceled(s)
        return enacted

    def end_trials(self, now: datetime) -> List[str]:
        ended: List[str] = []
        subs = self.store.list_subscriptions()
        for s in subs:
            if s.status == SubscriptionStatus.TRIALING and s.trial_end and s.trial_end <= now:
                if self.store.end_subscription_trial(s.id, now):
                    ended.append(s.id)
        return ended

    def mark_invoices_past_due(self, now: datetime) -> List[str]:
        past_due: List[str] = []
        overdue_invoices = self.store.list_overdue_invoices(now)
        for inv in overdue_invoices:
            if self.store.mark_invoice_past_due(inv.id, now):
                past_due.append(inv.id)
        return past_due
