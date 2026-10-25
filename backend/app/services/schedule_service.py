"""Teaching schedule: recurring timetable entries expanded into dated occurrences.

Nothing is materialized per date. A faculty member's schedule for a date range is computed
on read from the *published* TimetableEntry rows mapped to them (across every class timetable),
then adjusted by ScheduleExceptions:

- ``holiday``   no teaching that date (institution-wide, or one department): occurrences are
                returned with status ``holiday`` so the calendar can explain the gap.
- ``cancelled`` one occurrence of one entry is cancelled (status ``cancelled``); the weekly
                entry itself is untouched.
- ``modified``  one occurrence moves to a new time and/or room (status ``rescheduled``).
- ``extra``     a one-off replacement lecture for a faculty member (status ``extra``).

Dates are local calendar dates in ``settings.INSTITUTION_TIMEZONE``; times are "HH:MM".
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.core.config import settings
from app.models.structured import ScheduleException, TimetableEntry, TimetableImport, User

EXCEPTION_KINDS = {"cancelled", "modified", "holiday", "extra"}
MAX_RANGE_DAYS = 42
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ScheduleError(ValueError):
    pass


def local_today() -> date:
    return datetime.now(ZoneInfo(settings.INSTITUTION_TIMEZONE)).date()


def as_day(d: date) -> date:
    """Stored form of a local date (a DATE column)."""
    return d


def valid_hhmm(value: Optional[str]) -> bool:
    return bool(value and _HHMM.match(value))


def class_label(imp: TimetableImport) -> str:
    return " ".join(p for p in (imp.year_label, imp.division) if p) or imp.class_key


class ScheduleService:
    def published_entries(self, db: Session, user_id: UUID) -> list[tuple[TimetableEntry, TimetableImport]]:
        stmt = (
            select(TimetableEntry, TimetableImport)
            .where(TimetableEntry.import_id == TimetableImport.id)
            .where(TimetableImport.status == "published")
            .where(TimetableEntry.faculty_user_id == user_id)
        )
        return list(db.exec(stmt))

    def occurrences(self, db: Session, user: User, start: date, days: int) -> list[dict[str, Any]]:
        if days < 1 or days > MAX_RANGE_DAYS:
            raise ScheduleError(f"days must be between 1 and {MAX_RANGE_DAYS}")
        end = start + timedelta(days=days - 1)
        entries = self.published_entries(db, user.id)
        exceptions = list(db.exec(
            select(ScheduleException)
            .where(ScheduleException.on_date >= as_day(start))
            .where(ScheduleException.on_date <= as_day(end))
        ))
        holidays: dict[date, ScheduleException] = {}
        by_entry: dict[tuple[UUID, date], ScheduleException] = {}
        extras: list[ScheduleException] = []
        for ex in exceptions:
            d = ex.on_date
            if ex.kind == "holiday" and ex.department in ("all", user.department):
                holidays[d] = ex
            elif ex.kind in ("cancelled", "modified") and ex.entry_id:
                by_entry[(ex.entry_id, d)] = ex
            elif ex.kind == "extra" and ex.faculty_user_id == user.id:
                extras.append(ex)

        out: list[dict[str, Any]] = []
        for offset in range(days):
            d = start + timedelta(days=offset)
            for entry, imp in entries:
                if entry.weekday != d.weekday():
                    continue
                if imp.effective_from and d < imp.effective_from:
                    continue
                item = self._item(d, entry, imp)
                if d in holidays:
                    item.update(status="holiday", note=holidays[d].reason or "Holiday")
                elif (ex := by_entry.get((entry.id, d))) is not None:
                    if ex.kind == "cancelled":
                        item.update(status="cancelled", note=ex.reason)
                    else:
                        item.update(
                            status="rescheduled", note=ex.reason,
                            start_time=ex.start_time or item["start_time"],
                            end_time=ex.end_time or item["end_time"],
                            room=ex.room or item["room"],
                            original={"start_time": entry.start_time, "end_time": entry.end_time, "room": entry.room},
                        )
                    item["exception_id"] = str(ex.id)
                out.append(item)
        for ex in extras:
            out.append({
                "date": ex.on_date.isoformat(), "start_time": ex.start_time, "end_time": ex.end_time,
                "subject": ex.subject, "room": ex.room, "class_label": ex.class_label, "kind": "lecture",
                "batch": None, "status": "extra", "note": ex.reason, "entry_id": None,
                "exception_id": str(ex.id), "source": None,
            })
        out.sort(key=lambda i: (i["date"], i["start_time"] or ""))
        return out

    def _item(self, d: date, entry: TimetableEntry, imp: TimetableImport) -> dict[str, Any]:
        return {
            "date": d.isoformat(),
            "start_time": entry.start_time,
            "end_time": entry.end_time,
            "subject": entry.subject,
            "room": entry.room,
            "class_label": class_label(imp),
            "kind": entry.kind,
            "batch": entry.batch,
            "status": "scheduled",
            "note": None,
            "entry_id": str(entry.id),
            "exception_id": None,
            # Every published occurrence keeps its link to the uploaded timetable it came from.
            "source": {"import_id": str(imp.id), "filename": imp.source_filename, "version": imp.version},
        }

    def weekly_load(self, db: Session, user_id: UUID) -> dict[str, Any]:
        """Teaching load from the published timetable: slots and hours per week (no dates)."""
        minutes = 0
        entries = self.published_entries(db, user_id)
        for e, _ in entries:
            if valid_hhmm(e.start_time) and valid_hhmm(e.end_time):
                sh, sm = map(int, e.start_time.split(":"))
                eh, em = map(int, e.end_time.split(":"))
                minutes += max(0, (eh * 60 + em) - (sh * 60 + sm))
        return {"slots_per_week": len(entries), "hours_per_week": round(minutes / 60, 1)}

    def add_exception(self, db: Session, actor: User, *, on_date: date, kind: str,
                      entry_id: Optional[UUID] = None, faculty_user_id: Optional[UUID] = None,
                      department: str = "all", start_time: Optional[str] = None,
                      end_time: Optional[str] = None, room: Optional[str] = None,
                      subject: Optional[str] = None, class_label_text: Optional[str] = None,
                      reason: Optional[str] = None) -> ScheduleException:
        if kind not in EXCEPTION_KINDS:
            raise ScheduleError(f"kind must be one of {sorted(EXCEPTION_KINDS)}")
        for t in (start_time, end_time):
            if t is not None and not valid_hhmm(t):
                raise ScheduleError("times must be HH:MM (24-hour)")
        if start_time and end_time and start_time >= end_time:
            raise ScheduleError("end time must be after start time")
        if kind in ("cancelled", "modified"):
            entry = db.get(TimetableEntry, entry_id) if entry_id else None
            imp = db.get(TimetableImport, entry.import_id) if entry else None
            if not entry or not imp or imp.status != "published":
                raise ScheduleError("a published timetable entry is required")
            if on_date.weekday() != entry.weekday:
                raise ScheduleError("that lecture does not take place on this date")
            if kind == "modified" and not (start_time or end_time or room):
                raise ScheduleError("a modification needs a new time or room")
            dup = db.exec(select(ScheduleException).where(
                ScheduleException.entry_id == entry.id, ScheduleException.on_date == as_day(on_date))).first()
            if dup:
                raise ScheduleError("this lecture already has a change on that date; remove it first")
        if kind == "extra":
            if not faculty_user_id or not db.get(User, faculty_user_id):
                raise ScheduleError("a faculty member is required for an extra lecture")
            if not (start_time and end_time and subject):
                raise ScheduleError("an extra lecture needs a subject, start and end time")
        ex = ScheduleException(
            on_date=as_day(on_date), kind=kind, entry_id=entry_id if kind in ("cancelled", "modified") else None,
            faculty_user_id=faculty_user_id if kind == "extra" else None, department=department or "all",
            start_time=start_time, end_time=end_time, room=room, subject=subject,
            class_label=class_label_text, reason=reason, created_by_user_id=actor.id,
        )
        db.add(ex)
        db.commit()
        db.refresh(ex)
        return ex


schedule_service = ScheduleService()
