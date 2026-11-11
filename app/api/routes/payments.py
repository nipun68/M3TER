"""
Payment Provider methods and synchronization routes.
"""
from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.dependencies import get_ledger
from app.services.ledger import Ledger

router = APIRouter(prefix="/payments", tags=["Payments & Providers"])


@router.get("/methods")
def list_payment_methods(
    tenant_id: str = Query(...),
    provider_name: str = Query("stripe"),
    ledger: Ledger = Depends(get_ledger),
):
    prov = ledger.get_provider(provider_name)
    if not prov:
        raise HTTPException(status_code=404, detail=f"Payment provider {provider_name} not found")
    methods = prov.list_payment_methods(tenant_id)
    return [m.to_dict() for m in methods]
