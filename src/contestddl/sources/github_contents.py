"""Narrow GitHub Contents fallback for two public JSON source files.

The raw URLs remain the canonical source/evidence URLs.  Only their transport
falls back to GitHub's Contents API when raw.githubusercontent.com cannot be
read as JSON.
"""

from __future__ import annotations

import base64
import binascii
import json

import requests

OFFICIAL_CATALOG_URL = "https://raw.githubusercontent.com/xcg1125/college-competition-ddl/main/competitions.json"
BOARDCASTER_URL = "https://raw.githubusercontent.com/CS-BAOYAN/BoardCaster/main/data.json"

_CONTENTS_ENDPOINTS = {
    OFFICIAL_CATALOG_URL: (
        "https://api.github.com/repos/xcg1125/college-competition-ddl/contents/competitions.json?ref=main",
        "competitions.json",
    ),
    BOARDCASTER_URL: (
        "https://api.github.com/repos/CS-BAOYAN/BoardCaster/contents/data.json?ref=main",
        "data.json",
    ),
}
_MAX_JSON_BYTES = 2 * 1024 * 1024
_MAX_BASE64_CHARS = ((_MAX_JSON_BYTES + 2) // 3) * 4
_MAX_BASE64_CHARS += _MAX_BASE64_CHARS // 60 + 2  # GitHub wraps base64 lines.


def load_public_json(fetcher, raw_url: str):
    """Read one allowlisted raw JSON file, falling back to its Contents API."""
    if raw_url not in _CONTENTS_ENDPOINTS:
        raise ValueError("no GitHub Contents fallback configured for this URL")
    try:
        return fetcher.json(raw_url)
    except (requests.RequestException, ValueError, OSError):
        pass

    api_url, expected_path = _CONTENTS_ENDPOINTS[raw_url]
    response = fetcher.get(api_url, headers={"Accept": "application/vnd.github+json"})
    if response.status_code != 200:
        raise ValueError(f"GitHub Contents API returned HTTP {response.status_code} for {expected_path}")
    if "json" not in response.headers.get("Content-Type", "").lower():
        raise ValueError(f"GitHub Contents API did not return JSON for {expected_path}")
    envelope = response.json()
    if not isinstance(envelope, dict) or envelope.get("type") != "file" or envelope.get("path") != expected_path:
        raise ValueError(f"unexpected GitHub Contents metadata for {expected_path}")
    if envelope.get("encoding") != "base64":
        raise ValueError(f"GitHub Contents API did not provide base64 content for {expected_path}")
    size = envelope.get("size")
    content = envelope.get("content")
    if type(size) is not int or not 0 < size <= _MAX_JSON_BYTES:
        raise ValueError(f"GitHub Contents file size is invalid for {expected_path}")
    if not isinstance(content, str) or len(content) > _MAX_BASE64_CHARS:
        raise ValueError(f"GitHub Contents content is missing or oversized for {expected_path}")
    try:
        decoded = base64.b64decode(content.replace("\n", ""), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"GitHub Contents base64 is invalid for {expected_path}") from exc
    if len(decoded) != size:
        raise ValueError(f"GitHub Contents decoded size does not match metadata for {expected_path}")
    try:
        return json.loads(decoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"GitHub Contents content is not UTF-8 JSON for {expected_path}") from exc
