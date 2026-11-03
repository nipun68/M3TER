"""
Pydantic schemas for Standalone Feature Catalog.
"""
from __future__ import annotations
from typing import Dict, Optional
from pydantic import BaseModel, Field


class FeatureCreateSchema(BaseModel):
    key: str
    name: str
    description: str = ""
    type: str = Field(default="boolean", description="metered, boolean, seat")
    app_id: str = "default"
    is_global: bool = False
    metadata: Dict[str, str] = Field(default_factory=dict)


class FeatureResponseSchema(BaseModel):
    id: str
    key: str
    name: str
    description: str
    type: str
    app_id: str
    is_global: bool
    status: str
    metadata: Dict[str, str]
    created_at: str
    updated_at: str
