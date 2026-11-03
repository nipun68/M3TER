"""
Authentication, password hashing, JWT, and webhook security.
Backward-compatible with Express.js/JWT.js and bcrypt1.js while providing
production-grade security standards.
"""
from __future__ import annotations
import hmac
import hashlib
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
import bcrypt
import jwt


DEFAULT_SECRET_KEY = "PASSKEY"  # Preserved from Express.js/JWT.js
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash password using bcrypt (10 rounds, identical to Express.js)."""
    salt = bcrypt.gensalt(rounds=10)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(
    data: Dict[str, Any],
    secret_key: str = DEFAULT_SECRET_KEY,
    expires_delta: Optional[timedelta] = None
) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=10)  # Preserved from Express.js: 10h
    to_encode.update({"exp": int(expire.timestamp())})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str, secret_key: str = DEFAULT_SECRET_KEY) -> Dict[str, Any]:
    try:
        decoded = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        return decoded
    except jwt.PyJWTError as e:
        raise ValueError(f"Invalid or expired token: {e}") from e


def verify_stripe_webhook_signature(
    payload: bytes,
    signature_header: str,
    webhook_secret: str,
    tolerance_seconds: int = 300
) -> bool:
    """
    Verify Stripe webhook signature header 't=...,v1=...'.
    Prevents replay attacks within tolerance_seconds.
    """
    if not signature_header or not webhook_secret:
        return False
    parts = {}
    for item in signature_header.split(","):
        if "=" in item:
            k, v = item.strip().split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    signature = parts.get("v1")
    if not timestamp or not signature:
        return False

    try:
        ts = int(timestamp)
    except ValueError:
        return False

    current_ts = int(time.time())
    if abs(current_ts - ts) > tolerance_seconds:
        return False

    signed_payload = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(webhook_secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
