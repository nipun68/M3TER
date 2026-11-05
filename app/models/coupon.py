"""
Coupon and CouponApplication domain models reproducing coupon/models.go.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional
from app.core.entity import Entity, utc_now
from app.core.id import new_id, PREFIX_COUPON, PREFIX_COUPON_APP
from app.core.money import Money, zero


class CouponType(str, Enum):
    PERCENTAGE = "percentage"
    AMOUNT = "amount"


@dataclass
class Coupon(Entity):
    id: str = field(default_factory=lambda: new_id(PREFIX_COUPON))
    code: str = ""
    name: str = ""
    type: CouponType = CouponType.PERCENTAGE
    amount: Money = field(default_factory=lambda: zero("usd"))
    percentage: int = 0
    currency: str = "usd"
    max_redemptions: int = 0  # <= 0 means unlimited
    times_redeemed: int = 0
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    app_id: str = "default"
    metadata: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def is_valid(self, now: Optional[datetime] = None) -> bool:
        n = now or utc_now()
        if self.valid_from and n < self.valid_from:
            return False
        if self.valid_until and n > self.valid_until:
            return False
        if self.max_redemptions > 0 and self.times_redeemed >= self.max_redemptions:
            return False
        return True

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "type": self.type.value if isinstance(self.type, CouponType) else str(self.type),
            "amount": self.amount.to_dict(),
            "percentage": self.percentage,
            "currency": self.currency,
            "max_redemptions": self.max_redemptions,
            "times_redeemed": self.times_redeemed,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "app_id": self.app_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> Coupon:
        def parse_dt(v):
            if v is None:
                return None
            return datetime.fromisoformat(v) if isinstance(v, str) else v

        amt = d.get("amount")
        return cls(
            id=d.get("id", new_id(PREFIX_COUPON)),
            code=d.get("code", "").strip().upper(),
            name=d.get("name", ""),
            type=CouponType(d.get("type", CouponType.PERCENTAGE.value)),
            amount=Money.from_dict(amt) if isinstance(amt, dict) else zero(d.get("currency", "usd")),
            percentage=int(d.get("percentage", 0)),
            currency=d.get("currency", "usd").lower(),
            max_redemptions=int(d.get("max_redemptions", 0)),
            times_redeemed=int(d.get("times_redeemed", 0)),
            valid_from=parse_dt(d.get("valid_from")),
            valid_until=parse_dt(d.get("valid_until")),
            app_id=d.get("app_id", "default"),
            metadata=dict(d.get("metadata", {})),
            created_at=parse_dt(d.get("created_at")) or utc_now(),
            updated_at=parse_dt(d.get("updated_at")) or utc_now(),
        )


@dataclass
class CouponApplication:
    id: str = field(default_factory=lambda: new_id(PREFIX_COUPON_APP))
    coupon_id: str = ""
    subscription_id: str = ""
    applied_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "coupon_id": self.coupon_id,
            "subscription_id": self.subscription_id,
            "applied_at": self.applied_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> CouponApplication:
        at = datetime.fromisoformat(d["applied_at"]) if isinstance(d.get("applied_at"), str) else d.get("applied_at")
        return cls(
            id=d.get("id", new_id(PREFIX_COUPON_APP)),
            coupon_id=d.get("coupon_id", ""),
            subscription_id=d.get("subscription_id", ""),
            applied_at=at or utc_now(),
        )
