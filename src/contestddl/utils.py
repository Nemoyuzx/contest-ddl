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
MARKETING_TITLE_KEYWORDS = (
    "今日", "明日", "最后", "倒计时", "截止", "即将", "报名", "考试", "开学",
    "证书", "领证", "领取", "热门", "福利", "免费", "奖金", "奖品", "收藏",
    "加分", "获奖", "题目", "题库", "仅剩", "速来", "速报",
)
LEADING_BRACKET = re.compile(r"^\s*[【\[](?P<label>[^】\]]{1,50})[】\]]\s*")
SAIKR_NONCOMPETITION_STAGE = re.compile(
    r"成果转化|成果推广|颁奖|授奖|奖项公示|名单公示|结果公示|结果公布|启动宣传|宣传推广|赛后"
)
SAIKR_REGISTRATION_STAGE = re.compile(r"报名|注册|征集")
SAIKR_SUBMISSION_STAGE = re.compile(r"摘要|论文|投稿|截稿|作品提交|材料提交|报告.*提交|项目提交")


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


def clean_event_title(title: str) -> str:
    """Remove leading promotional badges while preserving official bracketed names."""
    text = clean_text(title)
    while match := LEADING_BRACKET.match(text):
        if not any(keyword in match.group("label") for keyword in MARKETING_TITLE_KEYWORDS):
            break
        text = text[match.end():].lstrip(" -—_:：")
    return clean_text(text)


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


def saikr_stage_kind(stage: dict) -> str:
    """Classify a Saikr stage by its name, not incidental words in its content.

    Parentheses commonly contain status notes such as "报名中" or "获奖名单已公布"
    on an actual competition round. Keep the full stage for display, but do
    not let those notes turn its dates into another kind of milestone.
    """
    name = clean_text(str(stage.get("name") or ""))
    core_name = re.split(r"[（(]", name, maxsplit=1)[0] or name
    if SAIKR_NONCOMPETITION_STAGE.search(core_name):
        return "informational"
    if SAIKR_REGISTRATION_STAGE.search(core_name):
        return "registration"
    if SAIKR_SUBMISSION_STAGE.search(core_name):
        return "submission"
    return "competition"


def is_saikr_noncompetition_stage(stage: dict) -> bool:
    return saikr_stage_kind(stage) == "informational"


def saikr_competition_end_without_post_event(event) -> str | None:
    """Repair a cached Saikr end date that came solely from a later ceremony.

    Older JSON snapshots did not keep the original top-level API date. Only
    change the cached field when it equals a known non-competition stage end
    and a dated competition round provides a defensible replacement.
    """
    if event.source.name != "赛氪公开前端 API" or "saikr" not in event.tags or not event.competition_end:
        return None
    current_end = parse_datetime(event.competition_end)
    if not current_end:
        return None
    stages = event.schedule if isinstance(event.schedule, list) else []
    if not any(
        isinstance(stage, dict) and is_saikr_noncompetition_stage(stage)
        and parse_datetime(stage.get("end")) == current_end
        for stage in stages
    ):
        return None
    rounds = [
        (stage.get("end"), parse_datetime(stage.get("end")))
        for stage in stages
        if isinstance(stage, dict) and saikr_stage_kind(stage) == "competition" and stage.get("end")
    ]
    rounds = [(value, date) for value, date in rounds if date]
    return max(rounds, key=lambda entry: entry[1])[0] if rounds else None


def compute_status(event, now: datetime | None = None) -> str:
    current = now or now_china()
    reg_start = parse_datetime(event.registration_start)
    reg_end = parse_datetime(event.registration_deadline)
    comp_start = parse_datetime(event.competition_start)
    comp_end = parse_datetime(event.competition_end)
    abstract = parse_datetime(getattr(event, "abstract_deadline", None))
    submit = parse_datetime(event.submission_deadline)
    schedule = event.schedule if isinstance(getattr(event, "schedule", None), list) else []
    registration_stages, submission_stages, competition_stages = [], [], []
    for stage in schedule:
        if not isinstance(stage, dict):
            continue
        saikr_kind = saikr_stage_kind(stage) if "saikr" in event.tags else None
        if saikr_kind == "informational":
            continue
        start, end = parse_datetime(stage.get("start")), parse_datetime(stage.get("end"))
        if not start and not end:
            continue
        if saikr_kind:
            target = {
                "registration": registration_stages,
                "submission": submission_stages,
                "competition": competition_stages,
            }[saikr_kind]
        else:
            label = f"{stage.get('name', '')} {stage.get('content', '')}"
            if re.search(r"报名|注册|征集", label):
                target = registration_stages
            elif re.search(r"摘要|论文|投稿|截稿|作品提交|材料提交", label):
                target = submission_stages
            else:
                target = competition_stages
        target.append((start, end))
    if any(start and current >= start and (not end or current <= end) for start, end in competition_stages):
        return "ongoing"
    if any((not start or current >= start) and end and current <= end for start, end in registration_stages):
        return "registration_open"
    if any(start and current < start for start, _ in registration_stages):
        return "registration_upcoming"
    if reg_start and current < reg_start:
        return "registration_upcoming"
    if reg_end and current <= reg_end:
        return "registration_open"
    if any((not start or current >= start) and end and current <= end for start, end in submission_stages):
        return "submission_open"
    if any(start and current < start for start, _ in submission_stages):
        return "submission_upcoming"
    if abstract and current <= abstract:
        return "submission_open"
    if submit and current <= submit:
        return "submission_open"
    if any(start and current < start for start, _ in competition_stages):
        return "upcoming"
    if competition_stages and all(end and current > end for _, end in competition_stages):
        return "ended"
    if comp_end and current > comp_end:
        return "ended"
    if comp_start and current >= comp_start and (not comp_end or current <= comp_end):
        return "ongoing"
    if reg_start and current < reg_start:
        return "registration_upcoming"
    if reg_end and current <= reg_end:
        return "registration_open"
    if comp_start and current < comp_start:
        return "registration_closed" if reg_end else "upcoming"
    if reg_end and current > reg_end:
        return "registration_closed"
    if submission_stages and all(end and current > end for _, end in submission_stages):
        return "submission_closed"
    if (abstract or submit) and all(value is None or current > value for value in (abstract, submit)):
        return "submission_closed"
    return "unknown"


def choose_primary_deadline(event, now: datetime | None = None) -> str | None:
    """Choose the nearest upcoming milestone instead of the first populated field."""
    current = now or now_china()
    values = [
        event.registration_deadline,
        getattr(event, "abstract_deadline", None),
        event.submission_deadline,
        event.competition_start,
        event.competition_end,
    ]
    for stage in event.schedule if isinstance(getattr(event, "schedule", None), list) else []:
        if isinstance(stage, dict):
            if "saikr" in event.tags and is_saikr_noncompetition_stage(stage):
                continue
            values.extend((stage.get("start"), stage.get("end")))
    parsed = [(value, parse_datetime(value)) for value in values if value]
    parsed = [(value, date) for value, date in parsed if date]
    future = [(value, date) for value, date in parsed if date >= current]
    if future:
        return min(future, key=lambda item: item[1])[0]
    return max(parsed, key=lambda item: item[1])[0] if parsed else None


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()
