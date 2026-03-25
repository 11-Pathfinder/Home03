"""Property data model."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import date


@dataclass
class Property:
    address: str
    price: int
    url: str
    agent: str
    bedrooms: int | None = None
    bathrooms: int | None = None
    property_type: str | None = None
    image_url: str | None = None
    description: str | None = None
    lat: float | None = None
    lng: float | None = None
    first_seen: str = field(default_factory=lambda: date.today().isoformat())
    id: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = hashlib.md5(f"{self.agent}:{self.url}".encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Property":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
