"""
Coupons API routes.
"""
from __future__ import annotations
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.api.dependencies import get_ledger
from app.core.exceptions import ErrAlreadyExists, ErrNotFound, ErrCouponInvalid
from app.core.money import Money
from app.models.coupon import Coupon, CouponType
from app.services.ledger import Ledger
from app.schemas.coupon import CouponCreateSchema, CouponApplySchema, CouponResponseSchema

router = APIRouter(prefix="/coupons", tags=["Coupons & Discounts"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CouponResponseSchema)
def create_coupon(data: CouponCreateSchema, ledger: Ledger = Depends(get_ledger)):
    try:
        amt = Money(data.amount.amount, data.amount.currency or data.currency) if data.amount else Money(0, data.currency)
        v_from = datetime.fromisoformat(data.valid_from) if data.valid_from else None
        v_until = datetime.fromisoformat(data.valid_until) if data.valid_until else None

        c = Coupon(
            code=data.code.strip().upper(),
            name=data.name,
            type=CouponType(data.type),
            amount=amt,
            percentage=data.percentage,
            currency=data.currency.lower(),
            max_redemptions=data.max_redemptions,
            valid_from=v_from,
            valid_until=v_until,
            app_id=data.app_id,
            metadata=data.metadata,
        )
        saved = ledger.create_coupon(c)
        return saved.to_dict()
    except ErrAlreadyExists as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[CouponResponseSchema])
def list_coupons(app_id: str = Query("default"), ledger: Ledger = Depends(get_ledger)):
    coupons = ledger.store.list_coupons(app_id=app_id)
    return [c.to_dict() for c in coupons]


@router.post("/apply")
def apply_coupon(data: CouponApplySchema, ledger: Ledger = Depends(get_ledger)):
    try:
        ledger.apply_coupon(sub_id=data.subscription_id, coupon_code=data.code, app_id=data.app_id)
        return {"message": f"Coupon {data.code} applied successfully to subscription {data.subscription_id}"}
    except ErrNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ErrCouponInvalid as e:
        raise HTTPException(status_code=400, detail=str(e))
