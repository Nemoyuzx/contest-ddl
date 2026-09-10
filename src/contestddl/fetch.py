from __future__ import annotations

import time
import re
from html import unescape
from collections import defaultdict
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class Fetcher:
    def __init__(self, timeout: int = 25, delay: float = 0.15):
        self.timeout = timeout
        self.delay = delay
        self.last_request: dict[str, float] = defaultdict(float)
        self.session = requests.Session()
        retry = Retry(total=2, backoff_factor=0.6, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",))
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers.update({
            "User-Agent": "contest-ddl/0.1 (+https://github.com/Nemoyuzx/contest-ddl; public-data research)",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        })

    def _wait(self, url: str) -> None:
        host = requests.utils.urlparse(url).netloc
        elapsed = time.monotonic() - self.last_request[host]
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request[host] = time.monotonic()

    def get(self, url: str, **kwargs) -> requests.Response:
        self._wait(url)
        response = self.session.get(url, timeout=kwargs.pop("timeout", self.timeout), **kwargs)
        response.raise_for_status()
        if int(response.headers.get("Content-Length") or 0) > 8 * 1024 * 1024:
            raise ValueError(f"response too large: {url}")
        return response

    def json(self, url: str, **kwargs) -> Any:
        response = self.get(url, **kwargs)
        try:
            return response.json()
        except requests.exceptions.JSONDecodeError as exc:
            # Retain enough transport context to distinguish an HTML challenge,
            # an empty response and unsupported compression. Never log bodies,
            # cookies, authorization headers or query strings.
            content_type = " ".join(response.headers.get("Content-Type", "unknown").split())[:100]
            encoding = " ".join(response.headers.get("Content-Encoding", "identity").split())[:40]
            title_match = re.search(r"<title\b[^>]*>(.*?)</title>", response.text[:4096], re.I | re.S)
            title = " ".join(unescape(re.sub(r"<[^>]*>", "", title_match.group(1))).split())[:100] if title_match else ""
            raise ValueError(
                f"expected JSON: HTTP {response.status_code}, content-type={content_type}, "
                f"content-encoding={encoding}, bytes={len(response.content)}, title={title!r}"
            ) from exc

    def text(self, url: str, **kwargs) -> str:
        response = self.get(url, **kwargs)
        if not response.encoding or response.encoding.lower() in {"iso-8859-1", "latin-1"}:
            response.encoding = response.apparent_encoding
        return response.text
