from datetime import datetime

from contestddl.models import Event, SourceEvidence
from contestddl.utils import CHINA_TZ, canonical_url, choose_primary_deadline, clean_event_title, compute_status, is_saikr_noncompetition_stage, normalize_title, parse_datetime, stable_id


def event(**kwargs):
    source = SourceEvidence("test", "https://example.com", "test", 5, "2026-08-22T12:00:00+08:00")
    defaults = dict(id="x", name="Test", event_type="competition", categories=[], official_url="https://example.com", source=source)
    defaults.update(kwargs)
    return Event(**defaults)


def test_canonical_url_drops_tracking_and_mobile_alias():
    assert canonical_url("https://m.saikr.com/vse/abc/?utm_source=x#top") == "https://saikr.com/vse/abc"


def test_normalize_title_drops_punctuation_and_saikr_suffix():
    assert normalize_title("2026 AI 大赛-大学生竞赛-赛氪竞赛网") == "2026ai大赛"


def test_clean_event_title_removes_marketing_badge_only():
    assert clean_event_title("【今日考试+开学领取证书】2026大学生创新数学竞赛") == "2026大学生创新数学竞赛"
    assert clean_event_title("【MathorCup】高校数学建模挑战赛") == "【MathorCup】高校数学建模挑战赛"


def test_stable_id_is_deterministic():
    assert stable_id("同一赛事", "competition", "2026-09-01") == stable_id("同一赛事", "competition", "2026-09-01")


def test_naive_chinese_datetime_gets_china_timezone():
    parsed = parse_datetime("2026年09月01日 12:30")
    assert parsed.utcoffset().total_seconds() == 8 * 3600


def test_status_registration_open():
    now = datetime(2026, 8, 22, 12, tzinfo=CHINA_TZ)
    item = event(registration_deadline="2026-08-23T23:59:59+08:00", competition_start="2026-09-01T08:00:00+08:00")
    assert compute_status(item, now) == "registration_open"


def test_status_ongoing_has_priority():
    now = datetime(2026, 8, 22, 12, tzinfo=CHINA_TZ)
    item = event(competition_start="2026-08-22T08:00:00+08:00", competition_end="2026-08-23T08:00:00+08:00")
    assert compute_status(item, now) == "ongoing"


def test_primary_deadline_keeps_future_competition_visible_after_registration_closes():
    now = datetime(2026, 8, 22, 12, tzinfo=CHINA_TZ)
    item = event(
        registration_deadline="2026-08-20T23:59:59+08:00",
        competition_start="2026-09-01T08:00:00+08:00",
        competition_end="2026-09-02T18:00:00+08:00",
    )
    assert choose_primary_deadline(item, now) == item.competition_start


def test_primary_deadline_prefers_conference_abstract_before_paper():
    now = datetime(2026, 8, 22, 12, tzinfo=CHINA_TZ)
    item = event(
        event_type="conference",
        abstract_deadline="2026-08-31T19:59:59+08:00",
        submission_deadline="2026-09-02T19:59:59+08:00",
    )
    assert choose_primary_deadline(item, now) == item.abstract_deadline
    assert compute_status(item, now) == "submission_open"


def test_future_submission_stage_is_upcoming_not_open():
    now = datetime(2026, 8, 22, 12, tzinfo=CHINA_TZ)
    item = event(schedule=[{
        "name": "作品提交",
        "start": "2026-09-10T00:00:00+08:00",
        "end": "2026-09-20T23:59:59+08:00",
    }])
    assert compute_status(item, now) == "submission_upcoming"


def test_schedule_status_and_primary_deadline_handle_multiple_rounds():
    now = datetime(2026, 8, 22, 20, tzinfo=CHINA_TZ)
    item = event(
        registration_deadline="2026-08-21T23:59:59+08:00",
        competition_start="2026-08-22T09:00:00+08:00",
        competition_end="2026-10-24T18:00:00+08:00",
        schedule=[
            {"name": "第一场", "start": "2026-08-22T09:00:00+08:00", "end": "2026-08-22T18:00:00+08:00"},
            {"name": "第二场报名", "start": "2026-08-23T00:00:00+08:00", "end": "2026-10-23T23:59:59+08:00"},
            {"name": "第二场", "start": "2026-10-24T09:00:00+08:00", "end": "2026-10-24T18:00:00+08:00"},
        ],
    )
    assert compute_status(item, now) == "registration_upcoming"
    assert choose_primary_deadline(item, now) == "2026-08-23T00:00:00+08:00"


def test_open_registration_precedes_future_schedule_status():
    now = datetime(2026, 8, 22, 12, tzinfo=CHINA_TZ)
    item = event(
        registration_deadline="2026-08-22T23:59:59+08:00",
        schedule=[{"name": "决赛", "start": "2026-09-01T09:00:00+08:00", "end": "2026-09-01T18:00:00+08:00"}],
    )
    assert compute_status(item, now) == "registration_open"


def test_saikr_post_event_stage_does_not_revive_finished_competition():
    now = datetime(2026, 10, 2, 12, tzinfo=CHINA_TZ)
    item = event(
        tags=["saikr"],
        registration_deadline="2026-07-31T23:59:59+08:00",
        competition_start="2026-08-01T00:00:00+08:00",
        competition_end="2026-09-30T23:59:59+08:00",
        schedule=[
            {"name": "全国总决赛", "start": "2026-09-01T00:00:00+08:00", "end": "2026-09-30T23:59:59+08:00"},
            {"name": "成果转化阶段（持续开展）", "start": "2026-10-01T00:00:00+08:00", "end": "2029-10-01T23:59:59+08:00"},
        ],
    )
    assert is_saikr_noncompetition_stage(item.schedule[1])
    assert choose_primary_deadline(item, now) == item.competition_end
    assert compute_status(item, now) == "ended"
    assert len(item.schedule) == 2


def test_saikr_award_ceremony_is_not_a_future_competition_round():
    now = datetime(2026, 10, 2, 12, tzinfo=CHINA_TZ)
    item = event(
        tags=["saikr"],
        competition_start="2026-08-01T00:00:00+08:00",
        competition_end="2026-09-15T23:59:59+08:00",
        schedule=[
            {"name": "比赛阶段", "start": "2026-08-01T00:00:00+08:00", "end": "2026-09-15T23:59:59+08:00"},
            {"name": "颁奖典礼", "start": "2026-10-13T00:00:00+08:00", "end": "2026-10-15T23:59:59+08:00"},
        ],
    )
    assert choose_primary_deadline(item, now) == item.competition_end
    assert compute_status(item, now) == "ended"


def test_saikr_stage_classifier_only_reads_stage_name_not_descriptive_content():
    assert not is_saikr_noncompetition_stage({"name": "竞赛评选阶段", "content": "确定获奖名单"})
    assert not is_saikr_noncompetition_stage({"name": "第一场（获奖名单已公布）"})
