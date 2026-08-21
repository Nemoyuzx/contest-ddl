from __future__ import annotations

import re

from contestddl.models import Event, SourceEvidence
from contestddl.sources.common import guarded
from contestddl.utils import iso, iso_or_none, now_china, stable_id

CN_URL = "https://raw.githubusercontent.com/ProbiusOfficial/Hello-CTFtime/main/CN.json"


def collect(fetcher, now=None):
    current = now or now_china()

    def run():
        payload = fetcher.json(CN_URL)
        rows = payload.get("data", {}).get("result", [])
        events = []
        for row in rows:
            start = iso_or_none(row.get("comp_time_start"))
            end = iso_or_none(row.get("comp_time_end"))
            source = SourceEvidence("Hello-CTFtime CN", CN_URL, "trusted_community", 4, iso(current), ["name", "competition_start", "competition_end"])
            detail = row.get("detail", "")
            event = Event(
                id=stable_id(row.get("name", "CTF"), "competition", start, "hello-ctftime-cn"),
                name=row.get("name", "CTF"), event_type="competition", categories=["网络安全", "CTF"],
                official_url=row.get("link") or CN_URL, source=source, level="national", region="china",
                mode="online" if "线上" in detail else ("offline" if "线下" in detail else ""),
                eligibility="students/open", competition_start=start, competition_end=end,
                tags=["ctf", "cn"], notes=re.sub(r"\s+", " ", detail).strip(),
            )
            events.append(event)
        return events

    return guarded("hello_ctftime_cn", CN_URL, run)
