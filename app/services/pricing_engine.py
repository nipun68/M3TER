"""
Price tier calculations and overage computation replicating invoice/pricing.go.
Guarantees mathematical correctness, checked overflow handling, and exact tier algorithms.
"""
from __future__ import annotations
from typing import List
from app.core.exceptions import ErrInvalidTiers
from app.core.money import Money, zero
from app.models.plan import PriceTier, TierType


def is_unbounded(up_to: int) -> bool:
    """Non-positive (0 or -1) indicates unbounded tier."""
    return up_to <= 0


def sort_tiers(tiers: List[PriceTier]) -> List[PriceTier]:
    """
    Sorts tiers by UpTo ascending, with unbounded (<= 0) sorted last,
    and Priority breaking ties. Does not mutate the input list.
    """
    def sort_key(t: PriceTier):
        unbounded = is_unbounded(t.up_to)
        return (1 if unbounded else 0, t.up_to if not unbounded else 0, t.priority)

    return sorted(tiers, key=sort_key)


def tier_at(tiers: List[PriceTier], qty: int) -> PriceTier:
    """
    Finds the tier that a total quantity of qty falls into.
    Assumes tiers are non-empty and sorted by sort_tiers.
    The last tier extends to cover anything above it.
    """
    for i, t in enumerate(tiers):
        if is_unbounded(t.up_to) or i == len(tiers) - 1 or qty <= t.up_to:
            return t
    return tiers[-1]


def compute_graduated(tiers: List[PriceTier], qty: int, currency: str) -> Money:
    """
    Charges each tier for the units that fall inside its range.
    """
    total = zero(currency)
    if qty <= 0 or not tiers:
        return total

    consumed = 0
    for i, t in enumerate(tiers):
        if consumed >= qty:
            break

        if is_unbounded(t.up_to) or i == len(tiers) - 1:
            capacity = qty - consumed
        else:
            capacity = t.up_to - consumed

        if capacity <= 0:
            continue

        units = min(capacity, qty - consumed)
        charge = Money(t.unit_amount.amount, currency).checked_multiply(units)
        total = total.checked_add(charge)
        consumed += units

    return total


def compute_volume(tiers: List[PriceTier], usage: int, included: int, currency: str) -> Money:
    """
    Applies the rate of the tier covering TOTAL usage to the billable units (usage - included).
    """
    if usage <= 0 or not tiers:
        return zero(currency)

    billable = usage - included
    if billable <= 0:
        return zero(currency)

    t = tier_at(tiers, usage)
    return Money(t.unit_amount.amount, currency).checked_multiply(billable)


def compute_flat(tiers: List[PriceTier], qty: int, currency: str) -> Money:
    """
    Charges the flat fee attached to the tier the quantity reaches.
    """
    if qty <= 0 or not tiers:
        return zero(currency)
    t = tier_at(tiers, qty)
    return Money(t.flat_amount.amount, currency)


def compute_overage(tiers: List[PriceTier], usage: int, included: int, currency: str) -> Money:
    """
    Prices the billable excess of usage over an included allowance,
    using whichever tier model the plan declares (graduated, volume, flat).
    """
    currency = currency.lower().strip()
    if not tiers or included < 0 or usage <= included:
        return zero(currency)

    sorted_tiers = sort_tiers(tiers)
    tier_type = sorted_tiers[0].type

    if tier_type == TierType.VOLUME:
        return compute_volume(sorted_tiers, usage, included, currency)
    elif tier_type == TierType.FLAT:
        fee_usage = compute_flat(sorted_tiers, usage, currency)
        fee_included = compute_flat(sorted_tiers, included, currency)
        fee = fee_usage.checked_subtract(fee_included)
        return fee.max(zero(currency))
    elif tier_type == TierType.GRADUATED:
        priced = compute_graduated(sorted_tiers, usage, currency)
        allowance = compute_graduated(sorted_tiers, included, currency)
        return priced.checked_subtract(allowance)
    else:
        return zero(currency)


def validate_tiers(tiers: List[PriceTier], currency: str) -> None:
    """
    Validates tier configuration against structural invariants.
    Raises ErrInvalidTiers on invalid configuration.
    """
    if not tiers:
        return

    currency = currency.lower().strip()
    want_type = tiers[0].type
    want_feature_key = tiers[0].feature_key
    seen_up_to = set()

    for idx, t in enumerate(tiers):
        if t.type != want_type:
            raise ErrInvalidTiers(
                f"tier {idx} (UpTo {t.up_to}, feature {t.feature_key!r}) mixes types {want_type} and {t.type}"
            )

        if t.type not in (TierType.GRADUATED, TierType.VOLUME, TierType.FLAT):
            raise ErrInvalidTiers(
                f"tier {idx} (UpTo {t.up_to}, feature {t.feature_key!r}) has invalid type {t.type}"
            )

        if t.unit_amount.currency and t.unit_amount.currency.lower() != currency:
            raise ErrInvalidTiers(
                f"tier {idx} (UpTo {t.up_to}) unit currency {t.unit_amount.currency} != {currency}"
            )
        if t.flat_amount.currency and t.flat_amount.currency.lower() != currency:
            raise ErrInvalidTiers(
                f"tier {idx} (UpTo {t.up_to}) flat currency {t.flat_amount.currency} != {currency}"
            )

        if t.unit_amount.amount < 0 or t.flat_amount.amount < 0:
            raise ErrInvalidTiers(
                f"tier {idx} (UpTo {t.up_to}) has negative rate"
            )

        if t.feature_key != want_feature_key:
            raise ErrInvalidTiers(
                f"tier {idx} feature key {t.feature_key!r} != {want_feature_key!r}"
            )

        up_to_key = 0 if is_unbounded(t.up_to) else t.up_to
        if up_to_key in seen_up_to:
            raise ErrInvalidTiers(
                f"tier {idx} (UpTo {t.up_to}) duplicates another tier's UpTo"
            )
        seen_up_to.add(up_to_key)

        if t.type in (TierType.GRADUATED, TierType.VOLUME) and t.flat_amount.amount != 0:
            raise ErrInvalidTiers(
                f"tier {idx} is {t.type} but carries non-zero flat amount"
            )
        if t.type == TierType.FLAT and t.unit_amount.amount != 0:
            raise ErrInvalidTiers(
                f"tier {idx} is flat but carries non-zero unit amount"
            )
