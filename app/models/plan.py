"""
Billing Plan domain models reproducing plan/models.go.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from app.core.entity import Entity, utc_now
from app.core.money import Money, zero
from app.core.id import new_id, PREFIX_PLAN, PREFIX_FEATURE, PREFIX_PRICE


class PlanStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DRAFT = "draft"


class Period(str, Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"
    NONE = "none"


class FeatureType(str, Enum):
    METERED = "metered"
    BOOLEAN = "boolean"
    SEAT = "seat"


class TierType(str, Enum):
    GRADUATED = "graduated"
    VOLUME = "volume"
    FLAT = "flat"


@dataclass
class PriceTier:
    feature_key: str
    type: TierType
    up_to: int  # <= 0 means unbounded
    unit_amount: Money = field(default_factory=lambda: zero("usd"))
    flat_amount: Money = field(default_factory=lambda: zero("usd"))
    priority: int = 0

    def to_dict(self) -> Dict:
        return {
            "feature_key": self.feature_key,
            "type": self.type.value if isinstance(self.type, TierType) else str(self.type),
            "up_to": self.up_to,
            "unit_amount": self.unit_amount.to_dict(),
            "flat_amount": self.flat_amount.to_dict(),
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, d: Dict, default_currency: str = "usd") -> PriceTier:
        t_type = TierType(d.get("type", TierType.GRADUATED.value))
        unit = d.get("unit_amount")
        flat = d.get("flat_amount")
        unit_m = Money.from_dict(unit) if isinstance(unit, dict) else zero(default_currency)
        flat_m = Money.from_dict(flat) if isinstance(flat, dict) else zero(default_currency)
        return cls(
            feature_key=d.get("feature_key", ""),
            type=t_type,
            up_to=int(d.get("up_to", 0)),
            unit_amount=unit_m,
            flat_amount=flat_m,
            priority=int(d.get("priority", 0)),
        )


@dataclass
class CreditPool:
    key: str
    amount: Money
    feature_keys: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "key": self.key,
            "amount": self.amount.to_dict(),
            "feature_keys": self.feature_keys,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> CreditPool:
        return cls(
            key=d.get("key", ""),
            amount=Money.from_dict(d.get("amount", {})),
            feature_keys=list(d.get("feature_keys", [])),
        )


@dataclass
class PlanFeature(Entity):
    id: str = field(default_factory=lambda: new_id(PREFIX_FEATURE))
    catalog_id: Optional[str] = None
    key: str = ""
    name: str = ""
    type: FeatureType = FeatureType.BOOLEAN
    limit: int = 0  # -1 means unlimited
    period: Period = Period.MONTHLY
    soft_limit: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "catalog_id": self.catalog_id,
            "key": self.key,
            "name": self.name,
            "type": self.type.value if isinstance(self.type, FeatureType) else str(self.type),
            "limit": self.limit,
            "period": self.period.value if isinstance(self.period, Period) else str(self.period),
            "soft_limit": self.soft_limit,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> PlanFeature:
        c_at = datetime.fromisoformat(d["created_at"]) if "created_at" in d and isinstance(d["created_at"], str) else d.get("created_at")
        u_at = datetime.fromisoformat(d["updated_at"]) if "updated_at" in d and isinstance(d["updated_at"], str) else d.get("updated_at")
        return cls(
            id=d.get("id", new_id(PREFIX_FEATURE)),
            catalog_id=d.get("catalog_id"),
            key=d.get("key", ""),
            name=d.get("name", ""),
            type=FeatureType(d.get("type", FeatureType.BOOLEAN.value)),
            limit=int(d.get("limit", 0)),
            period=Period(d.get("period", Period.MONTHLY.value)),
            soft_limit=bool(d.get("soft_limit", False)),
            metadata=dict(d.get("metadata", {})),
            created_at=c_at or utc_now(),
            updated_at=u_at or utc_now(),
        )


@dataclass
class Pricing(Entity):
    id: str = field(default_factory=lambda: new_id(PREFIX_PRICE))
    plan_id: str = ""
    base_amount: Money = field(default_factory=lambda: zero("usd"))
    billing_period: Period = Period.MONTHLY
    tiers: List[PriceTier] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "base_amount": self.base_amount.to_dict(),
            "billing_period": self.billing_period.value if isinstance(self.billing_period, Period) else str(self.billing_period),
            "tiers": [t.to_dict() for t in self.tiers],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> Pricing:
        c_at = datetime.fromisoformat(d["created_at"]) if "created_at" in d and isinstance(d["created_at"], str) else d.get("created_at")
        u_at = datetime.fromisoformat(d["updated_at"]) if "updated_at" in d and isinstance(d["updated_at"], str) else d.get("updated_at")
        base_amount = Money.from_dict(d.get("base_amount", {}))
        tiers = [PriceTier.from_dict(t, base_amount.currency) for t in d.get("tiers", [])]
        return cls(
            id=d.get("id", new_id(PREFIX_PRICE)),
            plan_id=d.get("plan_id", ""),
            base_amount=base_amount,
            billing_period=Period(d.get("billing_period", Period.MONTHLY.value)),
            tiers=tiers,
            created_at=c_at or utc_now(),
            updated_at=u_at or utc_now(),
        )


@dataclass
class Plan(Entity):
    id: str = field(default_factory=lambda: new_id(PREFIX_PLAN))
    name: str = ""
    slug: str = ""
    description: str = ""
    currency: str = "usd"
    status: PlanStatus = PlanStatus.ACTIVE
    trial_days: int = 0
    features: List[PlanFeature] = field(default_factory=list)
    pricing: Optional[Pricing] = None
    credits: List[CreditPool] = field(default_factory=list)
    app_id: str = "default"
    provider_id: Optional[str] = None
    provider_name: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def find_feature(self, key: str) -> Optional[PlanFeature]:
        for f in self.features:
            if f.key == key:
                return f
        return None

    def allows(self, feature_key: str, current_usage: int) -> bool:
        f = self.find_feature(feature_key)
        if f is None:
            return False
        if f.type == FeatureType.BOOLEAN:
            return f.limit > 0
        if f.limit == -1:
            return True
        if current_usage < f.limit:
            return True
        return f.soft_limit

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "currency": self.currency,
            "status": self.status.value if isinstance(self.status, PlanStatus) else str(self.status),
            "trial_days": self.trial_days,
            "features": [f.to_dict() for f in self.features],
            "pricing": self.pricing.to_dict() if self.pricing else None,
            "credits": [c.to_dict() for c in self.credits],
            "app_id": self.app_id,
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> Plan:
        c_at = datetime.fromisoformat(d["created_at"]) if "created_at" in d and isinstance(d["created_at"], str) else d.get("created_at")
        u_at = datetime.fromisoformat(d["updated_at"]) if "updated_at" in d and isinstance(d["updated_at"], str) else d.get("updated_at")
        pricing = Pricing.from_dict(d["pricing"]) if d.get("pricing") else None
        features = [PlanFeature.from_dict(f) for f in d.get("features", [])]
        credits = [CreditPool.from_dict(c) for c in d.get("credits", [])]
        return cls(
            id=d.get("id", new_id(PREFIX_PLAN)),
            name=d.get("name", ""),
            slug=d.get("slug", ""),
            description=d.get("description", ""),
            currency=d.get("currency", "usd").lower(),
            status=PlanStatus(d.get("status", PlanStatus.ACTIVE.value)),
            trial_days=int(d.get("trial_days", 0)),
            features=features,
            pricing=pricing,
            credits=credits,
            app_id=d.get("app_id", "default"),
            provider_id=d.get("provider_id"),
            provider_name=d.get("provider_name"),
            metadata=dict(d.get("metadata", {})),
            created_at=c_at or utc_now(),
            updated_at=u_at or utc_now(),
        )
