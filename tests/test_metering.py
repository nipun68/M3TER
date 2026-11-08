"""
Unit tests for usage metering and event batching.
"""
import pytest
from datetime import datetime, timezone, timedelta
from app.models.meter import UsageEvent
from app.models.plan import Period
from app.repositories.memory_store import MemoryStore
from app.services.ledger import Ledger


def test_idempotency_and_aggregation():
    store = MemoryStore()
    ledger = Ledger(store=store)

    tenant_id = "tenant_xyz"
    feature_key = "api_calls"

    # Ingest 3 events, two share idempotency_key
    e1 = UsageEvent(tenant_id=tenant_id, feature_key=feature_key, quantity=10, idempotency_key="key_1")
    e2 = UsageEvent(tenant_id=tenant_id, feature_key=feature_key, quantity=10, idempotency_key="key_1")  # Duplicate
    e3 = UsageEvent(tenant_id=tenant_id, feature_key=feature_key, quantity=25, idempotency_key="key_2")

    store.ingest_batch([e1, e2, e3])

    # Check aggregation: 10 + 25 = 35 (duplicate was dropped)
    total = store.aggregate(tenant_id=tenant_id, app_id="default", feature_key=feature_key, period=Period.MONTHLY)
    assert total == 35


def test_meter_via_ledger_engine():
    store = MemoryStore()
    ledger = Ledger(store=store)

    ledger.meter_with_key(tenant_id="t1", feature_key="compute_hours", idempotency_key="event_1", quantity=5)
    ledger.meter_with_key(tenant_id="t1", feature_key="compute_hours", idempotency_key="event_1", quantity=5)  # Duplicate
    ledger.meter(tenant_id="t1", feature_key="compute_hours", quantity=3)

    total = store.aggregate(tenant_id="t1", app_id="default", feature_key="compute_hours", period=Period.MONTHLY)
    assert total == 8
