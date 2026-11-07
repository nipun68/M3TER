"""
Unit tests for Plans and Feature Catalog.
"""
import pytest
from app.core.exceptions import ErrAlreadyExists, ErrPlanNotFound
from app.core.money import usd
from app.models.plan import Plan, PlanFeature, Pricing, FeatureType, Period
from app.models.feature import CatalogFeature
from app.repositories.memory_store import MemoryStore
from app.services.ledger import Ledger


def test_plan_creation_and_allows():
    store = MemoryStore()
    ledger = Ledger(store=store)

    plan = Plan(
        name="Pro Plan",
        slug="pro",
        currency="usd",
        trial_days=14,
        features=[
            PlanFeature(key="sso", name="SSO", type=FeatureType.BOOLEAN, limit=1),
            PlanFeature(key="export", name="Export", type=FeatureType.BOOLEAN, limit=0),
            PlanFeature(key="api_calls", name="API Calls", type=FeatureType.METERED, limit=1000, soft_limit=True),
            PlanFeature(key="hard_limit_calls", name="Hard Limit", type=FeatureType.METERED, limit=500, soft_limit=False),
            PlanFeature(key="unlimited_seats", name="Seats", type=FeatureType.SEAT, limit=-1),
        ],
        pricing=Pricing(
            base_amount=usd(4900),
            billing_period=Period.MONTHLY,
        )
    )
    created = ledger.create_plan(plan)
    assert created.id is not None
    assert created.slug == "pro"

    # allows logic
    assert created.allows("sso", 0) is True
    assert created.allows("export", 0) is False
    assert created.allows("api_calls", 500) is True
    assert created.allows("api_calls", 1500) is True  # soft limit allowed
    assert created.allows("hard_limit_calls", 499) is True
    assert created.allows("hard_limit_calls", 500) is False  # hard limit blocked
    assert created.allows("unlimited_seats", 10000) is True
    assert created.allows("non_existent_feature", 0) is False


def test_duplicate_slug_rejection():
    store = MemoryStore()
    ledger = Ledger(store=store)

    p1 = Plan(name="Starter", slug="starter")
    p2 = Plan(name="Starter 2", slug="starter")

    ledger.create_plan(p1)
    with pytest.raises(ErrAlreadyExists):
        ledger.create_plan(p2)


def test_feature_catalog():
    store = MemoryStore()
    ledger = Ledger(store=store)

    feat = CatalogFeature(
        key="ai_tokens",
        name="AI Tokens",
        type=FeatureType.METERED,
        is_global=True,
    )
    ledger.create_feature(feat)

    fetched = ledger.get_feature_by_key("ai_tokens")
    assert fetched is not None
    assert fetched.name == "AI Tokens"
    assert fetched.is_global is True
