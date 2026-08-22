from datetime import datetime, timedelta

from contestddl.models import Event, SourceEvidence
from contestddl.output import build_ics
from contestddl.pipeline import _is_removed_event, _lifecycle, _merge_events, _validate
from contestddl.utils import CHINA_TZ, iso


NOW = datetime(2026, 8, 22, 12, tzinfo=CHINA_TZ)


def make_event(authority=5, **kwargs):
    source = SourceEvidence(kwargs.pop("source_name", "source"), kwargs.pop("source_url", "https://example.com"), "test", authority, iso(NOW))
    defaults = dict(id=f"id-{authority}", name="Test Hack 2026", event_type="hackathon", categories=["黑客松"], official_url="https://event.example", source=source, competition_start="2026-09-01T08:00:00+08:00")
    defaults.update(kwargs)
    return Event(**defaults)


def test_merge_prefers_high_authority_and_fills_empty_fields():
    high = make_event(5, organizer="", source_name="official", source_url="https://official.example")
    low = make_event(2, organizer="Organizer", competition_start="2026-09-02T08:00:00+08:00", source_name="aggregator", source_url="https://other.example")
    conflicts = []
    merged = _merge_events([low, high], conflicts)[0]
    assert merged.source.name == "official"
    assert merged.organizer == "Organizer"
    assert conflicts and conflicts[0]["field"] == "competition_start"


def test_validation_rejects_event_without_any_date():
    item = make_event(competition_start=None)
    errors = []
    assert not _validate(item, errors, NOW)


def test_lifecycle_preserves_unseen_old_record():
    old = make_event()
    old.first_seen_at = iso(NOW - timedelta(days=40))
    old.last_seen_at = iso(NOW - timedelta(days=40))
    items = _lifecycle([], {old.id: old}, NOW)
    assert len(items) == 1
    assert items[0].stale and items[0].archived


def test_ics_contains_deadline_and_url():
    item = make_event(registration_deadline="2026-08-30T23:59:59+08:00")
    item.last_seen_at = iso(NOW)
    assert _validate(item, [], NOW)
    text = build_ics([item.to_dict()])
    assert "BEGIN:VCALENDAR" in text
    assert "[报名截止] Test Hack 2026" in text
    assert "https://event.example" in text


def test_ctf_and_codeforces_records_are_removed():
    ctf = make_event(name="Student CTF 2026", categories=["网络安全", "CTF"])
    codeforces = make_event(source_name="Codeforces API")
    normal = make_event(name="Student AI Hackathon", categories=["黑客松"])
    assert _is_removed_event(ctf)
    assert _is_removed_event(codeforces)
    assert not _is_removed_event(normal)
