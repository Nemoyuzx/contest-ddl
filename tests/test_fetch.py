import pytest
import requests

from contestddl.fetch import Fetcher


def response(body, content_type="application/json", encoding=None):
    result = requests.Response()
    result.status_code = 200
    result._content = body
    result.encoding = "utf-8"
    result.headers["Content-Type"] = content_type
    if encoding:
        result.headers["Content-Encoding"] = encoding
    return result


def test_json_fetch_keeps_valid_payload(monkeypatch):
    fetcher = Fetcher()
    monkeypatch.setattr(fetcher, "get", lambda *args, **kwargs: response(b'{"code":200}'))
    assert fetcher.json("https://example.com") == {"code": 200}


@pytest.mark.parametrize("body,content_type,encoding,expected", [
    (b"", "application/json", None, "bytes=0"),
    (b"<html><title>Access &amp; restriction</title><script>secret-cookie</script></html>", "text/html", None, "Access & restriction"),
    (b"invalid-compressed-data", "application/json", "br", "content-encoding=br"),
])
def test_json_fetch_preserves_safe_transport_diagnostics(monkeypatch, body, content_type, encoding, expected):
    fetcher = Fetcher()
    monkeypatch.setattr(fetcher, "get", lambda *args, **kwargs: response(body, content_type, encoding))
    with pytest.raises(ValueError, match="expected JSON") as error:
        fetcher.json("https://example.com?credential=secret-query")
    assert expected in str(error.value)
    assert "HTTP 200" in str(error.value)
    assert "secret-cookie" not in str(error.value)
    assert "secret-query" not in str(error.value)
