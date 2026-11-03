"""
Standalone feature catalog domain models reproducing feature/models.go.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
from app.core.entity import Entity, utc_now
from app.core.id import new_id, PREFIX_FEATURE
from app.models.plan import FeatureType


@dataclass
class CatalogFeature(Entity):
    id: str = field(default_factory=lambda: new_id(PREFIX_FEATURE))
    key: str = ""
    name: str = ""
    description: str = ""
    type: FeatureType = FeatureType.BOOLEAN
    app_id: str = "default"
    is_global: bool = False
    status: str = "active"
    metadata: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "type": self.type.value if isinstance(self.type, FeatureType) else str(self.type),
            "app_id": self.app_id,
            "is_global": self.is_global,
            "status": self.status,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> CatalogFeature:
        c_at = datetime.fromisoformat(d["created_at"]) if "created_at" in d and isinstance(d["created_at"], str) else d.get("created_at")
        u_at = datetime.fromisoformat(d["updated_at"]) if "updated_at" in d and isinstance(d["updated_at"], str) else d.get("updated_at")
        return cls(
            id=d.get("id", new_id(PREFIX_FEATURE)),
            key=d.get("key", ""),
            name=d.get("name", ""),
            description=d.get("description", ""),
            type=FeatureType(d.get("type", FeatureType.BOOLEAN.value)),
            app_id=d.get("app_id", "default"),
            is_global=bool(d.get("is_global", False)),
            status=d.get("status", "active"),
            metadata=dict(d.get("metadata", {})),
            created_at=c_at or utc_now(),
            updated_at=u_at or utc_now(),
        )
