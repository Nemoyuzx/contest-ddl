from __future__ import annotations

import json

from bs4 import BeautifulSoup

from contestddl.models import Event, SourceEvidence
from contestddl.sources.common import guarded
from contestddl.utils import canonical_url, iso, iso_or_none, now_china, stable_id


def collect(fetcher, now=None):
    current = now or now_china()
    urls = [f"https://mlh.io/seasons/{current.year}/events", f"https://mlh.io/seasons/{current.year + 1}/events"]

    def run():
        events = []
        seen = set()
        for url in urls:
            html = fetcher.text(url)
            soup = BeautifulSoup(html, "html.parser")
            node = soup.select_one('script[data-page="app"][type="application/json"]')
            if not node:
                raise ValueError("MLH embedded event data not found")
            props = json.loads(node.get_text()).get("props", {})
            for row in props.get("upcomingEvents", []):
                external_url = row.get("websiteUrl") or f"https://mlh.io/events/{row.get('slug', '')}"
                identity = row.get("id") or canonical_url(external_url)
                if identity in seen:
                    continue
                seen.add(identity)
                mode = {"digital": "online", "physical": "offline", "hybrid": "hybrid"}.get(row.get("formatType"), row.get("formatType", ""))
                source = SourceEvidence("Major League Hacking", url, "official_platform", 5, iso(current), ["name", "competition_start", "competition_end", "location", "mode"])
                focus = row.get("customFields", {}).get("hackathon_focus", [])
                event = Event(
                    id=stable_id(row.get("name", "Hackathon"), "hackathon", row.get("startsAt"), f"mlh-{identity}"),
                    name=row.get("name", "Hackathon"), event_type="hackathon",
                    categories=["黑客松", *[str(item) for item in focus][:3]], official_url=external_url,
                    source=source, organizer="Major League Hacking", level="international", region=row.get("region") or "global",
                    location=row.get("location") or "", mode=mode, eligibility="students/open",
                    registration_deadline=None, competition_start=iso_or_none(row.get("startsAt")), competition_end=iso_or_none(row.get("endsAt")),
                    tags=["hackathon", "mlh"], notes="MLH 官方高校黑客松日历；报名截止时间未提供时，请以活动官网为准。",
                )
                events.append(event)
        return events

    return guarded("mlh", urls[0], run)
