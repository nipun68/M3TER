"""
Administrative lifecycle clock control API routes.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from app.api.dependencies import get_ledger
from app.services.ledger import Ledger

router = APIRouter(prefix="/lifecycle", tags=["Lifecycle Clock"])


@router.post("/advance")
def advance_lifecycle(
    now: Optional[str] = Query(None, description="ISO timestamp to advance to; defaults to server time"),
    ledger: Ledger = Depends(get_ledger),
):
    dt = datetime.fromisoformat(now) if now else None
    report = ledger.lifecycle_engine.advance(dt)
    return {
        "periods_advanced": report.periods_advanced,
        "cancels_enacted": report.cancels_enacted,
        "trials_ended": report.trials_ended,
        "invoices_past_due": report.invoices_past_due,
        "is_empty": report.is_empty,
    }
