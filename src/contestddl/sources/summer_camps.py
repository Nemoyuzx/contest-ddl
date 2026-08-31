from __future__ import annotations

from contestddl.models import Event, SourceEvidence
from contestddl.sources.common import guarded
from contestddl.university_tiers import university_tiers
from contestddl.utils import engineering_relevant, iso, iso_or_none, now_china, stable_id

URL = "https://raw.githubusercontent.com/CS-BAOYAN/BoardCaster/main/data.json"
PRE_ADMISSION_LABELS = (
    "预推免",
    "推免预报名",
    "推免生预报名",
    "推免研究生预报名",
    "直博预报名",
)


def _event_type(key: str, institute: str) -> str:
    """Use BoardCaster's structured bucket or an explicit institute label.

    Some current-year pre-admission records are published under ``campYYYY``
    after the dedicated ``yutuimianYYYY`` bucket disappears.  Only the short
    institute/title field is used as a fallback; prose mentioning the
    pre-admission registration system inside a real summer-camp notice must not
    change that event's type.
    """
    if key.startswith("yutuimian") or any(label in institute for label in PRE_ADMISSION_LABELS):
        return "pre_admission"
    return "summer_camp"


def collect(fetcher, now=None):
    current = now or now_china()

    def run():
        payload = fetcher.json(URL)
        keys = [f"camp{current.year}", f"camp{current.year + 1}", f"yutuimian{current.year}"]
        events = []
        for key in keys:
            for row in payload.get(key, []):
                name = str(row.get("name", "")).strip()
                institute = str(row.get("institute", "")).strip()
                description = str(row.get("description", "")).strip()
                if not name or not engineering_relevant(institute, description):
                    continue
                event_type = _event_type(key, institute)
                deadline = iso_or_none(row.get("deadline"), end_of_day=True)
                if not deadline:
                    continue
                title = f"{name} · {institute}"
                tiers = university_tiers(name)
                tags = list(dict.fromkeys([*[str(tag) for tag in row.get("tags", [])], *tiers]))
                source = SourceEvidence("CS-BAOYAN BoardCaster", URL, "trusted_community", 4, iso(current), ["name", "registration_deadline", "official_url"])
                event = Event(
                    id=stable_id(title, event_type, deadline, key), name=title, event_type=event_type,
                    categories=["保研夏令营" if event_type == "summer_camp" else "预推免"],
                    official_url=row.get("website") or URL, source=source, organizer=name,
                    level="university", region="china", eligibility="undergraduate students",
                    registration_deadline=deadline, tags=tags, university_tiers=tiers,
                    notes="" if description in {"_No response_", "No response"} else description[:500],
                )
                events.append(event)
        return events

    return guarded("cs_baoyan", URL, run)
