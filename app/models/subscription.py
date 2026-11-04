"""
Subscription domain models replicating subscription/models.go.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from app.core.entity import Entity, utc_now
from app.core.id import new_id, PREFIX_SUBSCRIPTION


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"
    PAUSED = "paused"


@dataclass
class BillingPeriod:
    start: datetime
    end: datetime

    def to_dict(self) -> Dict:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> BillingPeriod:
        s = datetime.fromisoformat(d["start"]) if isinstance(d["start"], str) else d["start"]
        e = datetime.fromisoformat(d["end"]) if isinstance(d["end"], str) else d["end"]
        return cls(start=s, end=e)


@dataclass
class Stretch:
    start: datetime
    end: datetime
    original_end: datetime
    floor: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "original_end": self.original_end.isoformat(),
            "floor": self.floor.isoformat() if self.floor else None,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> Stretch:
        s = datetime.fromisoformat(d["start"]) if isinstance(d["start"], str) else d["start"]
        e = datetime.fromisoformat(d["end"]) if isinstance(d["end"], str) else d["end"]
        oe = datetime.fromisoformat(d["original_end"]) if isinstance(d["original_end"], str) else d["original_end"]
        fl = None
        if d.get("floor"):
            fl = datetime.fromisoformat(d["floor"]) if isinstance(d["floor"], str) else d["floor"]
        return cls(start=s, end=e, original_end=oe, floor=fl)


@dataclass
class Resume:
    paused_at: Optional[datetime]
    status: SubscriptionStatus
    period_end: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    stretch: Optional[Stretch] = None


@dataclass
class Renewal:
    subscription: Subscription
    ended: List[BillingPeriod]


@dataclass
class Subscription(Entity):
    id: str = field(default_factory=lambda: new_id(PREFIX_SUBSCRIPTION))
    tenant_id: str = ""
    plan_id: str = ""
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    current_period_start: datetime = field(default_factory=utc_now)
    current_period_end: datetime = field(default_factory=utc_now)
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    cancel_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    stretch: Optional[Stretch] = None
    app_id: str = "default"
    provider_id: Optional[str] = None
    provider_name: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    quantity: Dict[str, int] = field(default_factory=dict)  # Feature key -> count (e.g. seats)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "plan_id": self.plan_id,
            "status": self.status.value if isinstance(self.status, SubscriptionStatus) else str(self.status),
            "current_period_start": self.current_period_start.isoformat(),
            "current_period_end": self.current_period_end.isoformat(),
            "trial_start": self.trial_start.isoformat() if self.trial_start else None,
            "trial_end": self.trial_end.isoformat() if self.trial_end else None,
            "canceled_at": self.canceled_at.isoformat() if self.canceled_at else None,
            "cancel_at": self.cancel_at.isoformat() if self.cancel_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "paused_at": self.paused_at.isoformat() if self.paused_at else None,
            "stretch": self.stretch.to_dict() if self.stretch else None,
            "app_id": self.app_id,
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "metadata": self.metadata,
            "quantity": self.quantity,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> Subscription:
        def parse_dt(v):
            if v is None:
                return None
            return datetime.fromisoformat(v) if isinstance(v, str) else v

        stretch = Stretch.from_dict(d["stretch"]) if d.get("stretch") else None
        return cls(
            id=d.get("id", new_id(PREFIX_SUBSCRIPTION)),
            tenant_id=d.get("tenant_id", ""),
            plan_id=d.get("plan_id", ""),
            status=SubscriptionStatus(d.get("status", SubscriptionStatus.ACTIVE.value)),
            current_period_start=parse_dt(d.get("current_period_start")) or utc_now(),
            current_period_end=parse_dt(d.get("current_period_end")) or utc_now(),
            trial_start=parse_dt(d.get("trial_start")),
            trial_end=parse_dt(d.get("trial_end")),
            canceled_at=parse_dt(d.get("canceled_at")),
            cancel_at=parse_dt(d.get("cancel_at")),
            ended_at=parse_dt(d.get("ended_at")),
            paused_at=parse_dt(d.get("paused_at")),
            stretch=stretch,
            app_id=d.get("app_id", "default"),
            provider_id=d.get("provider_id"),
            provider_name=d.get("provider_name"),
            metadata=dict(d.get("metadata", {})),
            quantity={k: int(v) for k, v in d.get("quantity", {}).items()},
            created_at=parse_dt(d.get("created_at")) or utc_now(),
            updated_at=parse_dt(d.get("updated_at")) or utc_now(),
        )
