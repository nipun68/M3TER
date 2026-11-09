"""
Usage Metering API routes.
"""
from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.api.dependencies import get_ledger
from app.models.meter import UsageEvent
from app.services.ledger import Ledger
from app.schemas.meter import UsageEventSchema, UsageEventResponseSchema

router = APIRouter(prefix="/meter", tags=["Usage Metering"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def ingest_usage_event(data: UsageEventSchema, ledger: Ledger = Depends(get_ledger)):
    if data.idempotency_key:
        ledger.meter_with_key(
            tenant_id=data.tenant_id,
            feature_key=data.feature_key,
            idempotency_key=data.idempotency_key,
            quantity=data.quantity,
            app_id=data.app_id,
        )
    else:
        ledger.meter(
            tenant_id=data.tenant_id,
            feature_key=data.feature_key,
            quantity=data.quantity,
            app_id=data.app_id,
        )
    return {"status": "accepted", "tenant_id": data.tenant_id, "feature_key": data.feature_key}


@router.get("/usage", response_model=List[UsageEventResponseSchema])
def query_usage(
    tenant_id: str = Query(...),
    app_id: str = Query("default"),
    feature_key: Optional[str] = Query(None),
    ledger: Ledger = Depends(get_ledger),
):
    events = ledger.store.query_usage(tenant_id=tenant_id, app_id=app_id, feature_key=feature_key)
    return [e.to_dict() for e in events]
