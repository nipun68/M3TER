"""
Plans API routes.
"""
from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.api.dependencies import get_ledger, resolve_tenant
from app.core.exceptions import ErrAlreadyExists, ErrPlanNotFound
from app.models.plan import Plan, PlanFeature, Pricing, PriceTier, CreditPool, FeatureType, Period, TierType, PlanStatus
from app.core.money import Money
from app.services.ledger import Ledger
from app.schemas.plan import PlanCreateSchema, PlanResponseSchema

router = APIRouter(prefix="/plans", tags=["Billing Plans"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PlanResponseSchema)
def create_plan(data: PlanCreateSchema, ledger: Ledger = Depends(get_ledger)):
    try:
        # Convert schema to domain models
        features = [
            PlanFeature(
                catalog_id=f.catalog_id,
                key=f.key,
                name=f.name,
                type=FeatureType(f.type),
                limit=f.limit,
                period=Period(f.period),
                soft_limit=f.soft_limit,
                metadata=f.metadata,
            )
            for f in data.features
        ]
        pricing = None
        if data.pricing:
            base_amt = Money(data.pricing.base_amount.amount, data.pricing.base_amount.currency or data.currency)
            tiers = [
                PriceTier(
                    feature_key=t.feature_key,
                    type=TierType(t.type),
                    up_to=t.up_to,
                    unit_amount=Money(t.unit_amount.amount, t.unit_amount.currency or data.currency),
                    flat_amount=Money(t.flat_amount.amount, t.flat_amount.currency or data.currency),
                    priority=t.priority,
                )
                for t in data.pricing.tiers
            ]
            pricing = Pricing(
                base_amount=base_amt,
                billing_period=Period(data.pricing.billing_period),
                tiers=tiers,
            )

        credits = [
            CreditPool(
                key=c.key,
                amount=Money(c.amount.amount, c.amount.currency or data.currency),
                feature_keys=c.feature_keys,
            )
            for c in data.credits
        ]

        plan = Plan(
            name=data.name,
            slug=data.slug,
            description=data.description,
            currency=data.currency.lower(),
            trial_days=data.trial_days,
            features=features,
            pricing=pricing,
            credits=credits,
            app_id=data.app_id,
            metadata=data.metadata,
        )
        saved = ledger.create_plan(plan)
        return saved.to_dict()
    except ErrAlreadyExists as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[PlanResponseSchema])
def list_plans(
    app_id: str = Query("default"),
    status: Optional[str] = Query(None),
    ledger: Ledger = Depends(get_ledger),
):
    plans = ledger.list_plans(app_id=app_id, status=status)
    return [p.to_dict() for p in plans]


@router.get("/{plan_id}", response_model=PlanResponseSchema)
def get_plan(plan_id: str, ledger: Ledger = Depends(get_ledger)):
    p = ledger.get_plan(plan_id)
    if not p:
        p = ledger.get_plan_by_slug(plan_id)
    if not p:
        raise HTTPException(status_code=404, detail="Plan not found")
    return p.to_dict()


@router.post("/{plan_id}/activate", response_model=PlanResponseSchema)
def activate_plan(plan_id: str, ledger: Ledger = Depends(get_ledger)):
    try:
        p = ledger.activate_plan(plan_id)
        return p.to_dict()
    except ErrPlanNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{plan_id}/archive")
def archive_plan(plan_id: str, ledger: Ledger = Depends(get_ledger)):
    try:
        ledger.archive_plan(plan_id)
        return {"message": "Plan archived successfully"}
    except ErrPlanNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{plan_id}")
def delete_plan(plan_id: str, ledger: Ledger = Depends(get_ledger)):
    try:
        ledger.delete_plan(plan_id)
        return {"message": "Plan deleted successfully"}
    except ErrPlanNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
