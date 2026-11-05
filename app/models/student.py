"""
Student model preserving existing Mongodb/student.js functionality.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
import uuid
from app.core.entity import utc_now


@dataclass
class Student:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    age: int = 0
    grade: str = ""
    city: str = "Not Provided"
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "_id": self.id,
            "name": self.name,
            "age": self.age,
            "grade": self.grade,
            "city": self.city,
            "createdAt": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> Student:
        c_at = None
        if "createdAt" in d:
            c_at = datetime.fromisoformat(d["createdAt"]) if isinstance(d["createdAt"], str) else d["createdAt"]
        elif "created_at" in d:
            c_at = datetime.fromisoformat(d["created_at"]) if isinstance(d["created_at"], str) else d["created_at"]
        doc_id = str(d.get("_id") or d.get("id") or uuid.uuid4())
        return cls(
            id=doc_id,
            name=str(d.get("name", "")).strip(),
            age=int(d.get("age", 0)),
            grade=str(d.get("grade", "")).strip().upper(),
            city=str(d.get("city", "Not Provided")).strip(),
            created_at=c_at or utc_now(),
        )
