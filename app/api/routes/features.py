"""
Feature Catalog API routes.
"""
from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.api.dependencies import get_ledger
from app.core.exceptions import ErrAlreadyExists, ErrFeatureNotFound
from app.models.feature import CatalogFeature
from app.models.plan import FeatureType
from app.services.ledger import Ledger
from app.schemas.feature import FeatureCreateSchema, FeatureResponseSchema

router = APIRouter(prefix="/features", tags=["Feature Catalog"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=FeatureResponseSchema)
def create_feature(data: FeatureCreateSchema, ledger: Ledger = Depends(get_ledger)):
    try:
        f = CatalogFeature(
            key=data.key,
            name=data.name,
            description=data.description,
            type=FeatureType(data.type),
            app_id=data.app_id,
            is_global=data.is_global,
            metadata=data.metadata,
        )
        saved = ledger.create_feature(f)
        return saved.to_dict()
    except ErrAlreadyExists as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[FeatureResponseSchema])
def list_features(app_id: str = Query("default"), ledger: Ledger = Depends(get_ledger)):
    features = ledger.list_features(app_id=app_id)
    return [f.to_dict() for f in features]


@router.get("/{feature_id}", response_model=FeatureResponseSchema)
def get_feature(feature_id: str, ledger: Ledger = Depends(get_ledger)):
    f = ledger.get_feature(feature_id)
    if not f:
        f = ledger.get_feature_by_key(feature_id)
    if not f:
        raise HTTPException(status_code=404, detail="Feature not found")
    return f.to_dict()


@router.delete("/{feature_id}")
def delete_feature(feature_id: str, ledger: Ledger = Depends(get_ledger)):
    try:
        ledger.delete_feature(feature_id)
        return {"message": "Feature deleted successfully"}
    except ErrFeatureNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
