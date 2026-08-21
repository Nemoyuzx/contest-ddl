import json
from datetime import datetime

from contestddl.sources import mlh, saikr, summer_camps
from contestddl.utils import CHINA_TZ


class FakeFetcher:
    def __init__(self, payload=None, html=""):
        self.payload = payload
        self.html = html

    def json(self, url):
        return self.payload

    def text(self, url):
        return self.html


NOW = datetime(2026, 8, 22, 12, tzinfo=CHINA_TZ)


def test_saikr_promotion_filter():
    assert saikr._is_promotion("保研规划培训课程")
    assert not saikr._is_promotion("全国大学生智能车竞赛")


def test_saikr_contextual_timeline():
    result = saikr._extract_timeline("报名截止：2026年9月1日 比赛时间：2026年9月12日 08:00")
    assert result["registration_deadline"].startswith("2026-09-01T23:59:59")
    assert result["competition_start"].startswith("2026-09-12T08:00:00")


def test_summer_camp_filters_non_engineering():
    payload = {"camp2026": [
        {"name": "甲大学", "institute": "计算机学院", "description": "", "deadline": "2026-09-01", "website": "https://a.edu.cn", "tags": []},
        {"name": "乙大学", "institute": "历史学院", "description": "古代史", "deadline": "2026-09-02", "website": "https://b.edu.cn", "tags": []},
    ]}
    result = summer_camps.collect(FakeFetcher(payload), NOW)
    assert result.ok
    assert [item.name for item in result.events] == ["甲大学 · 计算机学院"]


def test_mlh_embedded_json_parser():
    page = {"props": {"upcomingEvents": [{
        "id": "1", "name": "AI Student Hack", "startsAt": "2026-09-01T00:00:00Z",
        "endsAt": "2026-09-02T00:00:00Z", "websiteUrl": "https://hack.example",
        "location": "Online", "formatType": "digital", "region": "APAC",
        "customFields": {"hackathon_focus": ["AI"]},
    }]}}
    html = f'<script data-page="app" type="application/json">{json.dumps(page)}</script>'
    result = mlh.collect(FakeFetcher(html=html), NOW)
    assert result.ok
    assert len(result.events) == 1
    assert result.events[0].mode == "online"
