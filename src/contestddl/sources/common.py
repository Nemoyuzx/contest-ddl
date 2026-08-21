from __future__ import annotations

import time
from collections.abc import Callable

from contestddl.models import SourceResult
from contestddl.utils import iso


def guarded(name: str, url: str, collector: Callable[[], list]) -> SourceResult:
    started = time.monotonic()
    try:
        events = collector()
        return SourceResult(name=name, ok=True, events=events, fetched_at=iso(), url=url, duration_ms=int((time.monotonic() - started) * 1000))
    except Exception as exc:  # one source must not take down the full pipeline
        return SourceResult(name=name, ok=False, error=f"{type(exc).__name__}: {exc}", fetched_at=iso(), url=url, duration_ms=int((time.monotonic() - started) * 1000))
