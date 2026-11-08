"""
Unit tests for Entitlement checks and quota calculations.
"""
from app.core.money import usd
from app.models.plan import Plan, PlanFeature, Pricing, FeatureType, Period
from app.repositories.memory_store import MemoryStore
from app.services.ledger import Ledger


def test_entitlements_and_tenant_isolation():
    store = MemoryStore()
    ledger = Ledger(store=store)

    plan = Plan(
        name="Team Plan",
        slug="team",
        features=[
            PlanFeature(key="export_pdf", name="PDF Export", type=FeatureType.BOOLEAN, limit=1),
            PlanFeature(key="storage_gb", name="Storage", type=FeatureType.METERED, limit=100),
        ]
    )
    ledger.create_plan(plan)

    # Tenant A and Tenant B both subscribe to the same plan
    ledger.create_subscription(tenant_id="tenant_a", plan_id=plan.id)
    ledger.create_subscription(tenant_id="tenant_b", plan_id=plan.id)

    # Boolean check
    res_bool = ledger.entitled("tenant_a", "export_pdf")
    assert res_bool.allowed is True

    # Initial metered check
    res_storage = ledger.entitled("tenant_a", "storage_gb")
    assert res_storage.allowed is True
    assert res_storage.remaining == 100

    # Tenant A uses 60 GB
    ledger.meter("tenant_a", "storage_gb", 60)
    res_a = ledger.entitled("tenant_a", "storage_gb")
    assert res_a.allowed is True
    assert res_a.used == 60
    assert res_a.remaining == 40

    # Tenant B isolation check: Tenant B's quota must be unaffected by Tenant A
    res_b = ledger.entitled("tenant_b", "storage_gb")
    assert res_b.allowed is True
    assert res_b.used == 0
    assert res_b.remaining == 100

    # Tenant A exceeds remaining quota (uses 50 GB more -> 110 GB total)
    ledger.meter("tenant_a", "storage_gb", 50)
    res_a_exceeded = ledger.entitled("tenant_a", "storage_gb")
    assert res_a_exceeded.allowed is False
    assert res_a_exceeded.used == 110
    assert res_a_exceeded.remaining == 0
    assert res_a_exceeded.reason == "quota exceeded"
