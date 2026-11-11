"""
Authentication routes replicating Express.js/JWT.js and bcrypt1.js exactly.
Preserves /register, /login, /profile, /account endpoints and contracts.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from app.api.dependencies import get_store, get_current_user
from app.config.settings import settings
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User
from app.repositories.base import BaseStore
from app.schemas.user import (
    UserRegisterSchema,
    UserLoginSchema,
    UserLoginResponseSchema,
    UserProfileResponseSchema,
)

router = APIRouter(tags=["Authentication"])


@router.post("/register", status_code=status.HTTP_200_OK)
def register_user(data: UserRegisterSchema, store: BaseStore = Depends(get_store)):
    if not data.email or not data.password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    existing = store.get_user_by_email(data.email)
    hashed_pw = hash_password(data.password)

    if existing:
        existing.userpassword = hashed_pw
        store.create_user(existing)
    else:
        user = User(useremail=data.email, userpassword=hashed_pw)
        store.create_user(user)

    return {
        "message": "User registered successfully",
        "email": data.email,
    }


@router.post("/login", response_model=UserLoginResponseSchema)
def login_user(data: UserLoginSchema, store: BaseStore = Depends(get_store)):
    if not data.email or not data.password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    user = store.get_user_by_email(data.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(data.password, user.userpassword):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(
        data={"email": user.useremail},
        secret_key=settings.JWT_SECRET_KEY,
    )

    return UserLoginResponseSchema(
        message="User logged in successfully",
        token=token,
    )


@router.get("/profile", response_model=UserProfileResponseSchema)
def get_profile(current_user: dict = Depends(get_current_user)):
    return UserProfileResponseSchema(
        message="Profile Page",
        user=current_user,
    )


@router.get("/account")
def get_account(current_user: dict = Depends(get_current_user)):
    return {"message": "Welcome to account page"}
