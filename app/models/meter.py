"""
Usage metering models reproducing meter/models.go.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
from app.core.entity import utc_now
from app.core.id import new_id, PREFIX_USAGE_EVENT


@dataclass
class UsageEvent:
    id: str = field(default_factory=lambda: new_id(PREFIX_USAGE_EVENT))
    tenant_id: str = ""
    app_id: str = "default"
    feature_key: str = ""
    quantity: int = 1
    timestamp: datetime = field(default_factory=utc_now)
    idempotency_key: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "app_id": self.app_id,
            "feature_key": self.feature_key,
            "quantity": self.quantity,
            "timestamp": self.timestamp.isoformat(),
            "idempotency_key": self.idempotency_key,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> UsageEvent:
        ts = datetime.fromisoformat(d["timestamp"]) if isinstance(d.get("timestamp"), str) else d.get("timestamp")
        return cls(
            id=d.get("id", new_id(PREFIX_USAGE_EVENT)),
            tenant_id=d.get("tenant_id", ""),
            app_id=d.get("app_id", "default"),
            feature_key=d.get("feature_key", ""),
            quantity=int(d.get("quantity", 1)),
            timestamp=ts or utc_now(),
            idempotency_key=d.get("idempotency_key"),
            metadata=dict(d.get("metadata", {})),
        )
