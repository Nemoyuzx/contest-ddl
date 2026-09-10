"""Export only Saikr on Ubuntu; consume its verified public snapshot on GitHub."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from contestddl.fetch import Fetcher
from contestddl.models import Event, SourceResult
from contestddl.sources.common import guarded
from contestddl.utils import CHINA_TZ, iso, now_china

SNAPSHOT_URL = "https://where-to-study.cn/data/saikr-snapshot.json"
SNAPSHOT_VERSION = 1
MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024
MAX_EVENTS = 500
MAX_AGE = timedelta(hours=36)
CLOCK_TOLERANCE = timedelta(minutes=5)
DATE_FIELDS = ("registration_start", "registration_deadline", "competition_start", "competition_end", "abstract_deadline", "submission_deadline", "primary_deadline")


def _timestamp(value) -> datetime:
    if not isinstance(value, str):
        raise ValueError("snapshot timestamp is missing")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("snapshot timestamp must include timezone")
    return result.astimezone(CHINA_TZ)


def snapshot_digest(payload: dict) -> str:
    unsigned = {key: value for key, value in payload.items() if key != "sha256"}
    body = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def validate_snapshot(payload, now=None) -> list[Event]:
    current = now or now_china()
    if not isinstance(payload, dict) or type(payload.get("snapshot_version")) is not int or payload["snapshot_version"] != SNAPSHOT_VERSION:
        raise ValueError("unsupported Saikr snapshot version")
    if payload.get("source") != "saikr" or payload.get("producer") != "contest-ddl-saikr":
        raise ValueError("snapshot is not a Saikr-only export")
    if type(payload.get("ok")) is not bool or not isinstance(payload.get("error"), str) or not isinstance(payload.get("details"), dict):
        raise ValueError("invalid snapshot source status")
    if payload.get("sha256") != snapshot_digest(payload):
        raise ValueError("snapshot SHA-256 mismatch")
    fetched = _timestamp(payload.get("fetched_at"))
    if fetched > current + CLOCK_TOLERANCE or current - fetched > MAX_AGE:
        raise ValueError("Saikr snapshot is stale (over 36 hours) or future-dated")
    if payload.get("last_success_at") is not None and _timestamp(payload["last_success_at"]) > fetched + CLOCK_TOLERANCE:
        raise ValueError("snapshot last success timestamp is invalid")
    rows = payload.get("events")
    if not isinstance(rows, list) or len(rows) > MAX_EVENTS or type(payload.get("records")) is not int or payload["records"] != len(rows):
        raise ValueError("snapshot event count mismatch")
    if payload["ok"] and payload["error"]:
        raise ValueError("healthy snapshot must not contain a source error")
    events = []
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"] or row["id"] in ids:
            raise ValueError("invalid or duplicate snapshot event ID")
        ids.add(row["id"])
        if row.get("event_type") != "competition" or not isinstance(row.get("name"), str) or not row["name"].strip():
            raise ValueError("snapshot must contain named competitions only")
        original = row.get("source")
        if not isinstance(original, dict) or original.get("name") != "赛氪公开前端 API" or original.get("authority") != 2:
            raise ValueError("snapshot source evidence is invalid")
        if original.get("source_type") != "aggregator_api" or row.get("sources") != [original]:
            raise ValueError("snapshot must not mix in other data sources")
        for url in (row.get("official_url"), original.get("url")):
            parts = urlsplit(url or "")
            if parts.scheme != "https" or parts.hostname not in {"new.saikr.com", "www.saikr.com", "saikr.com"} or parts.username or parts.password or parts.port not in {None, 443}:
                raise ValueError("snapshot must retain the original Saikr evidence URL")
        checked = _timestamp(original.get("checked_at"))
        if checked > fetched + CLOCK_TOLERANCE or fetched - checked > timedelta(hours=1):
            raise ValueError("snapshot evidence timestamp does not match collection")
        dates = [_timestamp(row[field]) for field in DATE_FIELDS if row.get(field)]
        if not dates or not isinstance(row.get("categories"), list) or any(not isinstance(value, str) for value in row["categories"]):
            raise ValueError("snapshot event lacks valid dates or categories")
        event = Event.from_dict(row)
        # Refreshing the mirror is not a new upstream observation.
        event.last_seen_at = iso(fetched)
        events.append(event)
    return events


def read_snapshot(fetcher: Fetcher) -> dict:
    started = time.monotonic()
    with fetcher.get(SNAPSHOT_URL, headers={"Accept": "application/json"}, stream=True, allow_redirects=False, timeout=(5, 15)) as response:
        if response.status_code != 200 or response.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            raise ValueError("Saikr snapshot endpoint did not return HTTP 200 JSON")
        chunks = []
        size = 0
        for chunk in response.iter_content(chunk_size=8192):
            size += len(chunk)
            if size > MAX_SNAPSHOT_BYTES or time.monotonic() - started > 30:
                raise ValueError("Saikr snapshot exceeds size or read-time budget")
            chunks.append(chunk)
    return json.loads(b"".join(chunks))


def collect_snapshot(fetcher, now=None) -> SourceResult:
    current = now or now_china()
    snapshot = None

    def run():
        nonlocal snapshot
        snapshot = read_snapshot(fetcher)
        events = validate_snapshot(snapshot, current)
        details = dict(snapshot["details"])
        details["transport"] = {
            "method": "ubuntu_snapshot", "url": SNAPSHOT_URL,
            "fetched_at": snapshot["fetched_at"], "last_success_at": snapshot.get("last_success_at"),
            "sha256": snapshot["sha256"], "max_age_hours": 36,
        }
        return events, details

    result = guarded("saikr", SNAPSHOT_URL, run)
    if result.ok and snapshot is not None:
        result.ok = snapshot["ok"]
        result.error = snapshot["error"] or ("Ubuntu Saikr collection failed" if not result.ok else "")
        result.fetched_at = snapshot["fetched_at"]
    return result


def _atomic_json(path: Path, value: dict) -> None:
    body = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(body) > MAX_SNAPSHOT_BYTES:
        raise ValueError("Saikr export exceeds snapshot size limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
            os.fchmod(output.fileno(), 0o644)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _document(result: SourceResult, last_success_at: str | None) -> dict:
    value = {
        "snapshot_version": SNAPSHOT_VERSION, "producer": "contest-ddl-saikr", "source": "saikr",
        "fetched_at": result.fetched_at, "ok": result.ok, "error": result.error,
        "last_success_at": result.fetched_at if result.ok else last_success_at,
        "records": len(result.events), "events": [event.to_dict() for event in result.events], "details": result.details,
    }
    value["sha256"] = snapshot_digest(value)
    return value


def refresh_snapshot(path: Path, collector=None, now=now_china) -> dict:
    from contestddl.sources.saikr import collect_direct
    collect = collector or (lambda: collect_direct(Fetcher(timeout=20)))
    last_good = path.with_name("last-success.json")
    try:
        previous = json.loads(last_good.read_text(encoding="utf-8"))
        last_success = previous["fetched_at"] if previous.get("sha256") == snapshot_digest(previous) and previous.get("ok") is True else None
    except (OSError, ValueError, KeyError, TypeError):
        last_success = None
    # If the process is killed or times out, consumers see failure, not an old
    # successful snapshot with a freshly rewritten timestamp.
    pending = _document(SourceResult(name="saikr", ok=False, fetched_at=iso(now()), error="Ubuntu Saikr collection in progress or interrupted"), last_success)
    _atomic_json(path, pending)
    try:
        result = collect()
        document = _document(result, last_success)
        validate_snapshot(document, now())
        if result.ok:
            _atomic_json(last_good, document)
        _atomic_json(path, document)
        return document
    except Exception as exc:
        failed = _document(SourceResult(name="saikr", ok=False, fetched_at=iso(now()), error=f"{type(exc).__name__}: {str(exc)[:500]}"), last_success)
        _atomic_json(path, failed)
        return failed


def main():
    import fcntl
    parser = argparse.ArgumentParser(description="Export a Saikr-only snapshot on the domestic collector host")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.with_name(".refresh.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Saikr snapshot collection is already running")
            return
        result = refresh_snapshot(args.output)
    print(json.dumps({key: result[key] for key in ("ok", "records", "fetched_at", "last_success_at", "error")}, ensure_ascii=False))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
