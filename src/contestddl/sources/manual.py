from __future__ import annotations

from pathlib import Path

import yaml

from contestddl.models import Event, SourceEvidence
from contestddl.sources.common import guarded
from contestddl.utils import iso, iso_or_none, now_china, stable_id


def collect(fetcher=None, now=None, path: str | Path = "data/manual.yml"):
    current = now or now_china()
    path = Path(path)

    def run():
        rows = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        events = []
        for row in rows:
            name = str(row["name"]).strip()
            event_type = row.get("event_type", "competition")
            official_url = row.get("official_url", "")
            checked_at = row.get("checked_at") or iso(current)
            source = SourceEvidence(row.get("source_name", "Maintainer reviewed"), row.get("source_url") or official_url, "manual_review", 5, checked_at, row.get("verified_fields", []))
            event = Event(
                id=row.get("id") or stable_id(name, event_type, row.get("competition_start") or row.get("registration_deadline"), "manual"),
                name=name, event_type=event_type, categories=row.get("categories", []), official_url=official_url,
                source=source, organizer=row.get("organizer", ""), level=row.get("level", ""), region=row.get("region", ""),
                location=row.get("location", ""), mode=row.get("mode", ""), eligibility=row.get("eligibility", ""),
                registration_start=iso_or_none(row.get("registration_start")), registration_deadline=iso_or_none(row.get("registration_deadline"), end_of_day=True),
                competition_start=iso_or_none(row.get("competition_start")), competition_end=iso_or_none(row.get("competition_end")),
                submission_deadline=iso_or_none(row.get("submission_deadline"), end_of_day=True),
                tags=row.get("tags", []), notes=row.get("notes", ""), confidence="high", verification_status="maintainer_reviewed",
            )
            events.append(event)
        return events

    return guarded("manual", "data/manual.yml", run)
