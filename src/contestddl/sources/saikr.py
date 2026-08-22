from __future__ import annotations

import os
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from contestddl.fetch import Fetcher
from contestddl.models import Event, SourceEvidence
from contestddl.sources.common import guarded
from contestddl.utils import CHINA_TZ, clean_text, iso, iso_or_none, now_china, parse_datetime, stable_id

API_BASE = "https://apiv4buffer.saikr.com/api/pc/contest"
LIST_URL = f"{API_BASE}/lists"
DETAIL_URL = f"{API_BASE}/info"
PUBLIC_BASE = "https://new.saikr.com"
REQUEST_HEADERS = {"Origin": PUBLIC_BASE, "Referer": f"{PUBLIC_BASE}/contests"}

# Only request the engineering tracks in scope instead of downloading all of
# Saikr's language, business, art and general-interest competitions.
CATEGORY_IDS = {
    1: "数学建模",
    2: "程序设计",
    4: "机器人",
    5: "电子信息与自动化",
    6: "计算机与信息技术",
    9: "机械工程",
    34: "大数据",
    1006: "人工智能",
}

PROMOTION_KEYWORDS = (
    "培训课程", "课程辅导", "辅导班", "保研规划", "保研咨询", "保送研究生", "留学",
    "雅思", "托福", "考研", "考公", "考编", "教师资格证", "会员", "团购",
    "扫码添加", "免费领取", "校园大使", "志愿者招募",
)
ENGINEERING_PATTERN = re.compile(
    r"数学建模|建模|mathorcup|程序设计|编程|算法|机器人|智能车|机械|力学|结构设计|"
    r"三维|3d|电子|通信|集成电路|芯片|嵌入式|eda|ict|自动化|控制|人工智能|"
    r"\bai\b|aigc|大模型|具身|数智|大数据|数据分析|数据库|信息技术|信息系统|"
    r"网络安全|网络技术|软件|计算机|物联网|工业互联网|航空航天|车辆|汽车|制造",
    re.I,
)


def _is_promotion(title: str) -> bool:
    normalized = clean_text(title).lower()
    return any(word.lower() in normalized for word in PROMOTION_KEYWORDS)


def _is_ctf(title: str) -> bool:
    return bool(re.search(r"(?:^|\W)ctf(?:$|\W)", title, flags=re.I))


def _api_data(payload: object) -> dict:
    if not isinstance(payload, dict) or payload.get("code") != 200 or not isinstance(payload.get("data"), dict):
        raise ValueError("unexpected Saikr API response")
    return payload["data"]


def _unix_iso(value: object) -> str | None:
    try:
        timestamp = int(value or 0)
    except (TypeError, ValueError):
        return None
    return iso(datetime.fromtimestamp(timestamp, CHINA_TZ)) if timestamp > 0 else None


def _plain_html(value: object, limit: int = 2600) -> str:
    soup = BeautifulSoup(str(value or ""), "html.parser")
    for node in soup(["script", "style", "noscript", "template", "svg"]):
        node.decompose()
    return clean_text(soup.get_text(" ", strip=True))[:limit]


def _public_url(value: object) -> str:
    url = str(value or "").strip()
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""
    return url if parts.scheme in {"http", "https"} and parts.netloc else ""


def _normalize_detail_date(value: object, *, end_of_day: bool = False) -> str | None:
    return iso_or_none(str(value or "").replace("/", "-").replace(".", "-"), end_of_day=end_of_day)


def _organizer(value: object, fallback: object = "") -> str:
    if isinstance(value, list):
        return "、".join(clean_text(str(item)) for item in value if clean_text(str(item)))
    return clean_text(str(value or fallback or ""))


def _categories(row: dict, detail: dict) -> list[str]:
    text = " ".join(str(value or "") for value in (
        row.get("contest_name"), row.get("contest_class_second"), detail.get("contest_name"),
        _plain_html(detail.get("content"), limit=10000),
    ))[:12000].lower()
    categories = ["工科竞赛"]
    mappings = {
        "人工智能": ("人工智能", "机器学习", "大模型", "aigc", "具身"),
        "程序设计": ("程序设计", "编程", "算法", "软件"),
        "网络安全": ("网络安全", "信息安全", "密码", "攻防"),
        "机器人": ("机器人", "智能车", "无人机"),
        "电子信息": ("电子", "通信", "集成电路", "芯片", "嵌入式", "eda", "物联网"),
        "自动化": ("自动化", "自动控制", "控制工程"),
        "机械": ("机械", "制造", "力学", "结构设计", "三维"),
        "数学建模": ("数学建模", "mathorcup"),
        "大数据": ("大数据", "数据分析", "数据库"),
    }
    for label, words in mappings.items():
        contains_ai = label == "人工智能" and bool(re.search(r"(?<![a-z])ai(?![a-z])", text, flags=re.I))
        if contains_ai or any(word in text for word in words):
            categories.append(label)
    fallback = CATEGORY_IDS.get(int(row.get("contest_class_second_id") or 0))
    if fallback and fallback not in categories:
        categories.append(fallback)
    return categories


def _schedule(detail: dict) -> list[dict[str, str]]:
    stage = detail.get("contest_stage") or {}
    rows = stage.get("list", []) if isinstance(stage, dict) else []
    result = []
    for row in rows[:12]:
        if not isinstance(row, dict):
            continue
        item = {
            "name": clean_text(str(row.get("name") or "赛程阶段")),
            "content": clean_text(str(row.get("content") or "")),
            "start": _normalize_detail_date(row.get("start_time")) or "",
            "end": _normalize_detail_date(row.get("end_time"), end_of_day=True) or "",
        }
        if any(item.values()):
            result.append(item)
    return result


def _attachments(detail: dict) -> list[dict[str, str]]:
    payload = detail.get("attachment") or {}
    if not isinstance(payload, dict):
        return []
    return [
        {"name": clean_text(str(name)) or "赛事附件", "url": url}
        for name, value in list(payload.items())[:10]
        if (url := _public_url(value))
    ]


def _level(value: object) -> str:
    text = str(value or "")
    if "全球" in text or "国际" in text:
        return "international"
    if "全国" in text:
        return "national"
    if "省" in text:
        return "provincial"
    if "市" in text:
        return "city"
    if "校" in text:
        return "school"
    return ""


def _extreme_date(values: list[str | None], *, latest: bool) -> str | None:
    parsed = [(value, parse_datetime(value)) for value in values if value]
    parsed = [(value, date) for value, date in parsed if date]
    if not parsed:
        return None
    selector = max if latest else min
    return selector(parsed, key=lambda item: item[1])[0]


def _is_in_window(row: dict, current: datetime) -> bool:
    dates = [
        parse_datetime(_unix_iso(row.get(key)))
        for key in ("regist_start_time", "regist_end_time", "contest_start_time", "contest_end_time")
    ]
    dates = [value for value in dates if value]
    return bool(dates and max(dates) >= current - timedelta(days=30) and min(dates) <= current + timedelta(days=500))


def _selected(row: dict, current: datetime) -> bool:
    title = clean_text(str(row.get("contest_name") or ""))
    searchable = f"{title} {row.get('organiser') or ''} {row.get('contest_class_second') or ''}"
    return bool(
        title and not _is_promotion(title) and not _is_ctf(title)
        and ENGINEERING_PATTERN.search(searchable) and _is_in_window(row, current)
    )


def _event_from_api(row: dict, detail: dict, current: datetime) -> Event:
    title = clean_text(str(detail.get("contest_name") or row.get("contest_name") or "赛氪赛事"))
    slug = str(row.get("contest_url") or detail.get("old_url") or "").strip("/")
    official_url = f"{PUBLIC_BASE}/{slug}" if slug else f"{PUBLIC_BASE}/contests"

    registration_start = _normalize_detail_date(detail.get("regist_start_time")) or _unix_iso(row.get("regist_start_time"))
    registration_deadline = _normalize_detail_date(detail.get("regist_end_time"), end_of_day=True) or _unix_iso(row.get("regist_end_time"))
    competition_start = _normalize_detail_date(detail.get("contest_start_time")) or _unix_iso(row.get("contest_start_time"))
    competition_end = _normalize_detail_date(detail.get("contest_end_time"), end_of_day=True) or _unix_iso(row.get("contest_end_time"))
    schedule = _schedule(detail)
    registration_stages = [stage for stage in schedule if re.search(r"报名|注册|征集", f"{stage['name']} {stage['content']}")]
    competition_stages = [stage for stage in schedule if stage not in registration_stages]
    registration_start = _extreme_date([registration_start, *(stage["start"] for stage in registration_stages)], latest=False)
    registration_deadline = _extreme_date([registration_deadline, *(stage["end"] for stage in registration_stages)], latest=True)
    competition_start = _extreme_date([competition_start, *(stage["start"] for stage in competition_stages)], latest=False)
    competition_end = _extreme_date([competition_end, *(stage["end"] for stage in competition_stages)], latest=True)
    participation = detail.get("participation_detail") or {}
    eligibility = clean_text(str(participation.get("detail") or "")) if isinstance(participation, dict) else ""
    description = _plain_html(detail.get("content"))
    organizer = _organizer(detail.get("organiser"), row.get("organiser"))
    evidence_fields = [
        "name", "organizer", "description", "eligibility", "schedule", "attachments",
        "registration_start", "registration_deadline", "competition_start", "competition_end",
    ]
    source = SourceEvidence("赛氪公开前端 API", official_url, "aggregator_api", 2, iso(current), evidence_fields)
    return Event(
        id=stable_id(title, "competition", competition_start or registration_deadline, f"saikr-{row.get('contest_id')}"),
        name=title,
        event_type="competition",
        categories=_categories(row, detail),
        official_url=official_url,
        source=source,
        organizer=organizer,
        level=_level(detail.get("contest_level") or row.get("level_name")),
        region="global" if _level(detail.get("contest_level") or row.get("level_name")) == "international" else "china",
        eligibility=eligibility or clean_text(str(row.get("enter_range") or "college students")),
        registration_start=registration_start,
        registration_deadline=registration_deadline,
        competition_start=competition_start,
        competition_end=competition_end,
        description=description,
        schedule=schedule,
        attachments=_attachments(detail),
        image_url=_public_url(detail.get("web_pic_big") or row.get("thumb_pic")),
        tags=["saikr", "needs_official_verification"],
        notes="赛氪公开前端 API 用于赛事发现；报名或提交前请回到主办方官网复核。",
    )


def collect(fetcher, now=None, limit: int | None = None):
    current = now or now_china()
    max_events = max(1, limit or int(os.getenv("SAIKR_LIMIT", "72")))
    workers = max(1, min(8, int(os.getenv("SAIKR_WORKERS", "6"))))

    def run():
        rows_by_slug: dict[str, dict] = {}
        list_failures: list[dict[str, str]] = []
        category_counts: Counter[str] = Counter()
        for category_id, category_name in CATEGORY_IDS.items():
            try:
                payload = fetcher.json(
                    LIST_URL,
                    params={"page": 1, "limit": 100, "univs_id": "", "class_id": category_id, "level": 0, "sort": 0},
                    headers=REQUEST_HEADERS,
                )
                rows = _api_data(payload).get("list", [])
                category_counts[category_name] = len(rows)
                for row in rows:
                    if isinstance(row, dict) and row.get("contest_url"):
                        rows_by_slug.setdefault(str(row["contest_url"]), row)
            except Exception as exc:
                list_failures.append({"category": category_name, "error": f"{type(exc).__name__}: {str(exc)[:100]}"})
        if not rows_by_slug and list_failures:
            raise RuntimeError("all Saikr category list requests failed")

        selected = [row for row in rows_by_slug.values() if _selected(row, current)]
        selected.sort(key=lambda row: int(row.get("regist_end_time") or row.get("contest_start_time") or 0))
        selected = selected[:max_events]

        def fetch_detail(row: dict):
            local = Fetcher(timeout=15, delay=0.05) if isinstance(fetcher, Fetcher) else fetcher
            slug = str(row.get("contest_url") or "").strip("/").split("/")[-1]
            try:
                payload = local.json(
                    DETAIL_URL,
                    params={"contest_url": slug, "isp": ""},
                    headers=REQUEST_HEADERS,
                )
                return row, _api_data(payload), ""
            except Exception as exc:
                return row, {}, f"{type(exc).__name__}: {str(exc)[:120]}"

        if isinstance(fetcher, Fetcher):
            with ThreadPoolExecutor(max_workers=min(workers, len(selected) or 1)) as executor:
                detailed = list(executor.map(fetch_detail, selected))
        else:
            detailed = [fetch_detail(row) for row in selected]

        events = [_event_from_api(row, detail, current) for row, detail, _ in detailed]
        detail_failures = [
            {"contest": row.get("contest_name"), "error": error}
            for row, _, error in detailed if error
        ]
        details = {
            "api": {"lists": LIST_URL, "info": DETAIL_URL},
            "category_records": dict(category_counts),
            "unique_list_records": len(rows_by_slug),
            "engineering_current_selected": len(selected),
            "detail_success": len(detailed) - len(detail_failures),
            "detail_failures": detail_failures[:10],
            "list_failures": list_failures,
        }
        return events, details

    return guarded("saikr", LIST_URL, run)
