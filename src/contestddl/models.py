from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class SourceEvidence:
    name: str
    url: str
    source_type: str
    authority: int
    checked_at: str
    fields: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Event:
    id: str
    name: str
    event_type: str
    categories: list[str]
    official_url: str
    source: SourceEvidence
    organizer: str = ""
    level: str = ""
    region: str = ""
    location: str = ""
    mode: str = ""
    eligibility: str = ""
    registration_start: str | None = None
    registration_deadline: str | None = None
    competition_start: str | None = None
    competition_end: str | None = None
    abstract_deadline: str | None = None
    submission_deadline: str | None = None
    primary_deadline: str | None = None
    status: str = "unknown"
    confidence: str = "medium"
    verification_status: str = "single_source"
    tags: list[str] = field(default_factory=list)
    university_tiers: list[str] = field(default_factory=list)
    notes: str = ""
    description: str = ""
    schedule: list[dict[str, str]] = field(default_factory=list)
    attachments: list[dict[str, str]] = field(default_factory=list)
    image_url: str = ""
    catalog_listed: bool = False
    catalog_name: str = ""
    catalog_reference_url: str = ""
    first_seen_at: str = ""
    last_seen_at: str = ""
    stale: bool = False
    archived: bool = False
    sources: list[SourceEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source"] = asdict(self.source)
        payload["sources"] = [asdict(item) for item in self.sources or [self.source]]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Event":
        values = dict(payload)
        values["source"] = SourceEvidence(**values["source"])
        values["sources"] = [SourceEvidence(**item) for item in values.get("sources", [])]
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in values.items() if key in allowed})


@dataclass(slots=True)
class SourceResult:
    name: str
    ok: bool
    events: list[Event] = field(default_factory=list)
    error: str = ""
    fetched_at: str = ""
    url: str = ""
    duration_ms: int = 0
    details: dict[str, Any] = field(default_factory=dict)
