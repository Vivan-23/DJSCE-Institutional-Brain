"""Timetable import workflow: upload → extract (draft) → review/correct → publish.

- One ``TimetableImport`` per uploaded class sheet. ``class_key`` (e.g. ``TY-C3``) is the import identity: a new
  upload for the same class becomes the next ``version`` and is compared with the currently published one.
  The same file uploaded twice (same SHA-256) returns the existing import instead of extracting again.
- Faculty initials resolve to accounts only through verified ``FacultyAlias`` rows created by a coordinator.
  Suggestions from the sheet's legend are offered, never applied automatically.
- Review flags live on each entry (``issues``). Blocking flags must be fixed (or the entry deleted) before
  publishing; warnings need an explicit acknowledgement.
- Publishing supersedes the previous version of the same class only: other classes' timetables, and therefore
  other parts of a faculty member's consolidated schedule, are untouched. Date exceptions on unchanged lectures
  are carried over to the new version's matching entries.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import UUID

import structlog
from sqlmodel import Session, select

from app.models.structured import (
    FacultyAlias, ScheduleException, TimetableEntry, TimetableImport, TimetableSource, User,
)
from app.services.audit_service import audit_service
from app.services.notice_service import notice_service
from app.services.schedule_service import valid_hhmm
from app.services.timetable_extract import ExtractionError, extract
from app.services.timetable_parser import cells_to_slots, parse_header

log = structlog.get_logger()

BLOCKING = {"missing_day", "missing_time", "unknown_faculty", "unparsed", "duplicate"}
WARNINGS = {"overlap", "clash", "missing_room", "missing_subject", "no_faculty", "check_source"}
ISSUE_TEXT = {
    "missing_day": "Day not recognised",
    "missing_time": "Start/end time missing or invalid",
    "unknown_faculty": "Initials not mapped to a faculty account",
    "unparsed": "Cell text could not be read as subject (faculty) room",
    "duplicate": "Same lecture appears twice",
    "overlap": "This faculty member has another lecture at the same time in this timetable",
    "clash": "This faculty member is already teaching another class at this time (published timetable)",
    "missing_room": "Room not given",
    "missing_subject": "Subject missing",
    "no_faculty": "No faculty initials in this cell",
    "check_source": "Read differently on a second pass — check against the source",
}
_STICKY = {"unparsed", "check_source"}  # from extraction; cleared once a reviewer edits the entry
_ABBR = re.compile(r"^[A-Z]{1,4}$")
_TITLES = re.compile(r"^(prof|dr|mr|mrs|ms|shri|smt)\.?\s+", re.I)


class TimetableError(ValueError):
    pass


def _issues(e: TimetableEntry) -> list[str]:
    try:
        return list(json.loads(e.issues or "[]"))
    except json.JSONDecodeError:
        return []


def _overlaps(a: TimetableEntry, b: TimetableEntry) -> bool:
    return (a.weekday == b.weekday and valid_hhmm(a.start_time) and valid_hhmm(b.start_time)
            and valid_hhmm(a.end_time) and valid_hhmm(b.end_time)
            and a.start_time < b.end_time and b.start_time < a.end_time)


def entry_key(e: TimetableEntry) -> tuple:
    return (e.weekday, e.start_time, e.end_time, (e.subject or "").upper(), (e.batch or "").upper(),
            (e.faculty_abbrev or "").upper(), (e.room or "").upper())


def _slot_key(e: TimetableEntry) -> tuple:
    """Identity of a lecture across versions (room/end time may change)."""
    return (e.weekday, e.start_time, (e.subject or "").upper(), (e.batch or "").upper(), (e.faculty_abbrev or "").upper())


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z ]", "", _TITLES.sub("", (name or "").strip()).lower()).strip()


def _initials(name: str) -> str:
    return "".join(w[0] for w in _norm_name(name).split() if w).upper()


class TimetableService:
    # ── upload / extraction ─────────────────────────────────────────────────
    def upload(self, db: Session, actor: User, filename: str, content_type: str, data: bytes,
               department: str = "all") -> tuple[TimetableImport, bool]:
        """Store the file and a pending import. Returns (import, created); an identical file returns the existing one."""
        sha = hashlib.sha256(data).hexdigest()
        existing = db.exec(select(TimetableImport).where(TimetableImport.source_sha256 == sha,
                                                         TimetableImport.status != "discarded")).first()
        if existing:
            return existing, False
        imp = TimetableImport(class_key="pending", source_filename=filename[:200], source_sha256=sha,
                              status="extracting", department=department, uploaded_by_user_id=actor.id)
        db.add(imp)
        db.commit()
        db.add(TimetableSource(import_id=imp.id, content_type=content_type or "application/octet-stream", data=data))
        db.commit()
        db.refresh(imp)
        audit_service.record(db, actor=actor.email, action="timetable_uploaded", target_id=str(imp.id),
                             metadata={"filename": filename, "sha256": sha})
        return imp, True

    def run_extraction(self, db: Session, import_id: UUID) -> TimetableImport:
        imp = db.get(TimetableImport, import_id)
        src = db.get(TimetableSource, import_id)
        if not imp or not src:
            raise TimetableError("import not found")
        for e in db.exec(select(TimetableEntry).where(TimetableEntry.import_id == imp.id)):
            db.delete(e)
        imp.extraction_error = None
        try:
            out = extract(imp.source_filename, src.content_type, src.data)
        except ExtractionError as e:
            # Still a usable draft: the reviewer can enter the lectures by hand.
            imp.status, imp.extraction_error, imp.extraction_method = "draft", str(e), None
            if imp.class_key == "pending":
                imp.class_key = ""
            db.add(imp)
            db.commit()
            return imp
        except Exception as e:  # noqa: BLE001 — surface any extractor crash to the reviewer
            log.error("timetable extraction failed", import_id=str(import_id), error=str(e))
            imp.status, imp.extraction_error = "failed", f"Extraction failed: {e}"[:500]
            db.add(imp)
            db.commit()
            return imp

        header = parse_header(out.get("header") or {})
        imp.header_raw = json.dumps(out.get("header") or {})
        imp.legend = json.dumps(out.get("legend") or [])
        imp.extraction_method = out["method"]
        imp.extraction_notes = json.dumps(out.get("notes") or [])
        imp.year_label, imp.division = header["year_label"], header["division"]
        imp.semester, imp.academic_term = header["semester"], header["academic_term"]
        imp.effective_from = header["effective_from"]
        imp.class_key = header["class_key"] or ""
        imp.version = self._next_version(db, imp)
        for s in cells_to_slots(out.get("cells") or []):
            for abbr in s.faculty or [None]:
                db.add(TimetableEntry(
                    import_id=imp.id, weekday=s.weekday if s.weekday is not None else -1,
                    start_time=s.start_time or "", end_time=s.end_time or "", subject=s.subject, room=s.room,
                    faculty_abbrev=abbr, kind=s.kind, batch=s.batch, source_cell=s.raw[:300],
                    issues=json.dumps([i for i in s.issues if i in _STICKY]),
                ))
        imp.status = "draft"
        db.add(imp)
        db.commit()
        self.recompute(db, imp)
        return imp

    def _next_version(self, db: Session, imp: TimetableImport) -> int:
        if not imp.class_key:
            return 1
        versions = [i.version for i in db.exec(select(TimetableImport).where(
            TimetableImport.class_key == imp.class_key, TimetableImport.id != imp.id,
            TimetableImport.status.in_(["published", "superseded", "draft"])))]
        return max(versions, default=0) + 1

    # ── review ──────────────────────────────────────────────────────────────
    def entries(self, db: Session, imp: TimetableImport) -> list[TimetableEntry]:
        return list(db.exec(select(TimetableEntry).where(TimetableEntry.import_id == imp.id)
                            .order_by(TimetableEntry.weekday, TimetableEntry.start_time)))

    def published_for(self, db: Session, class_key: str, exclude: Optional[UUID] = None) -> Optional[TimetableImport]:
        stmt = select(TimetableImport).where(TimetableImport.class_key == class_key, TimetableImport.status == "published")
        if exclude:
            stmt = stmt.where(TimetableImport.id != exclude)
        return db.exec(stmt).first()

    def _alias_map(self, db: Session) -> dict[str, UUID]:
        return {a.abbrev: a.user_id for a in db.exec(select(FacultyAlias))}

    def recompute(self, db: Session, imp: TimetableImport) -> None:
        """Re-resolve faculty through verified aliases and rebuild every entry's review flags."""
        aliases = self._alias_map(db)
        entries = self.entries(db, imp)
        others = [] if not imp.class_key else [
            e for e, i in db.exec(select(TimetableEntry, TimetableImport)
                                  .where(TimetableEntry.import_id == TimetableImport.id)
                                  .where(TimetableImport.status == "published")
                                  .where(TimetableImport.class_key != imp.class_key))
        ]
        seen: set[tuple] = set()
        for e in entries:
            flags = {i for i in _issues(e) if i in _STICKY}
            abbr = (e.faculty_abbrev or "").upper() or None
            e.faculty_abbrev = abbr
            e.faculty_user_id = aliases.get(abbr) if abbr else None
            if e.weekday is None or not 0 <= e.weekday <= 6:
                flags.add("missing_day")
            if not (valid_hhmm(e.start_time) and valid_hhmm(e.end_time) and e.start_time < e.end_time):
                flags.add("missing_time")
            if not e.subject:
                flags.add("missing_subject")
            if not e.room:
                flags.add("missing_room")
            if not abbr:
                flags.add("no_faculty")
            elif not e.faculty_user_id:
                flags.add("unknown_faculty")
            k = entry_key(e)
            if k in seen:
                flags.add("duplicate")
            seen.add(k)
            if abbr and any(o.id != e.id and (o.faculty_abbrev or "").upper() == abbr and _overlaps(e, o)
                            and entry_key(o) != k for o in entries):
                flags.add("overlap")
            if e.faculty_user_id and any(o.faculty_user_id == e.faculty_user_id and _overlaps(e, o) for o in others):
                flags.add("clash")
            e.issues = json.dumps(sorted(flags))
            db.add(e)
        db.commit()

    def counts(self, entries: list[TimetableEntry]) -> dict[str, Any]:
        flags: dict[str, int] = {}
        for e in entries:
            for i in _issues(e):
                flags[i] = flags.get(i, 0) + 1
        return {
            "entries": len(entries),
            "blocking": sum(1 for e in entries if set(_issues(e)) & BLOCKING),
            "warnings": sum(1 for e in entries if set(_issues(e)) & WARNINGS and not set(_issues(e)) & BLOCKING),
            "by_issue": flags,
        }

    def diff(self, db: Session, imp: TimetableImport) -> Optional[dict[str, Any]]:
        """Proposed changes against the currently published version of the same class (None if first version)."""
        if not imp.class_key or imp.status == "published":
            return None
        pub = self.published_for(db, imp.class_key, exclude=imp.id)
        if not pub:
            return None
        old = {_slot_key(e): e for e in self.entries(db, pub)}
        new = {_slot_key(e): e for e in self.entries(db, imp)}
        changed = [(old[k], new[k]) for k in old.keys() & new.keys() if entry_key(old[k]) != entry_key(new[k])]
        return {
            "published_import_id": str(pub.id), "published_version": pub.version,
            "added": [new[k] for k in new.keys() - old.keys()],
            "removed": [old[k] for k in old.keys() - new.keys()],
            "changed": changed,
            "unchanged": len(old.keys() & new.keys()) - len(changed),
        }

    def _require_draft(self, imp: TimetableImport) -> None:
        if imp.status != "draft":
            raise TimetableError("only draft timetables can be edited")

    def update_header(self, db: Session, imp: TimetableImport, fields: dict[str, Any]) -> TimetableImport:
        self._require_draft(imp)
        for k in ("year_label", "division", "semester", "academic_term", "effective_from"):
            if k in fields:
                setattr(imp, k, fields[k] or None)
        if imp.year_label:
            imp.year_label = imp.year_label.strip().upper().replace(".", "").replace(" ", "")
        if imp.division:
            imp.division = imp.division.strip().upper()
        imp.class_key = f"{imp.year_label}-{imp.division}" if imp.year_label and imp.division else ""
        imp.version = self._next_version(db, imp)
        db.add(imp)
        db.commit()
        self.recompute(db, imp)
        db.refresh(imp)
        return imp

    def _apply(self, e: TimetableEntry, fields: dict[str, Any]) -> None:
        for k in ("weekday", "start_time", "end_time", "subject", "room", "faculty_abbrev", "kind", "batch"):
            if k in fields:
                v = fields[k]
                setattr(e, k, (v.strip() or None) if isinstance(v, str) and k not in ("start_time", "end_time") else v)
        if "faculty_abbrev" in fields and e.faculty_abbrev and not _ABBR.match(e.faculty_abbrev.upper()):
            raise TimetableError("faculty initials must be 1–4 letters")
        for t in ("start_time", "end_time"):
            if t in fields and fields[t] and not valid_hhmm(fields[t]):
                raise TimetableError("times must be HH:MM (24-hour)")
        if e.kind not in ("lecture", "lab", "tutorial"):
            raise TimetableError("kind must be lecture, lab or tutorial")
        e.edited = True
        e.issues = "[]"  # a reviewer's correction clears the extraction flags; recompute adds the rest

    def add_entry(self, db: Session, imp: TimetableImport, fields: dict[str, Any]) -> TimetableEntry:
        self._require_draft(imp)
        e = TimetableEntry(import_id=imp.id, weekday=-1, start_time="", end_time="", source_cell="(added by reviewer)")
        self._apply(e, fields)
        db.add(e)
        db.commit()
        self.recompute(db, imp)
        db.refresh(e)
        return e

    def update_entry(self, db: Session, imp: TimetableImport, e: TimetableEntry, fields: dict[str, Any]) -> TimetableEntry:
        self._require_draft(imp)
        self._apply(e, fields)
        db.add(e)
        db.commit()
        self.recompute(db, imp)
        db.refresh(e)
        return e

    def delete_entry(self, db: Session, imp: TimetableImport, e: TimetableEntry) -> None:
        self._require_draft(imp)
        db.delete(e)
        db.commit()
        self.recompute(db, imp)

    # ── publish ─────────────────────────────────────────────────────────────
    def publish(self, db: Session, actor: User, imp: TimetableImport, acknowledge_warnings: bool) -> dict[str, Any]:
        self._require_draft(imp)
        if not imp.class_key:
            raise TimetableError("set the class year and division before publishing")
        self.recompute(db, imp)
        entries = self.entries(db, imp)
        if not entries:
            raise TimetableError("the timetable has no entries")
        c = self.counts(entries)
        if c["blocking"]:
            raise TimetableError(f"{c['blocking']} entr{'y' if c['blocking'] == 1 else 'ies'} still need fixing "
                                 "(unknown initials, missing times, unreadable cells or duplicates)")
        if c["warnings"] and not acknowledge_warnings:
            raise TimetableError(f"{c['warnings']} entr{'y has' if c['warnings'] == 1 else 'ies have'} warnings; "
                                 "review them and confirm to publish")
        d = self.diff(db, imp)
        old = self.published_for(db, imp.class_key, exclude=imp.id)
        carried = 0
        if old:
            new_by_slot = {_slot_key(e): e for e in entries}
            for e in self.entries(db, old):
                match = new_by_slot.get(_slot_key(e))
                for ex in db.exec(select(ScheduleException).where(ScheduleException.entry_id == e.id)):
                    if match:
                        ex.entry_id = match.id
                        db.add(ex)
                        carried += 1
            old.status = "superseded"
            db.add(old)
        imp.status = "published"
        imp.published_at = datetime.now(timezone.utc)
        imp.published_by_user_id = actor.id
        db.add(imp)
        db.commit()
        summary = {
            "class_key": imp.class_key, "version": imp.version, "entries": len(entries),
            "added": len(d["added"]) if d else len(entries), "removed": len(d["removed"]) if d else 0,
            "changed": len(d["changed"]) if d else 0, "exceptions_carried_over": carried,
            "superseded_import_id": str(old.id) if old else None,
        }
        audit_service.record(db, actor=actor.email, action="timetable_published", target_id=str(imp.id), metadata=summary)
        self._notify_published(db, actor, imp, old)
        return summary

    def _notify_published(self, db: Session, actor: User, imp: TimetableImport, old: Optional[TimetableImport]) -> None:
        label = " ".join(p for p in (imp.year_label, imp.division) if p) or imp.class_key
        users: dict[UUID, int] = {}
        for e in self.entries(db, imp):
            if e.faculty_user_id:
                users[e.faculty_user_id] = users.get(e.faculty_user_id, 0) + 1
        dropped = set()
        if old:
            dropped = {e.faculty_user_id for e in self.entries(db, old) if e.faculty_user_id} - users.keys()
        for uid, n in users.items():
            u = db.get(User, uid)
            notice_service.notify(db, actor, [u], f"Timetable {'updated' if old else 'published'}: {label}",
                                  f"{n} weekly slot(s) for you in the {label} timetable"
                                  f"{' (version ' + str(imp.version) + ')' if old else ''}. See My Work → My Schedule.")
        for uid in dropped:
            notice_service.notify(db, actor, [db.get(User, uid)], f"Timetable updated: {label}",
                                  f"You no longer have lectures in the {label} timetable.")

    def discard(self, db: Session, actor: User, imp: TimetableImport) -> None:
        if imp.status not in ("draft", "failed"):
            raise TimetableError("only drafts can be discarded")
        imp.status = "discarded"
        db.add(imp)
        db.commit()
        audit_service.record(db, actor=actor.email, action="timetable_discarded", target_id=str(imp.id))

    # ── faculty initials ────────────────────────────────────────────────────
    def add_alias(self, db: Session, actor: User, abbrev: str, user_id: UUID) -> FacultyAlias:
        abbrev = (abbrev or "").strip().upper()
        if not _ABBR.match(abbrev):
            raise TimetableError("initials must be 1–4 letters")
        user = db.get(User, user_id)
        if not user or not user.is_active or user.role == "student":
            raise TimetableError("initials can only be mapped to an active staff account")
        if db.exec(select(FacultyAlias).where(FacultyAlias.abbrev == abbrev)).first():
            raise TimetableError(f"{abbrev} is already mapped; remove that mapping first")
        alias = FacultyAlias(abbrev=abbrev, user_id=user.id, verified_by_user_id=actor.id)
        db.add(alias)
        db.commit()
        db.refresh(alias)
        audit_service.record(db, actor=actor.email, action="faculty_alias_created", target_id=str(alias.id),
                             metadata={"abbrev": abbrev, "user": user.email})
        self._recompute_drafts(db)
        return alias

    def remove_alias(self, db: Session, actor: User, alias: FacultyAlias) -> None:
        meta = {"abbrev": alias.abbrev, "user_id": str(alias.user_id)}
        db.delete(alias)
        db.commit()
        audit_service.record(db, actor=actor.email, action="faculty_alias_removed", target_id=str(alias.id), metadata=meta)
        self._recompute_drafts(db)

    def _recompute_drafts(self, db: Session) -> None:
        # Published timetables keep the accounts they were published with; drafts pick up the change.
        for imp in db.exec(select(TimetableImport).where(TimetableImport.status == "draft")):
            self.recompute(db, imp)

    def suggestions(self, db: Session, imp: TimetableImport) -> list[dict[str, Any]]:
        """For each unmapped set of initials: subjects taught, legend names for those subjects, and matching
        staff accounts. Candidates are hints for the coordinator — nothing is mapped automatically."""
        try:
            legend = json.loads(imp.legend or "[]")
        except json.JSONDecodeError:
            legend = []
        staff = list(db.exec(select(User).where(User.role != "student", User.is_active == True)))  # noqa: E712
        unknown: dict[str, set[str]] = {}
        for e in self.entries(db, imp):
            if e.faculty_abbrev and not e.faculty_user_id:
                unknown.setdefault(e.faculty_abbrev, set()).add((e.subject or "").upper())
        out = []
        for abbr, subjects in sorted(unknown.items()):
            names: list[str] = []
            for row in legend:
                code = str(row.get("code", "")).upper().replace(" LAB", "").strip()
                if code in subjects:
                    names += [n.strip() for n in re.split(r",|&| and ", str(row.get("faculty", ""))) if n.strip()]
            legend_names = [n for n in dict.fromkeys(names) if _initials(n) == abbr]
            candidates = []
            for u in staff:
                full = u.full_name or ""
                reasons = []
                if any(_norm_name(n) and _norm_name(n) == _norm_name(full) for n in legend_names):
                    reasons.append("name in the sheet's legend")
                if _initials(full) == abbr:
                    reasons.append("initials match")
                if reasons:
                    candidates.append({"user_id": str(u.id), "name": full or u.email, "email": u.email,
                                       "department": u.department, "reason": " + ".join(reasons)})
            out.append({"abbrev": abbr, "subjects": sorted(s for s in subjects if s), "legend_names": legend_names,
                        "candidates": candidates, "ambiguous": len(candidates) > 1})
        return out


timetable_service = TimetableService()
