from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from contestddl.models import Event, SourceEvidence
from contestddl.sources.common import guarded
from contestddl.utils import CHINA_TZ, clean_text, iso, now_china, stable_id


DATA_URL = "https://ccfddl.com/conference/allconf.yml"
PROJECT_URL = "https://github.com/ccfddl/ccf-deadlines"
RECENT_GRACE = timedelta(days=7)
LOOKAHEAD = timedelta(days=500)

CATEGORY_NAMES = {
    "DS": "计算机体系结构/并行与分布计算/存储系统",
    "NW": "计算机网络",
    "SC": "网络与信息安全",
    "SE": "软件工程/系统软件/程序设计语言",
    "DB": "数据库/数据挖掘/内容检索",
    "CT": "计算机科学理论",
    "CG": "计算机图形学与多媒体",
    "AI": "人工智能",
    "HI": "人机交互与普适计算",
    "MX": "交叉/综合/新兴",
}


def _deadline_timezone(label: str):
    normalized = (label or "").strip()
    if normalized == "AoE":
        return timezone(timedelta(hours=-12))
    if normalized == "PT":
        return ZoneInfo("America/Los_Angeles")
    if normalized in {"UTC", "UTC+0"}:
        return timezone.utc
    match = re.fullmatch(r"UTC([+-])(\d{1,2})", normalized)
    if not match:
        raise ValueError(f"unsupported CCFDDL timezone: {label}")
    offset = int(match.group(2)) * (1 if match.group(1) == "+" else -1)
    if not -12 <= offset <= 12:
        raise ValueError(f"invalid CCFDDL timezone offset: {label}")
    return timezone(timedelta(hours=offset))


def _parse_deadline(value: object, timezone_label: str) -> datetime | None:
    text = str(value or "").strip()
    if not text or text.upper() == "TBD":
        return None
    parsed = None
    for date_format in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, date_format)
            if date_format == "%Y-%m-%d":
                parsed = parsed.replace(hour=23, minute=59, second=59)
            break
        except ValueError:
            continue
    if parsed is None:
        raise ValueError(f"invalid CCFDDL deadline: {text}")
    return parsed.replace(tzinfo=_deadline_timezone(timezone_label)).astimezone(CHINA_TZ)


def _rank_labels(rank: dict) -> list[str]:
    labels = []
    ccf_rank = clean_text(str(rank.get("ccf") or ""))
    if ccf_rank:
        labels.append("非 CCF" if ccf_rank == "N" else f"CCF {ccf_rank}")
    for key, label in (("core", "CORE"), ("thcpl", "TH-CPL")):
        value = clean_text(str(rank.get(key) or ""))
        if value and value != "N":
            labels.append(f"{label} {value}")
    return labels


def _nearest(values: list[datetime], current: datetime) -> datetime | None:
    future = [value for value in values if value >= current]
    return min(future) if future else (max(values) if values else None)


def _event_from_entry(
    series: dict,
    edition: dict,
    current: datetime,
    *,
    disambiguate_title: bool = False,
) -> Event | None:
    title = clean_text(str(series.get("title") or ""))
    year = edition.get("year")
    link = clean_text(str(edition.get("link") or ""))
    timezone_label = clean_text(str(edition.get("timezone") or ""))
    timeline = edition.get("timeline")
    if not title or not year or not link.startswith(("http://", "https://")) or not isinstance(timeline, list):
        return None

    milestones = []
    for index, row in enumerate(timeline, start=1):
        if not isinstance(row, dict):
            continue
        comment = clean_text(str(row.get("comment") or ""))
        for field_name, label in (("abstract_deadline", "摘要截止"), ("deadline", "论文截止")):
            value = _parse_deadline(row.get(field_name), timezone_label)
            if value:
                milestones.append({
                    "kind": field_name,
                    "label": label,
                    "comment": comment,
                    "round": index,
                    "value": value,
                })

    window_start, window_end = current - RECENT_GRACE, current + LOOKAHEAD
    relevant = [item for item in milestones if window_start <= item["value"] <= window_end]
    if not relevant:
        return None
    relevant.sort(key=lambda item: item["value"])

    future_papers = [item for item in milestones if item["kind"] == "deadline" and current <= item["value"] <= window_end]
    future_abstracts = [item for item in milestones if item["kind"] == "abstract_deadline" and current <= item["value"] <= window_end]
    if future_papers:
        selected_round = min(future_papers, key=lambda item: item["value"])["round"]
    elif future_abstracts:
        selected_round = min(future_abstracts, key=lambda item: item["value"])["round"]
    else:
        selected_round = max(relevant, key=lambda item: item["value"])["round"]
    selected_milestones = [item for item in milestones if item["round"] == selected_round]
    paper_deadlines = [item["value"] for item in selected_milestones if item["kind"] == "deadline"]
    abstract_deadlines = [item["value"] for item in selected_milestones if item["kind"] == "abstract_deadline"]
    submission_deadline = _nearest(paper_deadlines, current)
    abstract_deadline = _nearest(abstract_deadlines, current)
    multiple_rounds = len(timeline) > 1
    schedule = []
    seen_schedule = set()
    for item in relevant:
        schedule_key = (item["round"], item["kind"], item["value"], item["comment"])
        if schedule_key in seen_schedule:
            continue
        seen_schedule.add(schedule_key)
        short_comment = item["comment"] if len(item["comment"]) <= 32 else ""
        prefix = short_comment or (f"第 {item['round']} 轮" if multiple_rounds else "")
        name = f"{prefix} · {item['label']}" if prefix else item["label"]
        stage = {
            "id": f"round-{item['round']}-{item['kind']}",
            "name": name,
            "end": iso(item["value"]),
        }
        if item["comment"]:
            stage["content"] = item["comment"]
        schedule.append(stage)

    rank = series.get("rank") if isinstance(series.get("rank"), dict) else {}
    rank_labels = _rank_labels(rank)
    sub = clean_text(str(series.get("sub") or ""))
    description = clean_text(str(series.get("description") or ""))
    name = f"{title} {year}"
    if disambiguate_title:
        name = f"{name} · {description or CATEGORY_NAMES.get(sub, sub or '学术会议')}"
    conference_date = clean_text(str(edition.get("date") or ""))
    location = clean_text(str(edition.get("place") or ""))
    notes = [
        "CCFDDL 社区协作维护的会议截稿数据",
        f"原始时区：{timezone_label}",
        f"会议时间：{conference_date}" if conference_date else "",
        "日期可能调整，投稿前请回会议官网复核",
    ]
    evidence_fields = [
        "name", "official_url", "categories", "level", "location",
        "abstract_deadline", "submission_deadline", "schedule",
    ]
    source = SourceEvidence(
        "CCFDDL Open Deadlines",
        DATA_URL,
        "trusted_community",
        4,
        iso(current),
        evidence_fields,
    )
    identity = clean_text(str(edition.get("id") or f"{title}-{year}"))
    dblp = clean_text(str(series.get("dblp") or ""))
    series_identity = "|".join((sub, dblp))
    stable_name = " ".join(filter(None, (title, str(year), sub, dblp)))
    place_lower = location.lower()
    mode = "online" if any(word in place_lower for word in ("online", "virtual")) else ("hybrid" if "hybrid" in place_lower else "")
    return Event(
        id=stable_id(stable_name, "conference", str(year), f"ccfddl-{series_identity}-{identity}"),
        name=name,
        event_type="conference",
        categories=[CATEGORY_NAMES.get(sub, sub or "计算机学术会议")],
        official_url=link,
        source=source,
        level=" / ".join(rank_labels),
        region="global",
        location=location,
        mode=mode,
        abstract_deadline=iso(abstract_deadline) if abstract_deadline else None,
        submission_deadline=iso(submission_deadline) if submission_deadline else None,
        tags=list(dict.fromkeys(filter(None, ["学术会议", sub, *rank_labels]))),
        notes="；".join(item for item in notes if item) + "。",
        description=description,
        schedule=schedule,
    )


def collect(fetcher, now=None):
    current = now or now_china()

    def run():
        payload = yaml.safe_load(fetcher.text(DATA_URL))
        if not isinstance(payload, list):
            raise ValueError("CCFDDL dataset must be a list")
        title_counts = Counter(
            clean_text(str(series.get("title") or "")).casefold()
            for series in payload if isinstance(series, dict)
        )
        events = []
        editions = 0
        invalid_entries = 0
        for series in payload:
            if not isinstance(series, dict):
                invalid_entries += 1
                continue
            confs = series.get("confs")
            if not isinstance(confs, list):
                invalid_entries += 1
                continue
            for edition in confs:
                editions += 1
                if not isinstance(edition, dict):
                    invalid_entries += 1
                    continue
                try:
                    title_key = clean_text(str(series.get("title") or "")).casefold()
                    event = _event_from_entry(
                        series,
                        edition,
                        current,
                        disambiguate_title=title_counts[title_key] > 1,
                    )
                except (TypeError, ValueError, ZoneInfoNotFoundError):
                    invalid_entries += 1
                    continue
                if event:
                    events.append(event)
        details = {
            "project": PROJECT_URL,
            "dataset_series": len(payload),
            "dataset_editions": editions,
            "recent_or_upcoming_editions": len(events),
            "invalid_entries": invalid_entries,
            "window": {"recent_grace_days": RECENT_GRACE.days, "lookahead_days": LOOKAHEAD.days},
        }
        return events, details

    return guarded("ccfddl", DATA_URL, run)
