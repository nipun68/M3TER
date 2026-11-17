"""
End-to-end FastAPI integration tests verifying M3TER billing, metering, and authentication endpoints.
"""
from fastapi.testclient import TestClient
import pytest
from app.main import app

client = TestClient(app)


def test_auth_api_endpoints():
    reg_payload = {"email": "dev@m3ter.local", "password": "securepassword123"}
    res_reg = client.post("/register", json=reg_payload)
    assert res_reg.status_code == 200
    assert res_reg.json()["message"] == "User registered successfully"

    # Verify duplicate registration is rejected with 409 Conflict (prevents account takeover)
    res_dup = client.post("/register", json=reg_payload)
    assert res_dup.status_code == 409

    res_login = client.post("/login", json=reg_payload)
    assert res_login.status_code == 200
    data = res_login.json()
    assert "token" in data
    token = data["token"]

    headers = {"Authorization": f"Bearer {token}"}
    res_prof = client.get("/profile", headers=headers)
    assert res_prof.status_code == 200
    assert res_prof.json()["message"] == "Profile Page"
    assert res_prof.json()["user"]["email"] == "dev@m3ter.local"

    res_acc = client.get("/account", headers=headers)
    assert res_acc.status_code == 200

    res_no_token = client.get("/profile")
    assert res_no_token.status_code == 401
    res_bad_token = client.get("/profile", headers={"Authorization": "Bearer invalid.token.value"})
    assert res_bad_token.status_code == 401


def test_billing_api_full_lifecycle():
    # 1. Create a Plan
    plan_payload = {
        "name": "Growth Plan",
        "slug": "growth",
        "currency": "usd",
        "features": [
            {"key": "seats", "name": "Team Seats", "type": "seat", "limit": 0},
            {"key": "reports", "name": "Reports", "type": "metered", "limit": 50, "period": "monthly"},
        ],
        "pricing": {
            "base_amount": {"amount": 2900, "currency": "usd"},
            "billing_period": "monthly",
            "tiers": [
                {"feature_key": "reports", "type": "graduated", "up_to": -1, "unit_amount": {"amount": 50, "currency": "usd"}}
            ]
        }
    }
    res_plan = client.post("/plans", json=plan_payload)
    assert res_plan.status_code == 201
    plan_id = res_plan.json()["id"]

    # 2. Create Subscription
    sub_payload = {
        "tenant_id": "customer_acme",
        "plan_id": plan_id,
        "quantity": {"seats": 5}
    }
    res_sub = client.post("/subscriptions", json=sub_payload)
    assert res_sub.status_code == 201
    sub_id = res_sub.json()["id"]
    assert res_sub.json()["status"] == "active"

    # 3. Ingest Usage
    meter_payload = {
        "tenant_id": "customer_acme",
        "feature_key": "reports",
        "quantity": 30
    }
    res_meter = client.post("/meter", json=meter_payload)
    assert res_meter.status_code == 202

    # 4. Check Entitlement
    res_ent = client.get("/entitlements/reports?tenant_id=customer_acme")
    assert res_ent.status_code == 200
    ent = res_ent.json()
    assert ent["allowed"] is True
    assert ent["used"] == 30
    assert ent["remaining"] == 20

    # 5. Generate Invoice
    res_inv = client.post("/invoices/generate", json={"subscription_id": sub_id})
    assert res_inv.status_code == 201
    inv = res_inv.json()
    assert inv["tenant_id"] == "customer_acme"
    assert inv["status"] == "draft"
    inv_id = inv["id"]

    # 6. Mark Invoice Paid
    res_pay = client.post(f"/invoices/{inv_id}/pay?payment_ref=pay_test_999")
    assert res_pay.status_code == 200
    assert res_pay.json()["status"] == "paid"

    # 7. Webhook Ingress
    webhook_payload = {
        "id": "evt_test_123",
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": "in_stripe_mock",
                "metadata": {"ledger_invoice_id": inv_id}
            }
        }
    }
    res_webhook = client.post("/webhooks/stripe", json=webhook_payload)
    assert res_webhook.status_code == 200
    assert res_webhook.json()["handled"] is True
