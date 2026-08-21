from __future__ import annotations

from contestddl.models import Event, SourceEvidence
from contestddl.sources.common import guarded
from contestddl.utils import engineering_relevant, iso, iso_or_none, now_china, stable_id

URL = "https://raw.githubusercontent.com/CS-BAOYAN/BoardCaster/main/data.json"


def collect(fetcher, now=None):
    current = now or now_china()

    def run():
        payload = fetcher.json(URL)
        keys = [f"camp{current.year}", f"camp{current.year + 1}", f"yutuimian{current.year}"]
        events = []
        for key in keys:
            event_type = "pre_admission" if key.startswith("yutuimian") else "summer_camp"
            for row in payload.get(key, []):
                name = str(row.get("name", "")).strip()
                institute = str(row.get("institute", "")).strip()
                description = str(row.get("description", "")).strip()
                if not name or not engineering_relevant(institute, description):
                    continue
                deadline = iso_or_none(row.get("deadline"), end_of_day=True)
                if not deadline:
                    continue
                title = f"{name} · {institute}"
                source = SourceEvidence("CS-BAOYAN BoardCaster", URL, "trusted_community", 4, iso(current), ["name", "registration_deadline", "official_url"])
                event = Event(
                    id=stable_id(title, event_type, deadline, key), name=title, event_type=event_type,
                    categories=["保研夏令营" if event_type == "summer_camp" else "预推免"],
                    official_url=row.get("website") or URL, source=source, organizer=name,
                    level="university", region="china", eligibility="undergraduate students",
                    registration_deadline=deadline, tags=[str(tag) for tag in row.get("tags", [])],
                    notes="" if description in {"_No response_", "No response"} else description[:500],
                )
                events.append(event)
        return events

    return guarded("cs_baoyan", URL, run)
