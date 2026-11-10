"""
Invoicing API routes.
"""
from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.api.dependencies import get_ledger
from app.core.exceptions import ErrAlreadyExists, ErrNotFound
from app.services.ledger import Ledger
from app.schemas.invoice import InvoiceGenerateRequestSchema, InvoiceResponseSchema

router = APIRouter(prefix="/invoices", tags=["Invoicing"])


@router.post("/generate", status_code=status.HTTP_201_CREATED, response_model=InvoiceResponseSchema)
def generate_invoice(data: InvoiceGenerateRequestSchema, ledger: Ledger = Depends(get_ledger)):
    try:
        p_start = datetime.fromisoformat(data.period_start) if data.period_start else None
        p_end = datetime.fromisoformat(data.period_end) if data.period_end else None
        inv = ledger.generate_invoice(
            sub_id=data.subscription_id,
            period_start=p_start,
            period_end=p_end,
        )
        return inv.to_dict()
    except ErrAlreadyExists as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ErrNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[InvoiceResponseSchema])
def list_invoices(
    tenant_id: Optional[str] = Query(None),
    app_id: str = Query("default"),
    ledger: Ledger = Depends(get_ledger),
):
    invoices = ledger.store.list_invoices(tenant_id=tenant_id, app_id=app_id)
    return [inv.to_dict() for inv in invoices]


@router.get("/{inv_id}", response_model=InvoiceResponseSchema)
def get_invoice(inv_id: str, ledger: Ledger = Depends(get_ledger)):
    inv = ledger.store.get_invoice(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv.to_dict()


@router.post("/{inv_id}/pay", response_model=InvoiceResponseSchema)
def mark_invoice_paid(
    inv_id: str,
    payment_ref: str = Query("", description="External payment reference"),
    ledger: Ledger = Depends(get_ledger),
):
    try:
        inv = ledger.mark_invoice_paid(inv_id, payment_ref=payment_ref)
        return inv.to_dict()
    except ErrNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{inv_id}/void", response_model=InvoiceResponseSchema)
def mark_invoice_voided(
    inv_id: str,
    reason: str = Query("operator void", description="Void reason"),
    ledger: Ledger = Depends(get_ledger),
):
    try:
        inv = ledger.mark_invoice_voided(inv_id, reason=reason)
        return inv.to_dict()
    except ErrNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
