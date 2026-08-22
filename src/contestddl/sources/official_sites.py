from __future__ import annotations

import ipaddress
import os
import re
import socket
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from functools import lru_cache
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

from contestddl.fetch import Fetcher
from contestddl.models import Event, SourceEvidence
from contestddl.sources.common import guarded
from contestddl.utils import CHINA_TZ, clean_text, iso, now_china, stable_id

CATALOG_URL = "https://raw.githubusercontent.com/xcg1125/college-competition-ddl/main/competitions.json"

ALLOWED_CATEGORIES = {
    "创新创业", "数学建模", "程序设计", "电子设计", "机械设计", "智能车", "工程实践",
    "工程制图", "智能制造", "服务外包", "光电技术", "集成电路", "机械工程", "软件设计",
    "通信技术", "信息技术", "嵌入式系统", "机器人", "人工智能", "计算机系统", "物联网",
    "信息安全", "创新设计",
}

LINK_KEYWORDS = ("报名", "通知", "竞赛", "大赛", "参赛", "赛项", "启动", "章程", "规程", "赛程")
LINK_DEADLINE_KEYWORDS = ("报名截止", "截止时间", "提交截止", "作品提交")
LINK_EXCLUSIONS = ("获奖", "晋级", "名单", "证书", "圆满落幕", "结果公布", "赛事回顾", "新闻报道")
DATE_TOKEN = re.compile(
    r"20\d{2}\s*[年./-]\s*\d{1,2}\s*[月./-]\s*\d{1,2}\s*日?"
    r"(?:\s*[（(][^）)]{1,8}[）)])?"
    r"(?:\s*(?:上午|下午|晚上|中午)?\s*\d{1,2}\s*(?:[:：时点])\s*\d{0,2}\s*分?)?"
)
TRANSPARENT_PROXY_NET = ipaddress.ip_network("198.18.0.0/15")
PUBLICATION_LABEL = re.compile(r"发布者|发布时间|发布日期|更新日期|更新时间|浏览量")
REGISTRATION_LABEL = re.compile(
    r"(?:报名|注册|申报|参赛申请).{0,12}(?:开始|起止|截止|截至|时间|日期|开放|结束|延迟|延长|关闭)"
)
SUBMISSION_LABEL = re.compile(
    r"(?:(?:作品|材料|项目|文档).{0,12}(?:提交|上传|报送)|(?:提交|上传|报送).{0,12}(?:作品|材料|项目|文档))"
    r".{0,12}(?:截止|截至|时间|日期|开始|结束)"
)
COMPETITION_LABEL = re.compile(
    r"(?:比赛|竞赛|初赛|复赛|决赛|答辩).{0,12}(?:时间|日期|开始|开赛|举行|定于|赛期)"
)
SHORT_SPLIT_LABEL = re.compile(
    r"^(?:报名|注册|申报|参赛申请|作品提交|材料提交|项目提交|文档提交|比赛|竞赛|初赛|复赛|决赛|答辩)"
    r"(?:开始|截止|截至|起止|时间|日期|赛期|开放|结束)?[：:]?$"
)


def _source_domain(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    parts = host.split(".")
    if len(parts) < 2:
        return host
    suffix = ".".join(parts[-2:])
    multipart = {"ac.cn", "com.cn", "edu.cn", "gov.cn", "net.cn", "org.cn", "co.uk", "org.uk"}
    return ".".join(parts[-3:] if suffix in multipart and len(parts) >= 3 else parts[-2:])


def _safe_public_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return False
        if parsed.port and parsed.port not in {80, 443}:
            return False
        host = parsed.hostname.lower()
        if host in {"localhost", "0.0.0.0", "::1"}:
            return False
        try:
            address = ipaddress.ip_address(host)
            return address.is_global
        except ValueError:
            return True
    except ValueError:
        return False


@lru_cache(maxsize=256)
def _host_resolves_public(host: str, port: int) -> bool:
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
        # Codex desktop routes external DNS through RFC 2544 benchmark addresses.
        # Literal 198.18/15 URLs remain blocked by _safe_public_url; only resolved
        # hostnames may use this transparent-proxy range during local verification.
        return bool(addresses) and all(
            (parsed := ipaddress.ip_address(address)).is_global or parsed in TRANSPARENT_PROXY_NET
            for address in addresses
        )
    except (OSError, ValueError):
        return False


def _safe_get(fetcher, url: str, *, timeout: int):
    current = url
    for _ in range(5):
        parsed = urlsplit(current)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not _safe_public_url(current) or not _host_resolves_public(parsed.hostname or "", port):
            raise ValueError(f"unsafe or unresolvable URL: {current}")
        response = fetcher.get(current, timeout=timeout, allow_redirects=False)
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            if not location:
                raise ValueError(f"redirect without location: {current}")
            current = urljoin(current, location)
            continue
        return response
    raise ValueError(f"too many redirects: {url}")


def _robots_allows(fetcher, url: str) -> bool:
    parsed = urlsplit(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        response = _safe_get(fetcher, robots_url, timeout=6)
        if not response.encoding or response.encoding.lower() in {"iso-8859-1", "latin-1"}:
            response.encoding = response.apparent_encoding
        text = response.text
    except Exception:
        return True
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(text.splitlines())
    return parser.can_fetch("contest-ddl", url)


def _fetch_html(fetcher, url: str) -> str:
    response = _safe_get(fetcher, url, timeout=10)
    content_type = response.headers.get("Content-Type", "").lower()
    if content_type and "html" not in content_type and "xhtml" not in content_type:
        raise ValueError(f"unsupported content type: {content_type.split(';')[0]}")
    if not response.encoding or response.encoding.lower() in {"iso-8859-1", "latin-1"}:
        response.encoding = response.apparent_encoding
    return response.text


def _parse_date_token(token: str, *, end_of_day: bool = False) -> datetime | None:
    match = re.search(
        r"(?P<year>20\d{2})\s*[年./-]\s*(?P<month>\d{1,2})\s*[月./-]\s*(?P<day>\d{1,2})\s*日?"
        r"(?:\s*[（(][^）)]{1,8}[）)])?"
        r"(?:\s*(?P<period>上午|下午|晚上|中午)?\s*(?P<hour>\d{1,2})\s*(?:[:：时点])\s*(?P<minute>\d{0,2})\s*分?)?",
        token,
    )
    if not match:
        return None
    hour = int(match.group("hour") or (23 if end_of_day else 0))
    minute = int(match.group("minute") or (59 if end_of_day else 0))
    second = 59 if end_of_day and not match.group("hour") else 0
    if hour >= 24:
        hour, minute, second = 23, 59, 59
    if match.group("period") in {"下午", "晚上"} and hour < 12:
        hour += 12
    if match.group("period") == "中午" and hour < 11:
        hour += 12
    try:
        return datetime(
            int(match.group("year")), int(match.group("month")), int(match.group("day")),
            hour, minute, second, tzinfo=CHINA_TZ,
        )
    except ValueError:
        return None


def _visible_nodes(html: str) -> tuple[BeautifulSoup, list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript", "template"]):
        node.decompose()
    return soup, [clean_text(value) for value in soup.stripped_strings if clean_text(value)]


def _extract_timeline(html: str, now: datetime) -> dict[str, str]:
    _, nodes = _visible_nodes(html)
    candidates: dict[str, list[tuple[int, datetime]]] = {
        "registration_start": [], "registration_deadline": [], "submission_deadline": [],
        "competition_start": [], "competition_end": [],
    }
    lower_bound, upper_bound = now - timedelta(days=120), now + timedelta(days=500)

    for index, own in enumerate(nodes):
        own_has_date = bool(DATE_TOKEN.search(own))
        if not own_has_date or PUBLICATION_LABEL.search(own):
            continue
        # Dates are only interpreted using their own text. The sole exception is
        # a short adjacent table label such as "报名截止：". This prevents a news
        # list's publication date from inheriting meaning from a nearby headline.
        semantic_context = own
        if not any(pattern.search(own) for pattern in (REGISTRATION_LABEL, SUBMISSION_LABEL, COMPETITION_LABEL)):
            neighbors = nodes[max(0, index - 1):index] + nodes[index + 1:index + 2]
            split_label = next((value for value in neighbors if len(value) <= 18 and SHORT_SPLIT_LABEL.fullmatch(value)), "")
            if not split_label:
                continue
            semantic_context = f"{split_label} {own}"
        tokens = DATE_TOKEN.findall(own)
        base_score = 4

        def parsed_dates(end_of_day=False):
            values = [_parse_date_token(token, end_of_day=end_of_day) for token in tokens]
            return [value for value in values if value and lower_bound <= value <= upper_bound]

        registration = bool(REGISTRATION_LABEL.search(semantic_context))
        deadline_language = bool(re.search(r"截止|截至|延长至|延迟至|关闭|结束", semantic_context))
        range_language = bool(re.search(r"起止|时间|日期|开放", semantic_context))
        submission = bool(SUBMISSION_LABEL.search(semantic_context))
        competition = bool(COMPETITION_LABEL.search(semantic_context))

        if registration:
            values = parsed_dates(end_of_day=True)
            if values and (deadline_language or (range_language and len(values) >= 2)):
                score = base_score + 5 + (3 if re.search(r"截止|截至|延长至", own) else 0)
                candidates["registration_deadline"].append((score, values[-1]))
                if len(values) >= 2:
                    candidates["registration_start"].append((score, values[0].replace(hour=0, minute=0, second=0)))
        if submission and deadline_language:
            values = parsed_dates(end_of_day=True)
            if values:
                score = base_score + 6 + (3 if re.search(r"截止|截至|延长至", own) else 0)
                candidates["submission_deadline"].append((score, values[-1]))
        if competition:
            values = parsed_dates(end_of_day=False)
            if values:
                score = base_score + 4 + (3 if re.search(r"比赛时间|竞赛时间|开赛|举行", own) else 0)
                candidates["competition_start"].append((score, values[0]))
                if len(values) >= 2:
                    candidates["competition_end"].append((score, values[-1]))

    result = {}
    for field, values in candidates.items():
        if not values:
            continue
        _, selected = max(values, key=lambda item: (item[0], item[1].timestamp()))
        result[field] = iso(selected)
    return result


def _candidate_links(html: str, base_url: str, row: dict, now: datetime, limit: int = 2) -> list[tuple[int, str]]:
    soup, _ = _visible_nodes(html)
    base_domain = _source_domain(base_url)
    aliases = [str(row.get("title", "")), str(row.get("name", ""))]
    scored: dict[str, int] = {}
    for anchor in soup.select("a[href]"):
        text = clean_text(anchor.get_text(" ", strip=True) or anchor.get("title", ""))
        href = urljoin(base_url, anchor.get("href", ""))
        if not text or not _safe_public_url(href) or _source_domain(href) != base_domain:
            continue
        if urlsplit(href).path.lower().endswith((".pdf", ".doc", ".docx", ".zip", ".rar")):
            continue
        score = 0
        if str(now.year) in text or str(now.year + 1) in text:
            score += 6
        score += sum(2 for keyword in LINK_KEYWORDS if keyword in text)
        score += sum(6 for keyword in LINK_DEADLINE_KEYWORDS if keyword in text)
        score += sum(4 for alias in aliases if len(alias) >= 4 and alias in text)
        score -= sum(7 for keyword in LINK_EXCLUSIONS if keyword in text)
        if score >= 4:
            # Some legacy competition servers only work on the www hostname.
            # Preserve the exact official link instead of canonicalizing it.
            normalized = href.split("#", 1)[0]
            scored[normalized] = max(score, scored.get(normalized, -100))
    return sorted(((score, url) for url, score in scored.items()), reverse=True)[:limit]


def _catalog_selected(row: dict) -> bool:
    text = " ".join([str(row.get("title", "")), str(row.get("name", "")), *map(str, row.get("tags", []))])
    if row.get("category") not in ALLOWED_CATEGORIES or re.search(r"\bctf\b", text, flags=re.I):
        return False
    # Challenge Cup alternates science/entrepreneurship editions on one site;
    # a generic crawler cannot safely assign one notice to the right catalog row.
    return "挑战杯" not in text


def _crawl_one(row: dict, shared_fetcher, now: datetime) -> tuple[Event | None, dict]:
    website = str(row.get("website", "")).strip()
    if not _safe_public_url(website):
        return None, {"title": row.get("title"), "reason": "unsafe_or_invalid_url"}
    fetcher = Fetcher(timeout=10, delay=0.15) if isinstance(shared_fetcher, Fetcher) else shared_fetcher
    if not _robots_allows(fetcher, website):
        return None, {"title": row.get("title"), "reason": "robots_disallowed", "url": website}
    try:
        homepage = _fetch_html(fetcher, website)
    except Exception as exc:
        return None, {"title": row.get("title"), "reason": "fetch_failed", "url": website, "error": f"{type(exc).__name__}: {str(exc)[:120]}"}

    pages: list[tuple[int, str, str]] = [(0, website, homepage)]
    for score, url in _candidate_links(homepage, website, row, now):
        if not _robots_allows(fetcher, url):
            continue
        try:
            pages.append((score, url, _fetch_html(fetcher, url)))
        except Exception:
            continue

    extracted: dict[str, tuple[int, str, str]] = {}
    for link_score, url, html in pages:
        timeline = _extract_timeline(html, now)
        page_score = link_score + len(timeline) * 10
        for field, value in timeline.items():
            if field not in extracted or page_score > extracted[field][0]:
                extracted[field] = (page_score, value, url)
    if not extracted:
        return None, {"title": row.get("title"), "reason": "no_labeled_current_timeline", "url": website}

    timeline = {field: value for field, (_, value, _) in extracted.items()}
    best_url = max(extracted.values(), key=lambda value: value[0])[2]
    name = str(row.get("name") or row.get("title") or "赛事").strip()
    fields_by_url: dict[str, list[str]] = {}
    for field, (_, _, url) in extracted.items():
        fields_by_url.setdefault(url, []).append(field)
    evidences = [
        SourceEvidence("赛事官网自动核验", url, "official_site", 5, iso(now), sorted(fields))
        for url, fields in fields_by_url.items()
    ]
    source = next(evidence for evidence in evidences if evidence.url == best_url)
    event = Event(
        id=stable_id(name, "competition", timeline.get("competition_start") or timeline.get("registration_deadline"), f"official-catalog-{row.get('id')}"),
        name=name, event_type="competition", categories=[str(row.get("category") or "工科竞赛")],
        official_url=best_url, source=source, organizer=str(row.get("organizer", "")),
        level={"S": "top", "A": "national", "B": "national", "C": "national"}.get(str(row.get("level", "")), "national"),
        region="global" if "国际" in name or "icpc.global" in website else "china",
        eligibility="college students", registration_start=timeline.get("registration_start"),
        registration_deadline=timeline.get("registration_deadline"), competition_start=timeline.get("competition_start"),
        competition_end=timeline.get("competition_end"), submission_deadline=timeline.get("submission_deadline"),
        tags=[*map(str, row.get("tags", [])), "official_site"],
        notes=(str(row.get("description", "")).strip() + "；日期由官网公开页面自动提取，提交前请复核原文。").strip("；"),
        confidence="high", verification_status="official_site", sources=evidences,
    )
    return event, {
        "title": row.get("title"), "reason": "accepted", "url": best_url,
        "fields": sorted(timeline), "field_urls": {url: sorted(fields) for url, fields in fields_by_url.items()},
    }


def collect(fetcher, now=None):
    current = now or now_china()
    limit = max(1, int(os.getenv("OFFICIAL_SITE_LIMIT", "36")))
    workers = max(1, min(8, int(os.getenv("OFFICIAL_SITE_WORKERS", "6"))))

    def run():
        catalog = fetcher.json(CATALOG_URL)
        selected = [row for row in catalog if _catalog_selected(row)][:limit]
        with ThreadPoolExecutor(max_workers=min(workers, len(selected) or 1)) as executor:
            crawled = list(executor.map(lambda row: _crawl_one(row, fetcher, current), selected))
        events = [event for event, _ in crawled if event]
        outcomes = [outcome for _, outcome in crawled]
        reason_counts = Counter(outcome["reason"] for outcome in outcomes)
        details = {
            "catalog_records": len(catalog), "engineering_sites_selected": len(selected),
            "accepted": len(events), "outcomes": dict(sorted(reason_counts.items())),
            "accepted_sites": [outcome for outcome in outcomes if outcome["reason"] == "accepted"],
            "failure_samples": [outcome for outcome in outcomes if outcome["reason"] != "accepted"][:12],
            "catalog_deadlines_used": False,
        }
        return events, details

    return guarded("official_sites", CATALOG_URL, run)
