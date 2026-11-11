"""
Stripe and external payment provider webhook ingress.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from app.api.dependencies import get_ledger
from app.services.ledger import Ledger

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    ledger: Ledger = Depends(get_ledger),
):
    prov = ledger.get_provider("stripe")
    if not prov:
        raise HTTPException(status_code=503, detail="Stripe provider not registered")

    payload = await request.body()
    res = prov.handle_webhook(payload, signature_header=stripe_signature)

    if res.error:
        raise HTTPException(status_code=400, detail=res.error)

    if res.handled and res.entity_type == "invoice" and res.event_type == "invoice.paid" and res.entity_id:
        # Mark local invoice paid
        ledger.mark_invoice_paid(res.entity_id, payment_ref=res.provider_id)

    return res.to_dict()
