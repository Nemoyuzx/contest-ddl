from __future__ import annotations

import re
import time
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from contestddl.models import Event, SourceEvidence
from contestddl.sources.common import guarded
from contestddl.utils import canonical_url, clean_text, engineering_relevant, iso, iso_or_none, normalize_title, now_china, stable_id

LIST_URL = "https://www.saikr.com/index/hot/contest"

PROMOTION_KEYWORDS = (
    "培训", "课程", "辅导班", "保研规划", "保研咨询", "保送研究生", "留学", "雅思", "托福",
    "考研", "考公", "考编", "教师资格证", "会员", "团购", "扫码添加", "免费领取",
)

DATE = r"((?:20\d{2})[年./\-]\d{1,2}[月./\-]\d{1,2}(?:日)?(?:\s+\d{1,2}[:：]\d{2}(?::\d{2})?)?)"
GENERAL_STEM_TITLES = ("挑战杯", "互联网+", "创新创业大赛", "中国国际大学生创新大赛", "创青春")


def _is_promotion(title: str) -> bool:
    identity = normalize_title(title)
    return any(word in identity for word in PROMOTION_KEYWORDS)


def _parse_date(value: str, *, end_of_day=False) -> str | None:
    normalized = value.replace("年", "-").replace("月", "-").replace("日", "").replace(".", "-").replace("/", "-").replace("：", ":")
    return iso_or_none(normalized, end_of_day=end_of_day)


def _extract_timeline(text: str) -> dict:
    timeline = {}
    patterns = {
        "registration_deadline": [rf"(?:报名截止|截止报名|报名时间[^\n]{{0,40}}?(?:至|到|~|—|-))[^\d]{{0,12}}{DATE}", rf"{DATE}[^。；\n]{{0,10}}(?:报名截止|截止报名)"],
        "competition_start": [rf"(?:比赛时间|竞赛时间|考试时间|决赛时间|开赛时间)[^\d]{{0,12}}{DATE}"],
        "submission_deadline": [rf"(?:作品|项目|材料)?(?:提交截止|截止提交)[^\d]{{0,12}}{DATE}"],
    }
    for field, candidates in patterns.items():
        for pattern in candidates:
            match = re.search(pattern, text, flags=re.I)
            if match:
                timeline[field] = _parse_date(match.group(1), end_of_day=field.endswith("deadline"))
                break
    return timeline


def collect(fetcher, now=None, limit: int = 24):
    current = now or now_china()

    def run():
        soup = BeautifulSoup(fetcher.text(LIST_URL), "html.parser")
        candidates = []
        seen_urls, seen_titles = set(), set()
        for link in soup.select("a[href]"):
            url = urljoin(LIST_URL, link.get("href", ""))
            parsed = urlsplit(url)
            if not parsed.netloc.endswith("saikr.com") or not re.search(r"/(vse|vs|contest|races)/", parsed.path, re.I):
                continue
            title = clean_text(link.get("title") or link.get_text(" ", strip=True))
            if len(title) < 4 or _is_promotion(title):
                continue
            title_key, normalized_url = normalize_title(title), canonical_url(url)
            if not title_key or title_key in seen_titles or normalized_url in seen_urls:
                continue
            seen_titles.add(title_key)
            seen_urls.add(normalized_url)
            context = clean_text(link.parent.get_text(" ", strip=True) if link.parent else title)
            if not engineering_relevant(title) and not any(word in title for word in GENERAL_STEM_TITLES):
                continue
            candidates.append((title, normalized_url, context))

        events = []
        for index, (list_title, url, context) in enumerate(candidates[:limit]):
            text = context
            title = list_title
            try:
                detail_soup = BeautifulSoup(fetcher.text(url), "html.parser")
                page_title = clean_text(detail_soup.title.get_text(" ") if detail_soup.title else "")
                if page_title and not page_title.startswith("赛氪 -"):
                    title = re.sub(r"-大学生竞赛-赛氪.*$", "", page_title).strip() or list_title
                for bad in detail_soup(["script", "style", "noscript"]):
                    bad.decompose()
                text = clean_text(detail_soup.get_text("\n", strip=True))[:12000]
            except Exception:
                pass
            if _is_promotion(title) or (not engineering_relevant(title) and not any(word in title for word in GENERAL_STEM_TITLES)):
                continue
            timeline = _extract_timeline(text)
            if not any(timeline.values()):
                continue
            source = SourceEvidence("赛氪公开赛事页", url, "aggregator", 2, iso(current), ["name", *timeline.keys()])
            categories = ["工科竞赛"]
            for label, words in {
                "人工智能": ("人工智能", "ai", "机器学习"), "程序设计": ("程序设计", "编程", "软件"),
                "网络安全": ("网络安全", "ctf", "信息安全"), "机器人": ("机器人", "智能车"),
                "电子信息": ("电子", "通信", "集成电路", "物联网"), "自动化": ("自动化", "控制"),
                "机械": ("机械", "制造"), "数学建模": ("数学建模",),
            }.items():
                if any(word.lower() in f"{title} {text[:1000]}".lower() for word in words):
                    categories.append(label)
            event = Event(
                id=stable_id(title, "competition", timeline.get("competition_start") or timeline.get("registration_deadline"), "saikr"),
                name=title, event_type="competition", categories=list(dict.fromkeys(categories)), official_url=url,
                source=source, region="china", eligibility="college students",
                registration_deadline=timeline.get("registration_deadline"), competition_start=timeline.get("competition_start"),
                submission_deadline=timeline.get("submission_deadline"), tags=["saikr", "needs_official_verification"],
                notes="赛氪用于赛事发现；聚合站日期应回到主办方官网复核。",
            )
            events.append(event)
            if index + 1 < min(limit, len(candidates)):
                time.sleep(0.12)
        return events

    return guarded("saikr", LIST_URL, run)
