from __future__ import annotations

from datetime import datetime, timedelta

from contestddl.models import Event, SourceEvidence
from contestddl.sources.common import guarded
from contestddl.utils import iso, now_china, stable_id

URL = "https://codeforces.com/api/contest.list?gym=false"


def collect(fetcher, now=None):
    current = now or now_china()

    def run():
        payload = fetcher.json(URL)
        if payload.get("status") != "OK":
            raise ValueError(payload.get("comment", "Codeforces API returned non-OK"))
        events = []
        for row in payload.get("result", []):
            if row.get("phase") not in {"BEFORE", "CODING"} or not row.get("startTimeSeconds"):
                continue
            start = datetime.fromtimestamp(row["startTimeSeconds"], tz=current.tzinfo)
            if start > current + timedelta(days=180) or start < current - timedelta(days=2):
                continue
            end = start + timedelta(seconds=row.get("durationSeconds", 0))
            detail = f"https://codeforces.com/contest/{row['id']}"
            source = SourceEvidence("Codeforces API", URL, "official_api", 5, iso(current), ["name", "competition_start", "competition_end"])
            event = Event(
                id=stable_id(row["name"], "competition", iso(start), f"cf-{row['id']}"),
                name=row["name"], event_type="competition", categories=["程序设计"],
                official_url=detail, source=source, organizer="Codeforces", level="international",
                region="global", mode="online", eligibility="open",
                competition_start=iso(start), competition_end=iso(end),
                tags=["algorithm", "programming", f"codeforces:{row['id']}"], notes="公开算法竞赛；并非仅限大学生。",
            )
            events.append(event)
        return events[:40]

    return guarded("codeforces", URL, run)
