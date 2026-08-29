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


def _ics_fold(line: str) -> str:
    """Fold one content line to RFC 5545's 75-octet physical-line limit."""
    if len(line.encode("utf-8")) <= 75:
        return line
    chunks = []
    current = ""
    limit = 75
    for character in line:
        if current and len((current + character).encode("utf-8")) > limit:
            chunks.append(current)
            current = character
            limit = 74  # continuation lines begin with one whitespace octet
        else:
            current += character
    if current:
        chunks.append(current)
    return "\r\n ".join(chunks)


def _conference_schedule_milestones(item: dict) -> list[tuple[str, str, str, str, str]]:
    milestones = []
    for index, stage in enumerate(item.get("schedule") or [], start=1):
        if not isinstance(stage, dict):
            continue
        name = str(stage.get("name") or "").strip()
        if not re.search(r"摘要|论文|投稿|截稿|提交|deadline", name, flags=re.I):
            continue
        semantic_field = (
            "abstract_deadline"
            if re.search(r"摘要|abstract", name, flags=re.I)
            else "submission_deadline"
        )
        raw_identity = str(stage.get("id") or index)
        identity = re.sub(r"[^a-zA-Z0-9_.-]+", "-", raw_identity).strip("-") or str(index)
        for edge, suffix in (("start", "开始"), ("end", "结束")):
            value = stage.get(edge)
            if not value or not parse_datetime(value):
                continue
            label = name if re.search(r"截止|deadline", name, flags=re.I) else f"{name}{suffix}"
            description = str(stage.get("content") or item.get("notes") or "")[:500]
            milestones.append((f"schedule-{identity}-{edge}", label, value, description, semantic_field))
    return milestones


def build_ics(items: list[dict]) -> str:
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Contest DDL//CN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:Contest DDL 截止日期",
        "X-WR-TIMEZONE:Asia/Shanghai", "REFRESH-INTERVAL;VALUE=DURATION:P1D",
    ]
    labels = {
        "registration_deadline": "报名截止", "abstract_deadline": "摘要截止",
        "submission_deadline": "提交截止",
        "competition_start": "比赛开始", "competition_end": "比赛结束",
    }
    observed_times = [parse_datetime(item.get("last_seen_at")) for item in items]
    current = max((value for value in observed_times if value), default=None)
    for item in items:
        primary = parse_datetime(item.get("primary_deadline"))
        if item.get("archived") or not primary or (current and primary < current):
            continue
        schedule_milestones = (
            _conference_schedule_milestones(item)
            if item.get("event_type") == "conference" else []
        )
        skip_fields = {
            semantic_field
            for _, _, value, _, semantic_field in schedule_milestones
            if item.get(semantic_field)
            and parse_datetime(item[semantic_field]) == parse_datetime(value)
        }
        milestones = [
            (field, label, item.get(field), str(item.get("notes") or "")[:500])
            for field, label in labels.items()
            if field not in skip_fields and item.get(field)
        ]
        milestones.extend(entry[:4] for entry in schedule_milestones)
        emitted = set()
        for identity, label, value, description in milestones:
            if not value or (identity, value) in emitted:
                continue
            emitted.add((identity, value))
            start = parse_datetime(value)
            if not start:
                continue
            uid = f"{item['id']}-{identity}@contest-ddl"
            lines.extend([
                "BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{_ics_dt(item.get('last_seen_at') or value)}",
                f"DTSTART:{_ics_dt(value)}", f"DTEND:{(start.astimezone(UTC) + timedelta(minutes=30)).strftime('%Y%m%dT%H%M%SZ')}",
                f"SUMMARY:{_ics_escape('[' + label + '] ' + item['name'])}",
                f"DESCRIPTION:{_ics_escape(description)}",
                f"URL:{_ics_escape(item.get('official_url', ''))}",
                f"CATEGORIES:{_ics_escape(','.join(item.get('categories', [])))}", "END:VEVENT",
            ])
    lines.append("END:VCALENDAR")
    return "\r\n".join(_ics_fold(line) for line in lines) + "\r\n"


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
