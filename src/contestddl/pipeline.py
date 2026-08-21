from __future__ import annotations

import json
from dataclasses import fields
from datetime import timedelta
from pathlib import Path
from typing import Any

import yaml

from contestddl.fetch import Fetcher
from contestddl.models import Event, SourceEvidence, SourceResult
from contestddl.sources import codeforces, ctftime, hello_ctftime, manual, mlh, saikr, summer_camps
from contestddl.utils import (
    canonical_url,
    choose_primary_deadline,
    compute_status,
    iso,
    normalize_title,
    now_china,
    parse_datetime,
)

SCHEMA_VERSION = "1.0"
SOURCE_ADAPTERS = {
    "manual": manual.collect,
    "saikr": saikr.collect,
    "ctftime": ctftime.collect,
    "hello_ctftime_cn": hello_ctftime.collect,
    "codeforces": codeforces.collect,
    "mlh": mlh.collect,
    "cs_baoyan": summer_camps.collect,
}

MERGE_FIELDS = (
    "organizer", "level", "region", "location", "mode", "eligibility",
    "registration_start", "registration_deadline", "competition_start",
    "competition_end", "submission_deadline", "notes",
)
DATE_FIELDS = (
    "registration_start", "registration_deadline", "competition_start",
    "competition_end", "submission_deadline",
)


def _dedup_key(event: Event) -> str:
    title = normalize_title(event.name)
    date = parse_datetime(event.competition_start or event.registration_deadline or event.submission_deadline)
    year = date.year if date else ""
    if title:
        return f"title:{title}:{year}:{event.event_type}"
    return f"url:{canonical_url(event.official_url)}:{event.event_type}"


def _merge_events(events: list[Event], conflicts: list[dict]) -> list[Event]:
    grouped: dict[str, Event] = {}
    for event in sorted(events, key=lambda item: item.source.authority, reverse=True):
        key = _dedup_key(event)
        if key not in grouped:
            event.sources = [event.source]
            grouped[key] = event
            continue
        target = grouped[key]
        target.categories = list(dict.fromkeys([*target.categories, *event.categories]))
        target.tags = list(dict.fromkeys(filter(None, [*target.tags, *event.tags])))
        known_sources = {(item.name, canonical_url(item.url)) for item in target.sources}
        if (event.source.name, canonical_url(event.source.url)) not in known_sources:
            target.sources.append(event.source)
        for field_name in MERGE_FIELDS:
            existing = getattr(target, field_name)
            incoming = getattr(event, field_name)
            if not existing and incoming:
                setattr(target, field_name, incoming)
            elif field_name in DATE_FIELDS and existing and incoming and existing != incoming:
                conflicts.append({
                    "event": target.name, "field": field_name, "selected": existing,
                    "rejected": incoming, "selected_source": target.source.url,
                    "other_source": event.source.url,
                })
        if len(target.sources) >= 2 and len({canonical_url(item.url).split('/')[2] if '://' in canonical_url(item.url) else canonical_url(item.url) for item in target.sources}) >= 2:
            target.verification_status = "cross_source"
            target.confidence = "high"
    return list(grouped.values())


def _validate(event: Event, errors: list[dict], now) -> bool:
    if not event.name or not event.official_url.startswith(("http://", "https://")):
        errors.append({"event": event.name or event.id, "reason": "missing_name_or_http_url"})
        return False
    for field_name in DATE_FIELDS:
        value = getattr(event, field_name)
        if value and not parse_datetime(value):
            errors.append({"event": event.name, "field": field_name, "reason": "invalid_datetime", "value": value})
            setattr(event, field_name, None)
    start, end = parse_datetime(event.competition_start), parse_datetime(event.competition_end)
    reg_start, reg_end = parse_datetime(event.registration_start), parse_datetime(event.registration_deadline)
    if start and end and end < start:
        errors.append({"event": event.name, "reason": "competition_end_before_start"})
        event.competition_end = None
    if reg_start and reg_end and reg_end < reg_start:
        errors.append({"event": event.name, "reason": "registration_end_before_start"})
        event.registration_start = None
    event.primary_deadline = choose_primary_deadline(event)
    event.status = compute_status(event, now)
    event.confidence = "high" if event.source.authority >= 5 else ("medium" if event.source.authority >= 3 else "low")
    if event.verification_status == "cross_source":
        event.confidence = "high"
    return bool(event.primary_deadline)


def _apply_overrides(events: list[Event], path: Path, now) -> list[dict]:
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    allowed = {item.name for item in fields(Event)} - {"id", "sources", "source", "first_seen_at", "last_seen_at"}
    applied = []
    event_map = {event.id: event for event in events}
    for event_id, patch in payload.items():
        event = event_map.get(event_id)
        if not event:
            continue
        changed = []
        for key, value in patch.items():
            if key in allowed and key != "checked_at":
                setattr(event, key, value)
                changed.append(key)
        if changed:
            evidence = SourceEvidence("Maintainer override", patch.get("source_url") or event.official_url, "manual_review", 5, patch.get("checked_at") or iso(now), changed)
            event.source = evidence
            event.sources.insert(0, evidence)
            event.verification_status = "maintainer_reviewed"
            event.confidence = "high"
            applied.append({"event": event.name, "id": event.id, "fields": changed})
    return applied


def _load_previous(path: Path) -> dict[str, Event]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {row["id"]: Event.from_dict(row) for row in payload.get("items", [])}
    except (OSError, ValueError, TypeError, KeyError):
        return {}


def _lifecycle(current: list[Event], previous: dict[str, Event], now) -> list[Event]:
    current_ids = set()
    for event in current:
        current_ids.add(event.id)
        old = previous.get(event.id)
        event.first_seen_at = old.first_seen_at if old and old.first_seen_at else iso(now)
        event.last_seen_at = iso(now)
        event.stale = False
        event.archived = False
    for event_id, old in previous.items():
        if event_id in current_ids:
            continue
        last_seen = parse_datetime(old.last_seen_at or old.first_seen_at) or now
        age = now - last_seen
        old.stale = age >= timedelta(days=7)
        old.archived = age >= timedelta(days=30)
        old.status = compute_status(old, now)
        current.append(old)
    return current


def run_pipeline(root: str | Path = ".", selected_sources: list[str] | None = None, fetcher: Fetcher | None = None) -> dict[str, Any]:
    root = Path(root)
    now = now_china()
    fetcher = fetcher or Fetcher()
    source_names = selected_sources or list(SOURCE_ADAPTERS)
    unknown = sorted(set(source_names) - set(SOURCE_ADAPTERS))
    if unknown:
        raise ValueError(f"unknown sources: {', '.join(unknown)}")

    results: list[SourceResult] = []
    for name in source_names:
        collector = SOURCE_ADAPTERS[name]
        if name == "manual":
            result = collector(fetcher, now, root / "data/manual.yml")
        else:
            result = collector(fetcher, now)
        results.append(result)

    conflicts: list[dict] = []
    validation_errors: list[dict] = []
    fresh = _merge_events([event for result in results for event in result.events], conflicts)
    override_log = _apply_overrides(fresh, root / "data/overrides.yml", now)
    fresh = [event for event in fresh if _validate(event, validation_errors, now)]
    previous = _load_previous(root / "data/competitions.json")
    events = _lifecycle(fresh, previous, now)
    events.sort(key=lambda item: (item.archived, parse_datetime(item.primary_deadline) or now.replace(year=now.year + 10), item.name.lower()))

    ok_sources = sum(1 for result in results if result.ok)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso(now),
        "timezone": "Asia/Shanghai",
        "source_health": "healthy" if ok_sources == len(results) else ("degraded" if ok_sources else "failed"),
        "stats": {
            "total": len(events), "active": sum(
                bool(parse_datetime(event.primary_deadline) and parse_datetime(event.primary_deadline) >= now)
                and not event.archived for event in events
            ),
            "stale": sum(event.stale for event in events), "archived": sum(event.archived for event in events),
            "by_type": {kind: sum(event.event_type == kind for event in events) for kind in sorted({event.event_type for event in events})},
        },
        "items": [event.to_dict() for event in events],
    }
    source_status = {
        "generated_at": iso(now),
        "sources": [{
            "name": result.name, "ok": result.ok, "records": len(result.events), "url": result.url,
            "error": result.error, "fetched_at": result.fetched_at, "duration_ms": result.duration_ms,
        } for result in results],
    }
    quality = {
        "generated_at": iso(now), "accepted_fresh_records": len(fresh),
        "conflicts": conflicts, "validation_errors": validation_errors,
        "overrides_applied": override_log,
        "rules": {"stale_after_days": 7, "archive_after_days": 30, "physical_deletion": False},
    }
    return {"data": payload, "source_status": source_status, "quality": quality, "results": results}
