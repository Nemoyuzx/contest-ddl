from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import UTC, datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

CHINA_TZ = timezone(timedelta(hours=8))

ENGINEERING_KEYWORDS = (
    "计算机", "软件", "人工智能", "智能", "电子", "信息", "通信", "网络空间",
    "网安", "安全", "自动化", "机械", "机器人", "控制", "电气", "集成电路",
    "芯片", "物联网", "大数据", "数据科学", "算法", "编程", "程序设计", "数学建模",
    "computer", "software", "artificial intelligence", " ai ", "cyber", "security",
    "robot", "automation", "electronic", "communication", "engineering", "hack",
    "code", "data", "ctf", "machine learning",
)

TRACKING_KEYS = {"from", "spm", "source", "ref", "referrer", "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term"}


def now_china() -> datetime:
    return datetime.now(CHINA_TZ)


def iso(value: datetime | None = None) -> str:
    return (value or now_china()).astimezone(CHINA_TZ).isoformat(timespec="seconds")


def parse_datetime(value: object, *, default_tz=CHINA_TZ) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, UTC).astimezone(CHINA_TZ)
    text = str(value).strip().replace("Z", "+00:00")
    text = re.sub(r"\s+UTC\+8$", "+08:00", text, flags=re.I)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y年%m月%d日 %H:%M", "%Y年%m月%d日", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=default_tz)
    return parsed.astimezone(CHINA_TZ)


def iso_or_none(value: object, *, end_of_day: bool = False) -> str | None:
    parsed = parse_datetime(value)
    if not parsed:
        return None
    if end_of_day and parsed.hour == parsed.minute == parsed.second == 0:
        parsed = parsed.replace(hour=23, minute=59, second=59)
    return iso(parsed)


def canonical_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    if host == "m.saikr.com":
        host = "saikr.com"
    path = re.sub(r"/{2,}", "/", parts.path).rstrip("/") or "/"
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in TRACKING_KEYS))
    return urlunsplit((parts.scheme.lower() or "https", host, path, query, ""))


def normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFKC", title or "").strip().lower()
    text = re.sub(r"[-_]?大学生竞赛[-_]?赛氪.*$", "", text)
    text = re.sub(r"[-_]?赛氪竞赛网.*$", "", text)
    text = re.sub(r"\b(official|官网|报名入口)\b", "", text)
    return re.sub(r"[\s（）()【】\[\]《》<>「」“”'\"·—_\-，,。.!！:：;；/\\]", "", text)


def stable_id(name: str, event_type: str, start: str | None = None, source_hint: str = "") -> str:
    year = ""
    match = re.search(r"(?:19|20)\d{2}", f"{name} {start or ''}")
    if match:
        year = match.group(0)
    raw = "|".join((normalize_title(name), event_type, year, source_hint))
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    label = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()).strip("-")[:42]
    return f"{label or event_type}-{digest}"


def engineering_relevant(*values: str) -> bool:
    haystack = f" {' '.join(value or '' for value in values).lower()} "
    return any(keyword in haystack for keyword in ENGINEERING_KEYWORDS)


def compute_status(event, now: datetime | None = None) -> str:
    current = now or now_china()
    reg_start = parse_datetime(event.registration_start)
    reg_end = parse_datetime(event.registration_deadline)
    comp_start = parse_datetime(event.competition_start)
    comp_end = parse_datetime(event.competition_end)
    submit = parse_datetime(event.submission_deadline)
    if comp_end and current > comp_end:
        return "ended"
    if comp_start and current >= comp_start and (not comp_end or current <= comp_end):
        return "ongoing"
    if reg_start and current < reg_start:
        return "registration_upcoming"
    if reg_end and current <= reg_end:
        return "registration_open"
    if submit and current <= submit:
        return "submission_open"
    if comp_start and current < comp_start:
        return "registration_closed" if reg_end else "upcoming"
    if reg_end and current > reg_end:
        return "registration_closed"
    return "unknown"


def choose_primary_deadline(event) -> str | None:
    return event.registration_deadline or event.submission_deadline or event.competition_start or event.competition_end


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()
