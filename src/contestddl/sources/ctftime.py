from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlencode

from contestddl.models import Event, SourceEvidence
from contestddl.sources.common import guarded
from contestddl.utils import iso, iso_or_none, now_china, stable_id

BASE_URL = "https://ctftime.org/api/v1/events/"


def collect(fetcher, now=None):
    current = now or now_china()
    params = urlencode({"limit": 100, "start": int(current.timestamp()), "finish": int((current + timedelta(days=180)).timestamp())})
    url = f"{BASE_URL}?{params}"

    def run():
        rows = fetcher.json(url)
        events = []
        for row in rows:
            source = SourceEvidence("CTFtime API", row.get("ctftime_url") or url, "official_api", 5, iso(current), ["name", "competition_start", "competition_end", "mode"])
            organizers = row.get("organizers") or []
            organizer = ", ".join(item.get("name", "") for item in organizers if item.get("name"))
            event = Event(
                id=stable_id(row.get("title", "CTF"), "competition", row.get("start"), f"ctftime-{row.get('id') or ''}"),
                name=row.get("title", "CTF"), event_type="competition", categories=["网络安全", "CTF"],
                official_url=row.get("url") or row.get("ctftime_url") or url, source=source,
                organizer=organizer, level="international", region="global",
                mode="online" if row.get("onsite") is False else ("offline" if row.get("onsite") else ""),
                eligibility="open", competition_start=iso_or_none(row.get("start")), competition_end=iso_or_none(row.get("finish")),
                tags=["ctf", row.get("format", "")], notes="CTFtime 收录赛事；请在官方页确认报名要求。",
            )
            events.append(event)
        return events

    return guarded("ctftime", BASE_URL, run)
