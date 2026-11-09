"""
Unit tests for Invoice generation, credit pools, coupons, and tax calculations.
"""
from typing import Optional
from app.core.money import usd, zero, Money
from app.models.coupon import Coupon, CouponType
from app.models.invoice import InvoiceStatus, LineItemType
from app.models.plan import Plan, PlanFeature, Pricing, PriceTier, CreditPool, FeatureType, Period, TierType
from app.plugins.hooks import TaxCalculator
from app.plugins.registry import PluginRegistry
from app.repositories.memory_store import MemoryStore
from app.services.ledger import Ledger


class SimpleTaxPlugin(TaxCalculator):
    def name(self) -> str:
        return "simple_tax"

    def calculate_tax(self, net_amount: Money, tenant_id: str) -> Optional[Money]:
        # 10% tax rate
        return net_amount.percent(10)


def test_complete_invoice_generation():
    store = MemoryStore()
    plugins = PluginRegistry()
    plugins.register(SimpleTaxPlugin())
    ledger = Ledger(store=store, plugins=plugins)

    # Plan with:
    # 1. Base fee: $50.00 (5000 cents)
    # 2. API calls metered feature: limit 1000 included, overage graduated tiers (10c up to 2000, 5c unbounded)
    # 3. Seats feature: tiered @ $10/seat (1000 cents)
    # 4. Usage credit pool: $20.00 (2000 cents) against 'api_calls'
    plan = Plan(
        name="Enterprise",
        slug="enterprise",
        currency="usd",
        features=[
            PlanFeature(key="api_calls", name="API Calls", type=FeatureType.METERED, limit=1000),
            PlanFeature(key="seats", name="Seats", type=FeatureType.SEAT, limit=0),
        ],
        pricing=Pricing(
            base_amount=usd(5000),
            billing_period=Period.MONTHLY,
            tiers=[
                PriceTier(feature_key="api_calls", type=TierType.GRADUATED, up_to=2000, unit_amount=usd(10)),
                PriceTier(feature_key="api_calls", type=TierType.GRADUATED, up_to=-1, unit_amount=usd(5)),
                PriceTier(feature_key="seats", type=TierType.GRADUATED, up_to=-1, unit_amount=usd(1000)),
            ]
        ),
        credits=[
            CreditPool(key="api_credit", amount=usd(2000), feature_keys=["api_calls"])
        ]
    )
    ledger.create_plan(plan)

    # Create subscription with 3 seats
    sub = ledger.create_subscription(
        tenant_id="enterprise_tenant",
        plan_id=plan.id,
        quantity={"seats": 3}
    )

    # Ingest 2500 API calls (1000 included + 1500 billable overage)
    # Overage calculation:
    # 1000 units in tier 1 (1001..2000) @ 10c = $100.00 (10000 cents)
    # 500 units in tier 2 (2001..2500) @ 5c = $25.00 (2500 cents)
    # Total overage = $125.00 (12500 cents)
    ledger.meter("enterprise_tenant", "api_calls", 2500)

    # Create 20% discount coupon and apply to subscription
    coupon = Coupon(code="SAVE20", percentage=20, type=CouponType.PERCENTAGE)
    ledger.create_coupon(coupon)
    ledger.apply_coupon(sub.id, "SAVE20")

    # Generate Invoice
    inv = ledger.generate_invoice(sub.id)

    # Breakdown verification:
    # Base fee: 5000 cents ($50)
    # Seats: 3 * 1000 = 3000 cents ($30)
    # API Overage: 12500 cents ($125)
    # Subtotal: 5000 + 3000 + 12500 = 20500 cents ($205.00)
    assert inv.subtotal == usd(20500)

    # Usage credit applied against API calls ($20.00 = 2000 cents)
    assert inv.credit_amount == usd(2000)

    # Discount base = 20500 - 2000 = 18500 cents
    # Coupon 20% of 18500 = 3700 cents ($37.00)
    assert inv.discount_amount == usd(3700)

    # Net = 18500 - 3700 = 14800 cents ($148.00)
    # Tax 10% on Net = 1480 cents ($14.80)
    assert inv.tax_amount == usd(1480)

    # Total = Net (14800) + Tax (1480) = 16280 cents ($162.80)
    assert inv.total == usd(16280)

    # Status check
    assert inv.status == InvoiceStatus.DRAFT

    # Mark paid
    paid_inv = ledger.mark_invoice_paid(inv.id, payment_ref="ch_stripe_mock_123")
    assert paid_inv.status == InvoiceStatus.PAID
    assert paid_inv.payment_ref == "ch_stripe_mock_123"
