import copy
import json
from datetime import datetime, timedelta

import pytest

from contestddl.models import SourceResult
from contestddl.saikr_snapshot import (
    MAX_SNAPSHOT_BYTES, SNAPSHOT_URL, _document, collect_snapshot,
    read_snapshot, refresh_snapshot, snapshot_digest, validate_snapshot,
)
from contestddl.sources import saikr
from contestddl.pipeline import _lifecycle
from contestddl.utils import CHINA_TZ, iso

NOW = datetime(2026, 9, 10, 12, tzinfo=CHINA_TZ)


def source_result(ok=True):
    event = saikr._event_from_api({
        "contest_id": 1, "contest_name": "2026人工智能算法竞赛", "contest_url": "vse/test",
        "regist_end_time": 1789912800,
    }, {}, NOW)
    return SourceResult(name="saikr", ok=ok, events=[event], fetched_at=iso(NOW), error="" if ok else "1/8 categories failed", details={"list_failures": [] if ok else [{"category": "test", "error": "temporary failure"}]})


def snapshot(ok=True):
    return _document(source_result(ok), None)


class Response:
    def __init__(self, payload, *, status=200, content_type="application/json", raw=None):
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        self.body = raw if raw is not None else json.dumps(payload).encode()
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def iter_content(self, chunk_size):
        for offset in range(0, len(self.body), chunk_size):
            yield self.body[offset:offset + chunk_size]


class Fetcher:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_remote_collection_only_reads_fixed_snapshot_and_keeps_original_evidence(monkeypatch):
    monkeypatch.setenv("SAIKR_SOURCE", "ubuntu")
    fetcher = Fetcher(Response(snapshot()))
    result = saikr.collect(fetcher, NOW + timedelta(hours=4))
    assert result.ok and len(result.events) == 1
    assert len(fetcher.calls) == 1
    assert fetcher.calls[0][0] == SNAPSHOT_URL
    assert fetcher.calls[0][1]["allow_redirects"] is False
    assert fetcher.calls[0][1]["stream"] is True
    assert fetcher.response.closed
    assert result.events[0].source.url == "https://new.saikr.com/vse/test"
    assert result.events[0].source.authority == 2
    assert result.events[0].last_seen_at == iso(NOW)
    assert result.fetched_at == iso(NOW)
    assert result.details["transport"]["method"] == "ubuntu_snapshot"


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(snapshot_version=2),
    lambda p: p.update(ok="true"),
    lambda p: p.update(source="mlh"),
    lambda p: p.update(records=99),
    lambda p: p.update(fetched_at=iso(NOW - timedelta(hours=37))),
    lambda p: p.update(fetched_at=iso(NOW + timedelta(minutes=6))),
    lambda p: p.update(fetched_at="2026-09-10T12:00:00"),
    lambda p: p["events"][0].update(event_type="conference"),
    lambda p: p["events"][0].update(official_url="https://example.com/forged"),
    lambda p: p["events"][0].update(sources=[]),
    lambda p: p["events"][0]["source"].update(authority=5),
    lambda p: p["events"].append(copy.deepcopy(p["events"][0])),
])
def test_invalid_or_stale_snapshots_fail_closed(mutate):
    payload = snapshot()
    mutate(payload)
    payload["sha256"] = snapshot_digest(payload)
    result = collect_snapshot(Fetcher(Response(payload)), NOW)
    assert not result.ok
    assert result.events == []


def test_digest_detects_modified_event_and_no_direct_fallback(monkeypatch):
    payload = snapshot()
    payload["events"][0]["name"] = "modified"
    fetcher = Fetcher(Response(payload))
    monkeypatch.setenv("SAIKR_SOURCE", "ubuntu")
    result = saikr.collect(fetcher, NOW)
    assert not result.ok and "SHA-256" in result.error
    assert len(fetcher.calls) == 1
    assert all(call[0] == SNAPSHOT_URL for call in fetcher.calls)


def test_partial_failure_keeps_only_fresh_partial_discoveries():
    result = collect_snapshot(Fetcher(Response(snapshot(False))), NOW + timedelta(hours=1))
    assert not result.ok
    assert len(result.events) == 1
    assert "categories failed" in result.error
    assert result.fetched_at == iso(NOW)


@pytest.mark.parametrize("status,content_type,body", [
    (302, "application/json", b"{}"),
    (200, "text/html", b"<html>redirect</html>"),
    (200, "application/json", b"x" * (MAX_SNAPSHOT_BYTES + 1)),
])
def test_snapshot_stream_rejects_redirects_html_and_oversized_bodies(status, content_type, body):
    response = Response(None, status=status, content_type=content_type, raw=body)
    with pytest.raises(ValueError):
        read_snapshot(Fetcher(response))
    assert response.closed


def test_export_is_atomic_preserves_last_good_and_publishes_failures(tmp_path):
    target = tmp_path / "snapshot.json"
    first = refresh_snapshot(target, collector=source_result, now=lambda: NOW)
    assert first["ok"]
    assert validate_snapshot(first, NOW)
    last_good = (tmp_path / "last-success.json").read_bytes()

    def fail():
        pending = json.loads(target.read_text())
        assert not pending["ok"] and pending["events"] == []
        assert pending["last_success_at"] == iso(NOW)
        raise RuntimeError("upstream unavailable")

    failed = refresh_snapshot(target, collector=fail, now=lambda: NOW + timedelta(hours=24))
    assert not failed["ok"] and failed["records"] == 0
    assert failed["last_success_at"] == iso(NOW)
    assert "upstream unavailable" in failed["error"]
    assert (tmp_path / "last-success.json").read_bytes() == last_good
    assert json.loads(target.read_text()) == failed
    assert not list(tmp_path.glob("*.tmp"))


def test_export_never_uses_mirror_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("SAIKR_SOURCE", "ubuntu")
    monkeypatch.setattr(saikr, "collect_direct", lambda fetcher: source_result())
    monkeypatch.setattr(saikr, "collect", lambda *args, **kwargs: pytest.fail("producer must not recursively read its own snapshot"))
    assert refresh_snapshot(tmp_path / "snapshot.json", now=lambda: NOW)["ok"]


def test_repeated_snapshot_reads_do_not_renew_upstream_observation_time():
    item = validate_snapshot(snapshot(), NOW)[0]
    first = _lifecycle([item], {}, NOW + timedelta(hours=1))[0]
    assert first.first_seen_at == first.last_seen_at == iso(NOW)
    repeated = validate_snapshot(snapshot(), NOW + timedelta(hours=24))[0]
    second = _lifecycle([repeated], {first.id: first}, NOW + timedelta(hours=24))[0]
    assert second.last_seen_at == iso(NOW)
    later = copy.deepcopy(first)
    later.last_seen_at = iso(NOW + timedelta(hours=1))
    old = validate_snapshot(snapshot(), NOW + timedelta(hours=2))[0]
    assert _lifecycle([old], {later.id: later}, NOW + timedelta(hours=2))[0].last_seen_at == later.last_seen_at
