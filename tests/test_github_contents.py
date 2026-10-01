import base64
import json
from datetime import datetime

import pytest
import requests

from contestddl.sources import official_sites, summer_camps
from contestddl.sources.github_contents import (
    BOARDCASTER_URL,
    OFFICIAL_CATALOG_URL,
    load_public_json,
)
from contestddl.utils import CHINA_TZ


API_URLS = {
    OFFICIAL_CATALOG_URL: "https://api.github.com/repos/xcg1125/college-competition-ddl/contents/competitions.json?ref=main",
    BOARDCASTER_URL: "https://api.github.com/repos/CS-BAOYAN/BoardCaster/contents/data.json?ref=main",
}


def api_response(raw_url, payload, *, status=200, **overrides):
    body = json.dumps(payload).encode("utf-8")
    envelope = {
        "type": "file",
        "path": "competitions.json" if raw_url == OFFICIAL_CATALOG_URL else "data.json",
        "encoding": "base64",
        "size": len(body),
        "content": base64.b64encode(body).decode("ascii"),
    }
    envelope.update(overrides)
    result = requests.Response()
    result.status_code = status
    result.headers["Content-Type"] = "application/json; charset=utf-8"
    result._content = json.dumps(envelope).encode("utf-8")
    return result


class FakeFetcher:
    def __init__(self, *, raw_payload=None, raw_error=None, api_payload=None):
        self.raw_payload = raw_payload
        self.raw_error = raw_error
        self.api_payload = api_payload
        self.calls = []

    def json(self, url):
        self.calls.append(("raw", url))
        if self.raw_error:
            raise self.raw_error
        return self.raw_payload

    def get(self, url, **kwargs):
        self.calls.append(("api", url, kwargs))
        return self.api_payload


@pytest.mark.parametrize("raw_url", API_URLS)
def test_raw_success_does_not_call_contents_api(raw_url):
    payload = [] if raw_url == OFFICIAL_CATALOG_URL else {"camp2026": []}
    fetcher = FakeFetcher(raw_payload=payload)
    assert load_public_json(fetcher, raw_url) is payload
    assert fetcher.calls == [("raw", raw_url)]


@pytest.mark.parametrize("raw_url", API_URLS)
@pytest.mark.parametrize("raw_error", [ValueError("expected JSON"), requests.ConnectionError("raw unavailable")])
def test_raw_failure_uses_validated_contents_api(raw_url, raw_error):
    payload = [] if raw_url == OFFICIAL_CATALOG_URL else {"camp2026": []}
    fetcher = FakeFetcher(raw_error=raw_error, api_payload=api_response(raw_url, payload))
    assert load_public_json(fetcher, raw_url) == payload
    assert fetcher.calls == [
        ("raw", raw_url),
        ("api", API_URLS[raw_url], {"headers": {"Accept": "application/vnd.github+json"}}),
    ]


@pytest.mark.parametrize("overrides,expected", [
    ({"encoding": "none"}, "base64 content"),
    ({"content": "not-base64!"}, "base64 is invalid"),
    ({"size": 0}, "file size is invalid"),
    ({"size": 2 * 1024 * 1024 + 1}, "file size is invalid"),
    ({"size": 15}, "decoded size does not match"),
    ({"path": "other.json"}, "metadata"),
])
def test_rejects_malformed_or_oversized_contents_metadata(overrides, expected):
    fetcher = FakeFetcher(
        raw_error=requests.ConnectionError("raw unavailable"),
        api_payload=api_response(OFFICIAL_CATALOG_URL, [], **overrides),
    )
    with pytest.raises(ValueError, match=expected):
        load_public_json(fetcher, OFFICIAL_CATALOG_URL)


def test_rejects_contents_api_error_status():
    fetcher = FakeFetcher(
        raw_error=ValueError("expected JSON"),
        api_payload=api_response(BOARDCASTER_URL, {}, status=429),
    )
    with pytest.raises(ValueError, match="HTTP 429"):
        load_public_json(fetcher, BOARDCASTER_URL)


def test_rejects_unlisted_url_without_request():
    fetcher = FakeFetcher()
    with pytest.raises(ValueError, match="no GitHub Contents fallback"):
        load_public_json(fetcher, "https://example.com/data.json")
    assert fetcher.calls == []


def test_collectors_preserve_original_source_urls_after_fallback():
    now = datetime(2026, 8, 22, 12, tzinfo=CHINA_TZ)
    camp = {
        "camp2026": [{
            "name": "清华大学", "institute": "计算机学院", "description": "",
            "deadline": "2026-09-01", "website": "https://example.edu.cn/camp", "tags": [],
        }],
    }
    summer = summer_camps.collect(
        FakeFetcher(raw_error=ValueError("expected JSON"), api_payload=api_response(BOARDCASTER_URL, camp)), now
    )
    assert summer.ok
    assert summer.url == BOARDCASTER_URL
    assert summer.events[0].source.url == BOARDCASTER_URL

    official = official_sites.collect(
        FakeFetcher(raw_error=ValueError("expected JSON"), api_payload=api_response(OFFICIAL_CATALOG_URL, [])), now
    )
    assert official.ok
    assert official.url == OFFICIAL_CATALOG_URL
    assert official.details["catalog_records"] == 0
