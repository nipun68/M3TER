"""
Schemas for Authentication and Users preserving Express.js/JWT.js contracts.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, EmailStr


class UserRegisterSchema(BaseModel):
    email: str
    password: str


class UserLoginSchema(BaseModel):
    email: str
    password: str


class UserLoginResponseSchema(BaseModel):
    message: str
    token: str


class UserProfileResponseSchema(BaseModel):
    message: str
    user: dict
