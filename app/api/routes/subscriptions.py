"""
Subscription Management API routes.
"""
from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.api.dependencies import get_ledger, resolve_tenant
from app.core.exceptions import (
    ErrPlanNotFound,
    ErrPlanArchived,
    ErrSubscriptionNotFound,
    ErrSubscriptionCanceled,
    ErrInvalidInput,
)
from app.services.ledger import Ledger
from app.schemas.subscription import (
    SubscriptionCreateSchema,
    SubscriptionChangePlanSchema,
    SubscriptionResponseSchema,
)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SubscriptionResponseSchema)
def create_subscription(
    data: SubscriptionCreateSchema,
    ledger: Ledger = Depends(get_ledger),
):
    try:
        sub = ledger.create_subscription(
            tenant_id=data.tenant_id,
            plan_id=data.plan_id,
            app_id=data.app_id,
            quantity=data.quantity,
            trial_days=data.trial_days,
            metadata=data.metadata,
        )
        return sub.to_dict()
    except (ErrPlanNotFound, ErrPlanArchived) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[SubscriptionResponseSchema])
def list_subscriptions(
    tenant_id: Optional[str] = Query(None),
    app_id: str = Query("default"),
    ledger: Ledger = Depends(get_ledger),
):
    subs = ledger.list_subscriptions(tenant_id=tenant_id, app_id=app_id)
    return [s.to_dict() for s in subs]


@router.get("/{sub_id}", response_model=SubscriptionResponseSchema)
def get_subscription(sub_id: str, ledger: Ledger = Depends(get_ledger)):
    s = ledger.get_subscription(sub_id)
    if not s:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return s.to_dict()


@router.post("/{sub_id}/change-plan", response_model=SubscriptionResponseSchema)
def change_plan(
    sub_id: str,
    data: SubscriptionChangePlanSchema,
    ledger: Ledger = Depends(get_ledger),
):
    try:
        sub = ledger.change_plan(sub_id=sub_id, new_plan_id=data.plan_id, quantity=data.quantity)
        return sub.to_dict()
    except ErrSubscriptionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ErrPlanNotFound, ErrSubscriptionCanceled) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{sub_id}/pause", response_model=SubscriptionResponseSchema)
def pause_subscription(sub_id: str, ledger: Ledger = Depends(get_ledger)):
    try:
        sub = ledger.pause_subscription(sub_id)
        return sub.to_dict()
    except ErrSubscriptionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ErrInvalidInput as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{sub_id}/resume", response_model=SubscriptionResponseSchema)
def resume_subscription(sub_id: str, ledger: Ledger = Depends(get_ledger)):
    try:
        sub = ledger.resume_subscription(sub_id)
        return sub.to_dict()
    except ErrSubscriptionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ErrInvalidInput as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{sub_id}/cancel", response_model=SubscriptionResponseSchema)
def cancel_subscription(
    sub_id: str,
    immediately: bool = Query(False),
    ledger: Ledger = Depends(get_ledger),
):
    try:
        sub = ledger.cancel_subscription(sub_id, immediately=immediately)
        return sub.to_dict()
    except ErrSubscriptionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
