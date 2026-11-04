"""
Entitlement check result model reproducing entitlement/models.go.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class EntitlementResult:
    allowed: bool
    feature: str
    used: int = 0
    limit: int = 0
    remaining: int = 0
    soft_limit: bool = False
    reason: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "allowed": self.allowed,
            "feature": self.feature,
            "used": self.used,
            "limit": self.limit,
            "remaining": self.remaining,
            "soft_limit": self.soft_limit,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> EntitlementResult:
        return cls(
            allowed=bool(d.get("allowed", False)),
            feature=d.get("feature", ""),
            used=int(d.get("used", 0)),
            limit=int(d.get("limit", 0)),
            remaining=int(d.get("remaining", 0)),
            soft_limit=bool(d.get("soft_limit", False)),
            reason=d.get("reason"),
        )
