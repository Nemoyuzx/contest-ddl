from datetime import datetime

from contestddl.models import Event, SourceEvidence
from contestddl.utils import CHINA_TZ, canonical_url, compute_status, normalize_title, parse_datetime, stable_id


def event(**kwargs):
    source = SourceEvidence("test", "https://example.com", "test", 5, "2026-08-22T12:00:00+08:00")
    defaults = dict(id="x", name="Test", event_type="competition", categories=[], official_url="https://example.com", source=source)
    defaults.update(kwargs)
    return Event(**defaults)


def test_canonical_url_drops_tracking_and_mobile_alias():
    assert canonical_url("https://m.saikr.com/vse/abc/?utm_source=x#top") == "https://saikr.com/vse/abc"


def test_normalize_title_drops_punctuation_and_saikr_suffix():
    assert normalize_title("2026 AI 大赛-大学生竞赛-赛氪竞赛网") == "2026ai大赛"


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
