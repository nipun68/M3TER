"""
Schemas for Student model preserving Mongodb/server.js API contracts.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class StudentCreateSchema(BaseModel):
    name: str = Field(..., min_length=1)
    age: int = Field(..., ge=0)
    grade: str = Field(..., min_length=1)
    city: Optional[str] = "Not Provided"


class StudentUpdateSchema(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=0)
    grade: Optional[str] = None
    city: Optional[str] = None


class StudentResponseSchema(BaseModel):
    id: str
    name: str
    age: int
    grade: str
    city: str
    createdAt: str
