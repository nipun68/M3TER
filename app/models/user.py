"""
User model preserving existing Express.js/JWT.js authentication functionality.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict
import uuid
from app.core.entity import utc_now


@dataclass
class User:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    useremail: str = ""
    userpassword: str = ""
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "useremail": self.useremail,
            "userpassword": self.userpassword,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> User:
        c_at = datetime.fromisoformat(d["created_at"]) if "created_at" in d and isinstance(d["created_at"], str) else d.get("created_at")
        return cls(
            id=str(d.get("_id") or d.get("id") or uuid.uuid4()),
            useremail=str(d.get("useremail", "")).strip().lower(),
            userpassword=str(d.get("userpassword", "")),
            created_at=c_at or utc_now(),
        )
