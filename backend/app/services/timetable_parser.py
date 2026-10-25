"""Deterministic timetable parsing: transcribed grid cells → weekly slots.

Extraction (``timetable_extract``) only *transcribes* a sheet into ``{day, start, end, text}`` boxes plus the
header and legend, exactly as printed. Everything that interprets those strings lives here, as plain rules that
can be tested — no model guesses which subject, batch, teacher or room a cell means.

Cell grammar seen on DJSCE sheets (one box may hold several parallel sessions separated by "/"):

    ATCD (LD) 27                      subject (faculty) room
    ML_C31 (RK) L3                    subject_batch (faculty) lab-room            → lab
    GDS_C5 (PM) ICB Lab               named lab room
    IPD(AK)                           no room
    SM (NP 62, MA 63) / AA (SB 27)    per-faculty rooms inside the parentheses; parallel electives
    GDS(KG/NT)/FM(NP) 61,62,63        co-taught session; room list kept as printed

Anything that doesn't fit is kept verbatim with an ``unparsed`` issue for the reviewer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

_DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_SKIP = re.compile(r"^(break|lunch|recess|short break|lunch break|-+)$", re.I)
_PART = re.compile(
    r"^\s*(?P<subj>[A-Za-z][A-Za-z&]*(?:\s+Lab)?)\s*"
    r"(?:[_\-]\s*(?P<batch>[A-Za-z]?\d+))?\s*"
    r"\((?P<inner>[^()]*)\)\s*(?P<room>.*?)\s*$"
)
_FAC = re.compile(r"^(?P<abbr>[A-Z]{1,4})(?:\s+(?P<room>[A-Za-z]?\d+[A-Za-z]?|[A-Z]+\s*Lab))?$")


@dataclass
class Slot:
    subject: Optional[str] = None
    batch: Optional[str] = None
    faculty: list[str] = field(default_factory=list)
    room: Optional[str] = None
    kind: str = "lecture"
    raw: str = ""
    issues: list[str] = field(default_factory=list)
    weekday: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


def normalize_time(value: Optional[str]) -> Optional[str]:
    """"8:00" → "08:00"; afternoon hours printed 1–7 become 13–19 (the teaching day runs 8:00–18:00)."""
    m = re.match(r"^\s*(\d{1,2})[:.](\d{2})\s*$", value or "")
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if 1 <= h <= 7:
        h += 12
    if h > 23 or mi > 59:
        return None
    return f"{h:02d}:{mi:02d}"


def weekday_of(value: Optional[str]) -> Optional[int]:
    return _DAYS.get((value or "").strip().lower()[:3])


def _split_top(text: str, sep: str = "/") -> list[str]:
    """Split on ``sep`` outside parentheses."""
    parts, depth, cur = [], 0, []
    for ch in text:
        depth += ch == "("
        depth -= ch == ")"
        if ch == sep and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def _kind(subject: str, batch: Optional[str], room: Optional[str]) -> str:
    r = (room or "").lower()
    if batch or subject.lower().endswith(" lab") or re.match(r"^l\d", r) or "lab" in r:
        return "lab"
    return "lecture"


def parse_cell(text: str) -> list[Slot]:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text or _SKIP.match(text):
        return []
    out: list[Slot] = []
    for part in _split_top(text):
        m = _PART.match(part)
        items = [i.strip() for i in re.split(r"[,/]", m.group("inner"))] if m else []
        fac = [_FAC.match(i) for i in items if i]
        if not m or not fac or not all(fac):
            out.append(Slot(raw=part, issues=["unparsed"]))
            continue
        subject = m.group("subj").strip()
        batch = m.group("batch")
        room = m.group("room") or None
        if any(f.group("room") for f in fac):
            # Per-faculty rooms, e.g. "SM (NP 62, MA 63)": one slot each.
            for f in fac:
                r = f.group("room") or room
                out.append(Slot(subject=subject, batch=batch, faculty=[f.group("abbr")], room=r,
                                kind=_kind(subject, batch, r), raw=part))
        else:
            out.append(Slot(subject=subject, batch=batch, faculty=[f.group("abbr") for f in fac], room=room,
                            kind=_kind(subject, batch, room), raw=part))
    return out


def cells_to_slots(cells: list[dict[str, Any]]) -> list[Slot]:
    """Transcribed boxes → slots with weekday and normalized times; problems become issues, not drops."""
    slots: list[Slot] = []
    for c in cells:
        day = weekday_of(c.get("day"))
        start, end = normalize_time(c.get("start")), normalize_time(c.get("end"))
        for s in parse_cell(str(c.get("text") or "")):
            s.weekday, s.start_time, s.end_time = day, start, end
            if day is None:
                s.issues.append("missing_day")
            if not start or not end or (start and end and start >= end):
                s.issues.append("missing_time")
            if c.get("check"):
                s.issues.append("check_source")
            slots.append(s)
    return slots


def _clean(value: Any, *labels: str) -> Optional[str]:
    if not value:
        return None
    s = str(value).strip()
    for label in labels:
        s = re.sub(rf"^\s*{label}\s*[:\-]?\s*", "", s, flags=re.I)
    return s.strip(" .") or None


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    s = re.sub(r"(?i)^w\.?\s*e\.?\s*f\.?\s*[:\-]?\s*", "", value).strip(" .")
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", s)
    for fmt in ("%B %d, %Y", "%B %d %Y", "%d %B %Y", "%d %b %Y", "%b %d, %Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_header(raw: dict[str, Any]) -> dict[str, Any]:
    cls = _clean(raw.get("class"), "class") or ""
    year = None
    m = re.search(r"\b(F|S|T|L|B)\.?\s?(Y|E)\b", cls.upper())
    if m:
        year = f"{m.group(1)}{m.group(2)}"
    div = None
    dm = re.search(r"\b([A-Z]\d{1,2})\b", (_clean(raw.get("division"), "div", "division") or "").upper())
    if dm:
        div = dm.group(1)
    sem = _clean(raw.get("semester"), "sem", "semester")
    term = _clean(raw.get("term"), r"time\s*table\s*for\s*the\s*academic\s*term", "academic term", "term")
    return {
        "department_text": _clean(raw.get("department")),
        "class_text": cls or None,
        "year_label": year,
        "division": div,
        "semester": sem,
        "academic_term": term,
        "effective_from": _parse_date(raw.get("effective_from")),
        "class_key": f"{year}-{div}" if year and div else None,
    }
