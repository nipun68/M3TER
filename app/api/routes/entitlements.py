"""
Entitlements API routes.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from app.api.dependencies import get_ledger
from app.services.ledger import Ledger
from app.schemas.entitlement import EntitlementCheckSchema, EntitlementResponseSchema

router = APIRouter(prefix="/entitlements", tags=["Entitlements & Quotas"])


@router.post("/check", response_model=EntitlementResponseSchema)
def check_entitlement(data: EntitlementCheckSchema, ledger: Ledger = Depends(get_ledger)):
    res = ledger.check(
        tenant_id=data.tenant_id,
        feature_key=data.feature_key,
        app_id=data.app_id,
        strict=False,
    )
    return res.to_dict()


@router.get("/{feature_key}", response_model=EntitlementResponseSchema)
def get_entitlement(
    feature_key: str,
    tenant_id: str = Query(...),
    app_id: str = Query("default"),
    ledger: Ledger = Depends(get_ledger),
):
    res = ledger.entitled(tenant_id=tenant_id, feature_key=feature_key, app_id=app_id)
    return res.to_dict()
