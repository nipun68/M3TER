"""
Unit tests for price tier algorithms replicating invoice/pricing_test.go.
"""
import pytest
from app.core.exceptions import ErrInvalidTiers
from app.core.money import usd, zero
from app.models.plan import PriceTier, TierType
from app.services.pricing_engine import (
    sort_tiers,
    compute_graduated,
    compute_volume,
    compute_flat,
    compute_overage,
    validate_tiers,
)


def test_sort_tiers_unbounded_last():
    tiers = [
        PriceTier(feature_key="api", type=TierType.GRADUATED, up_to=-1, unit_amount=usd(5), priority=2),
        PriceTier(feature_key="api", type=TierType.GRADUATED, up_to=1000, unit_amount=usd(10), priority=1),
        PriceTier(feature_key="api", type=TierType.GRADUATED, up_to=5000, unit_amount=usd(8), priority=1),
    ]
    sorted_t = sort_tiers(tiers)
    assert sorted_t[0].up_to == 1000
    assert sorted_t[1].up_to == 5000
    assert sorted_t[2].up_to == -1


def test_compute_graduated():
    # 0..1000 @ 10c, 1001..5000 @ 8c, 5001+ @ 5c
    tiers = [
        PriceTier(feature_key="api", type=TierType.GRADUATED, up_to=1000, unit_amount=usd(10)),
        PriceTier(feature_key="api", type=TierType.GRADUATED, up_to=5000, unit_amount=usd(8)),
        PriceTier(feature_key="api", type=TierType.GRADUATED, up_to=-1, unit_amount=usd(5)),
    ]

    # 500 units -> 500 * 10 = 5000 cents ($50.00)
    assert compute_graduated(tiers, 500, "usd") == usd(5000)

    # 1000 units -> 1000 * 10 = 10000 cents ($100.00)
    assert compute_graduated(tiers, 1000, "usd") == usd(10000)

    # 3000 units -> 1000*10 + 2000*8 = 10000 + 16000 = 26000 cents ($260.00)
    assert compute_graduated(tiers, 3000, "usd") == usd(26000)

    # 6000 units -> 1000*10 + 4000*8 + 1000*5 = 10000 + 32000 + 5000 = 47000 cents ($470.00)
    assert compute_graduated(tiers, 6000, "usd") == usd(47000)


def test_compute_volume():
    # <= 1000 @ 10c, <= 5000 @ 8c, > 5000 @ 5c
    tiers = [
        PriceTier(feature_key="api", type=TierType.VOLUME, up_to=1000, unit_amount=usd(10)),
        PriceTier(feature_key="api", type=TierType.VOLUME, up_to=5000, unit_amount=usd(8)),
        PriceTier(feature_key="api", type=TierType.VOLUME, up_to=-1, unit_amount=usd(5)),
    ]

    # Total 3000 units, included 0 -> Tier 2 (8c) applied to all 3000 = 24000 cents ($240.00)
    assert compute_volume(tiers, 3000, 0, "usd") == usd(24000)

    # Total 6000 units, included 1000 -> Tier 3 (5c) applied to (6000-1000=5000) = 25000 cents ($250.00)
    assert compute_volume(tiers, 6000, 1000, "usd") == usd(25000)


def test_compute_flat():
    tiers = [
        PriceTier(feature_key="seats", type=TierType.FLAT, up_to=10, flat_amount=usd(5000)),
        PriceTier(feature_key="seats", type=TierType.FLAT, up_to=50, flat_amount=usd(20000)),
        PriceTier(feature_key="seats", type=TierType.FLAT, up_to=-1, flat_amount=usd(50000)),
    ]
    assert compute_flat(tiers, 5, "usd") == usd(5000)
    assert compute_flat(tiers, 25, "usd") == usd(20000)
    assert compute_flat(tiers, 100, "usd") == usd(50000)


def test_compute_overage_differential():
    grad_tiers = [
        PriceTier(feature_key="storage", type=TierType.GRADUATED, up_to=1000, unit_amount=usd(10)),
        PriceTier(feature_key="storage", type=TierType.GRADUATED, up_to=-1, unit_amount=usd(5)),
    ]
    # Included 500 units, Total usage 1500 units
    # Usage total: 1000*10 + 500*5 = 12500
    # Included total: 500*10 = 5000
    # Overage: 12500 - 5000 = 7500 ($75.00)
    assert compute_overage(grad_tiers, 1500, 500, "usd") == usd(7500)


def test_validate_tiers():
    valid = [
        PriceTier(feature_key="api", type=TierType.GRADUATED, up_to=100, unit_amount=usd(10)),
        PriceTier(feature_key="api", type=TierType.GRADUATED, up_to=200, unit_amount=usd(8)),
    ]
    validate_tiers(valid, "usd")  # Should pass

    # Negative rate
    with pytest.raises(ErrInvalidTiers):
        validate_tiers([PriceTier(feature_key="api", type=TierType.GRADUATED, up_to=100, unit_amount=usd(-5))], "usd")

    # Duplicate UpTo
    with pytest.raises(ErrInvalidTiers):
        validate_tiers([
            PriceTier(feature_key="api", type=TierType.GRADUATED, up_to=100, unit_amount=usd(5)),
            PriceTier(feature_key="api", type=TierType.GRADUATED, up_to=100, unit_amount=usd(6)),
        ], "usd")

    # Mixed tier types
    with pytest.raises(ErrInvalidTiers):
        validate_tiers([
            PriceTier(feature_key="api", type=TierType.GRADUATED, up_to=100, unit_amount=usd(5)),
            PriceTier(feature_key="api", type=TierType.VOLUME, up_to=200, unit_amount=usd(4)),
        ], "usd")
