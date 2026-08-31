import json
from datetime import datetime

import yaml

from contestddl.sources import ccfddl, mlh, official_sites, saikr, summer_camps
from contestddl.utils import CHINA_TZ


class FakeFetcher:
    def __init__(self, payload=None, html=""):
        self.payload = payload
        self.html = html

    def json(self, url, **kwargs):
        return self.payload

    def text(self, url, **kwargs):
        return self.html


NOW = datetime(2026, 8, 22, 12, tzinfo=CHINA_TZ)


def test_saikr_promotion_filter():
    assert saikr._is_promotion("保研规划培训课程")
    assert not saikr._is_promotion("全国大学生智能车竞赛")


def test_saikr_api_detail_becomes_rich_event():
    row = {
        "contest_id": 59224, "contest_name": "2026高校大学生人工智能大赛", "contest_url": "vse/HZRGZN",
        "regist_start_time": 1782867600, "regist_end_time": 1789912800,
        "contest_start_time": 1789866000, "contest_end_time": 1789916400,
        "level_name": "全国性", "contest_class_second_id": 1006, "contest_class_second": "ai",
    }
    detail = {
        "contest_name": row["contest_name"], "organiser": ["主办单位甲", "主办单位乙"],
        "regist_start_time": "2026/07/01 09:00:00", "regist_end_time": "2026/09/20 22:00:00",
        "contest_start_time": "2026/09/20 09:00:00", "contest_end_time": "2026/09/20 23:00:00",
        "participation_detail": {"detail": "全国高校学生"},
        "content": "<p>面向高校的人工智能实践赛事。</p><script>bad()</script>",
        "contest_stage": {"list": [{"name": "决赛", "start_time": "2026.09.20 09:00:00", "end_time": "2026.09.20 23:00:00"}]},
        "attachment": {"通知.pdf": "https://files.example/notice.pdf"},
    }
    event = saikr._event_from_api(row, detail, NOW)
    assert event.source.name == "赛氪公开前端 API"
    assert event.organizer == "主办单位甲、主办单位乙"
    assert event.registration_deadline.startswith("2026-09-20T22:00:00")
    assert event.description == "面向高校的人工智能实践赛事。"
    assert event.schedule[0]["name"] == "决赛"
    assert event.competition_end.startswith("2026-09-20T23:00:00")
    assert event.attachments[0]["url"] == "https://files.example/notice.pdf"


def test_saikr_event_removes_marketing_title_prefix():
    row = {
        "contest_id": 1, "contest_name": "【9月开学领证书】2026年大学生网络信息技术大赛",
        "contest_url": "vse/example", "regist_end_time": 1789912800, "contest_class_second_id": 6,
    }
    event = saikr._event_from_api(row, {}, NOW)
    assert event.name == "2026年大学生网络信息技术大赛"


def test_summer_camp_filters_non_engineering():
    payload = {"camp2026": [
        {"name": "清华大学", "institute": "计算机学院", "description": "", "deadline": "2026-09-01", "website": "https://a.edu.cn", "tags": []},
        {"name": "乙大学", "institute": "历史学院", "description": "古代史", "deadline": "2026-09-02", "website": "https://b.edu.cn", "tags": []},
    ]}
    result = summer_camps.collect(FakeFetcher(payload), NOW)
    assert result.ok
    assert [item.name for item in result.events] == ["清华大学 · 计算机学院"]
    assert result.events[0].university_tiers == ["985", "211", "双一流"]
    assert result.events[0].tags == ["985", "211", "双一流"]


def test_current_camp_bucket_uses_explicit_institute_label_for_pre_admission():
    payload = {"camp2026": [
        {
            "name": "甲大学", "institute": "计算机学院（推免预报名）",
            "description": "2027年接收推荐免试研究生预报名。",
            "deadline": "2026-09-01", "website": "https://a.edu.cn", "tags": [],
        },
        {
            "name": "乙大学", "institute": "人工智能学院",
            "description": "夏令营报名后使用推免生预报名系统提交材料。",
            "deadline": "2026-09-02", "website": "https://b.edu.cn", "tags": [],
        },
    ]}
    result = summer_camps.collect(FakeFetcher(payload), NOW)
    assert result.ok
    assert [item.event_type for item in result.events] == ["pre_admission", "summer_camp"]
    assert [item.categories for item in result.events] == [["预推免"], ["保研夏令营"]]


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


def test_ccfddl_collects_conference_deadlines_and_skips_bad_edition():
    payload = [{
        "title": "ICLR",
        "description": "International Conference on Learning Representations",
        "sub": "AI",
        "rank": {"ccf": "A", "core": "A*", "thcpl": "A"},
        "dblp": "iclr",
        "confs": [
            {
                "year": 2027,
                "id": "iclr27",
                "link": "https://iclr.cc/Conferences/2027",
                "timeline": [{
                    "abstract_deadline": "2026-08-30 23:59:59",
                    "deadline": "2026-09-01 23:59:59",
                }],
                "timezone": "AoE",
                "date": "April 2027",
                "place": "Vienna, Austria",
            },
            {
                "year": 2028,
                "id": "iclr28",
                "link": "https://iclr.cc/Conferences/2028",
                "timeline": [{"deadline": "2027-09-01 23:59:59"}],
                "timezone": "Mars/Colony",
                "date": "TBD",
                "place": "TBD",
            },
        ],
    }]
    result = ccfddl.collect(FakeFetcher(html=yaml.safe_dump(payload)), NOW)
    assert result.ok
    assert len(result.events) == 1
    event = result.events[0]
    assert event.name == "ICLR 2027"
    assert event.event_type == "conference"
    assert event.abstract_deadline == "2026-08-31T19:59:59+08:00"
    assert event.submission_deadline == "2026-09-02T19:59:59+08:00"
    assert event.categories == ["人工智能"]
    assert event.level == "CCF A / CORE A* / TH-CPL A"
    assert "CCF A" in event.tags
    assert event.source.authority == 4
    assert [stage["name"] for stage in event.schedule] == ["摘要截止", "论文截止"]
    assert result.details["invalid_entries"] == 1


def test_ccfddl_pt_deadline_uses_daylight_saving_time():
    parsed = ccfddl._parse_deadline("2026-10-02 17:00:00", "PT")
    assert parsed.isoformat() == "2026-10-03T08:00:00+08:00"


def test_ccfddl_keeps_abstract_and_paper_deadline_in_the_same_round():
    series = {
        "title": "VLDB", "description": "Very Large Data Bases", "sub": "DB",
        "rank": {"ccf": "A"},
    }
    edition = {
        "year": 2027,
        "id": "vldb27",
        "link": "https://www.vldb.org/2027/",
        "timeline": [
            {"abstract_deadline": "2026-08-20 17:00:00", "deadline": "2026-08-23 17:00:00"},
            {"abstract_deadline": "2026-09-20 17:00:00", "deadline": "2026-09-23 17:00:00"},
        ],
        "timezone": "PT",
        "date": "August 2027",
        "place": "Athens, Greece",
    }
    event = ccfddl._event_from_entry(series, edition, NOW)
    assert event.abstract_deadline == "2026-08-21T08:00:00+08:00"
    assert event.submission_deadline == "2026-08-24T08:00:00+08:00"


def test_ccfddl_keeps_tracks_that_share_a_deadline():
    series = {
        "title": "ADMA", "description": "Advanced Data Mining", "sub": "DB",
        "rank": {"ccf": "C"},
    }
    edition = {
        "year": 2026,
        "id": "adma26",
        "link": "https://adma2026.github.io/",
        "timeline": [
            {"deadline": "2026-09-12 23:59:59", "comment": "Poster Paper"},
            {"deadline": "2026-09-12 23:59:59", "comment": "Encore Paper"},
        ],
        "timezone": "AoE",
        "date": "October 2026",
        "place": "Hong Kong, China",
    }
    event = ccfddl._event_from_entry(series, edition, NOW)
    assert [stage["name"] for stage in event.schedule] == [
        "Poster Paper · 论文截止", "Encore Paper · 论文截止",
    ]
    assert [stage["id"] for stage in event.schedule] == [
        "round-1-deadline", "round-2-deadline",
    ]


def test_ccfddl_disambiguates_colliding_acronyms_and_upstream_ids():
    shared_edition = {
        "year": 2027,
        "id": "fse27",
        "timeline": [{"deadline": "2026-09-12 23:59:59"}],
        "timezone": "AoE",
        "date": "2027",
        "place": "TBD",
    }
    payload = [
        {
            "title": "FSE", "description": "Fast Software Encryption", "sub": "SC",
            "rank": {"ccf": "B"}, "dblp": "fse",
            "confs": [{**shared_edition, "link": "https://fse.iacr.org/2027/"}],
        },
        {
            "title": "FSE", "description": "Foundations of Software Engineering", "sub": "SE",
            "rank": {"ccf": "A"}, "dblp": "sigsoft",
            "confs": [{**shared_edition, "link": "https://conf.researchr.org/home/fse-2027"}],
        },
    ]
    result = ccfddl.collect(FakeFetcher(html=yaml.safe_dump(payload)), NOW)
    assert result.ok
    assert [event.name for event in result.events] == [
        "FSE 2027 · Fast Software Encryption",
        "FSE 2027 · Foundations of Software Engineering",
    ]
    assert len({event.id for event in result.events}) == 2
    original_id = result.events[0].id
    payload[0]["description"] = "Fast Software Encryption Conference"
    changed = ccfddl.collect(FakeFetcher(html=yaml.safe_dump(payload)), NOW)
    assert changed.events[0].id == original_id


def test_official_site_extracts_only_labeled_timeline():
    html = """
    <main>
      <p>报名时间：2026年8月1日至2026年9月5日 17:00</p>
      <p>全国决赛时间：2026年9月20日 08:30至2026年9月22日 18:00</p>
      <p>发布日期：2026年8月18日</p>
    </main>
    """
    timeline = official_sites._extract_timeline(html, NOW)
    assert timeline["registration_start"].startswith("2026-08-01T00:00:00")
    assert timeline["registration_deadline"].startswith("2026-09-05T17:00:00")
    assert timeline["competition_start"].startswith("2026-09-20T08:30:00")
    assert timeline["competition_end"].startswith("2026-09-22T18:00:00")
    assert "2026-08-18" not in " ".join(timeline.values())


def test_official_site_extracts_notice_text_without_scripts():
    html = "<nav>菜单</nav><article><h1>大赛通知</h1><p>这是赛事的具体介绍和参赛说明，内容足够长以供页面展示，报名同学请认真阅读官网原文和比赛章程。</p></article><script>bad()</script>"
    description = official_sites._extract_description(html)
    assert "大赛通知" in description
    assert "菜单" not in description
    assert "bad()" not in description


def test_official_site_ignores_news_dates_and_generic_edit_window():
    html = """
    <div>2026-07-31</div><a>全国赛决赛报到须知</a>
    <p>发布者： 时间：2026-06-24 浏览：</p>
    <p>更新时间不能超过前述截止时间（即2026年6月30日08:00）</p>
    """
    assert official_sites._extract_timeline(html, NOW) == {}


def test_official_site_accepts_short_split_table_label():
    html = "<table><tr><td>报名截止：</td><td>2026年9月5日 17:00</td></tr></table>"
    timeline = official_sites._extract_timeline(html, NOW)
    assert timeline["registration_deadline"].startswith("2026-09-05T17:00:00")


def test_official_site_does_not_treat_submission_opening_as_deadline():
    html = """
    <p>作品提交通道开通时间：2026年8月23日 15:00</p>
    <p>报名系统将延迟至2026年9月5日（周六）17:00关闭</p>
    """
    timeline = official_sites._extract_timeline(html, NOW)
    assert timeline["registration_deadline"].startswith("2026-09-05T17:00:00")
    assert "submission_deadline" not in timeline


def test_official_catalog_rejects_ctf_and_ambiguous_challenge_cup():
    ctf = {"title": "信息安全竞赛", "name": "全国大学生信息安全竞赛", "category": "信息安全", "tags": ["CTF"]}
    challenge = {"title": "挑战杯(科技)", "name": "挑战杯", "category": "创新创业", "tags": []}
    robot = {"title": "机器人竞赛", "name": "大学生机器人竞赛", "category": "机器人", "tags": []}
    assert not official_sites._catalog_selected(ctf)
    assert not official_sites._catalog_selected(challenge)
    assert official_sites._catalog_selected(robot)


def test_official_link_discovery_prefers_current_labeled_notice():
    html = '<a href="/news/2026-register">2026年大赛报名通知</a><a href="/about">大赛简介</a>'
    row = {"title": "机器人大赛", "name": "全国大学生机器人大赛"}
    links = official_sites._candidate_links(html, "https://contest.example/", row, NOW)
    assert links == [(12, "https://contest.example/news/2026-register")]


def test_official_link_discovery_preserves_www_hostname():
    html = '<a href="https://www.contest.example/deadline">报名截止时间通知</a>'
    row = {"title": "机器人大赛", "name": "全国大学生机器人大赛"}
    links = official_sites._candidate_links(html, "http://www.contest.example/", row, NOW)
    assert links[0][1] == "https://www.contest.example/deadline"


def test_official_host_resolution_accepts_codex_ipv4_and_ipv6_proxy(monkeypatch):
    addresses = [
        (None, None, None, None, ("198.18.1.79", 443)),
        (None, None, None, None, ("fdfe:dcba:9876::14f", 443, 0, 0)),
    ]
    monkeypatch.setattr(official_sites.socket, "getaddrinfo", lambda *args, **kwargs: addresses)
    official_sites._host_resolves_public.cache_clear()
    assert official_sites._host_resolves_public("conference.example", 443)
    assert not official_sites._safe_public_url("http://198.18.1.79/")
    assert not official_sites._safe_public_url("http://[fdfe:dcba:9876::14f]/")
    official_sites._host_resolves_public.cache_clear()
