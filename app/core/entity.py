"""
Base Entity timestamps replicating types/entity.go.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Entity:
    def __init__(self, created_at: datetime | None = None, updated_at: datetime | None = None) -> None:
        now = utc_now()
        self.created_at: datetime = created_at or now
        self.updated_at: datetime = updated_at or now

    def touch(self) -> None:
        self.updated_at = utc_now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
