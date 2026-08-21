from __future__ import annotations

import json
import re
from datetime import UTC, timedelta
from pathlib import Path

from contestddl.utils import parse_datetime


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _ics_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ics_dt(value: str) -> str:
    return parse_datetime(value).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def build_ics(items: list[dict]) -> str:
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Contest DDL//CN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:大学生竞赛 DDL",
        "X-WR-TIMEZONE:Asia/Shanghai", "REFRESH-INTERVAL;VALUE=DURATION:P1D",
    ]
    labels = {
        "registration_deadline": "报名截止", "submission_deadline": "提交截止",
        "competition_start": "比赛开始", "competition_end": "比赛结束",
    }
    observed_times = [parse_datetime(item.get("last_seen_at")) for item in items]
    current = max((value for value in observed_times if value), default=None)
    for item in items:
        primary = parse_datetime(item.get("primary_deadline"))
        if item.get("archived") or not primary or (current and primary < current):
            continue
        emitted = set()
        for field, label in labels.items():
            value = item.get(field)
            if not value or (field, value) in emitted:
                continue
            emitted.add((field, value))
            start = parse_datetime(value)
            if not start:
                continue
            uid = f"{item['id']}-{field}@contest-ddl"
            lines.extend([
                "BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{_ics_dt(item.get('last_seen_at') or value)}",
                f"DTSTART:{_ics_dt(value)}", f"DTEND:{(start.astimezone(UTC) + timedelta(minutes=30)).strftime('%Y%m%dT%H%M%SZ')}",
                f"SUMMARY:{_ics_escape('[' + label + '] ' + item['name'])}",
                f"DESCRIPTION:{_ics_escape(item.get('notes', '')[:500])}",
                f"URL:{_ics_escape(item.get('official_url', ''))}",
                f"CATEGORIES:{_ics_escape(','.join(item.get('categories', [])))}", "END:VEVENT",
            ])
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def update_readme_snapshot(path: Path, payload: dict) -> None:
    text = path.read_text(encoding="utf-8")
    start_marker, end_marker = "<!-- DATA_SNAPSHOT_START -->", "<!-- DATA_SNAPSHOT_END -->"
    if start_marker not in text or end_marker not in text:
        return
    generated_at = parse_datetime(payload["generated_at"])
    upcoming = [
        item for item in payload["items"]
        if not item.get("archived") and parse_datetime(item.get("primary_deadline"))
        and parse_datetime(item["primary_deadline"]) >= generated_at
    ][:12]
    rows = [
        f"> 数据生成于 `{payload['generated_at']}`，共 {payload['stats']['total']} 条；数据源状态：`{payload['source_health']}`。",
        "", "| 事件 | 类型 | 最近 DDL / 时间 | 状态 | 来源 |", "| --- | --- | --- | --- | --- |",
    ]
    for item in upcoming:
        name = re.sub(r"[|\n]", " ", item["name"])
        source_name = re.sub(r"[|\n]", " ", item["source"]["name"])
        rows.append(f"| [{name}]({item['official_url']}) | {item['event_type']} | {item.get('primary_deadline') or '待核验'} | {item['status']} | {source_name} |")
    replacement = start_marker + "\n" + "\n".join(rows) + "\n" + end_marker
    updated = re.sub(re.escape(start_marker) + r".*?" + re.escape(end_marker), replacement, text, flags=re.S)
    path.write_text(updated, encoding="utf-8")


def write_outputs(root: Path, result: dict) -> None:
    data_dir = root / "data"
    write_json(data_dir / "competitions.json", result["data"])
    write_json(data_dir / "source-status.json", result["source_status"])
    write_json(data_dir / "quality-report.json", result["quality"])
    (data_dir / "competitions.ics").write_text(build_ics(result["data"]["items"]), encoding="utf-8")
    update_readme_snapshot(root / "README.md", result["data"])
