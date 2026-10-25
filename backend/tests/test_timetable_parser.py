"""Timetable cell/grid parsing: deterministic rules over transcribed cell text (formats from real DJSCE sheets)."""
from app.services.timetable_parser import cells_to_slots, normalize_time, parse_cell, parse_header


def _one(text):
    slots = parse_cell(text)
    assert len(slots) == 1, slots
    return slots[0]


class TestTimes:
    def test_afternoon_hours_are_inferred(self):
        assert normalize_time("8:00") == "08:00"
        assert normalize_time("12:00") == "12:00"
        assert normalize_time("1:00") == "13:00"
        assert normalize_time("5:00") == "17:00"
        assert normalize_time("14:30") == "14:30"

    def test_garbage_is_rejected(self):
        assert normalize_time("noon") is None
        assert normalize_time("") is None


class TestCells:
    def test_lecture_with_room(self):
        s = _one("ATCD (LD) 27")
        assert (s.subject, s.faculty, s.room, s.kind, s.batch) == ("ATCD", ["LD"], "27", "lecture", None)

    def test_batch_lab(self):
        s = _one("ML_C31 (RK) L3")
        assert (s.subject, s.batch, s.faculty, s.room, s.kind) == ("ML", "C31", ["RK"], "L3", "lab")

    def test_numbered_batch_and_named_lab_room(self):
        s = _one("GDS_C5 (PM) ICB Lab")
        assert (s.subject, s.batch, s.room, s.kind) == ("GDS", "C5", "ICB Lab", "lab")
        assert _one("GDS_1 (NT) L1").batch == "1"

    def test_no_room(self):
        s = _one("IPD(AK)")
        assert (s.subject, s.faculty, s.room) == ("IPD", ["AK"], None)
        assert _one("MN&MR(SI)").subject == "MN&MR"

    def test_parallel_electives_with_rooms_inside_parentheses(self):
        slots = parse_cell("SM (NP 62, MA 63) / AA (SB 27)")
        got = [(s.subject, s.faculty, s.room) for s in slots]
        assert got == [("SM", ["NP"], "62"), ("SM", ["MA"], "63"), ("AA", ["SB"], "27")]

    def test_shared_faculty_and_room_list(self):
        slots = parse_cell("GDS(KG/NT)/FM(NP) 61,62,63")
        got = [(s.subject, s.faculty, s.room) for s in slots]
        assert got == [("GDS", ["KG", "NT"], None), ("FM", ["NP"], "61,62,63")]

    def test_break_and_blank_produce_nothing(self):
        assert parse_cell("BREAK") == []
        assert parse_cell("  ") == []

    def test_unparseable_text_is_kept_for_review(self):
        s = _one("Library hour")
        assert s.subject is None and "unparsed" in s.issues and s.raw == "Library hour"


class TestHeader:
    def test_header_fields_are_cleaned(self):
        h = parse_header({
            "department": "Department of Computer Engineering", "class": "Class: T.Y. B.TECH.",
            "semester": "Sem: V", "division": "Div: C3",
            "term": "Time Table for the Academic Term: Jul-Dec 2026", "effective_from": "w.e.f. July 16, 2026",
        })
        assert h["year_label"] == "TY" and h["division"] == "C3" and h["semester"] == "V"
        assert h["class_key"] == "TY-C3" and h["academic_term"] == "Jul-Dec 2026"
        assert h["effective_from"].isoformat() == "2026-07-16"

    def test_missing_header_gives_no_class_key(self):
        assert parse_header({})["class_key"] is None


class TestGridToSlots:
    def test_cells_become_weekly_slots_one_per_faculty(self):
        cells = [
            {"day": "Monday", "start": "8:00", "end": "10:00", "text": "SM (NP 62, MA 63) / AA (SB 27)"},
            {"day": "Tue", "start": "1:00", "end": "2:00", "text": "ICS (NG) 63"},
            {"day": "Monday", "start": "11:00", "end": "12:00", "text": "BREAK"},
            {"day": "Funday", "start": "9:00", "end": "10:00", "text": "ML (KD) 27"},
        ]
        slots = cells_to_slots(cells)
        mon = [s for s in slots if s.weekday == 0]
        assert [(s.start_time, s.end_time, s.faculty) for s in mon] == [
            ("08:00", "10:00", ["NP"]), ("08:00", "10:00", ["MA"]), ("08:00", "10:00", ["SB"])]
        tue = [s for s in slots if s.weekday == 1][0]
        assert (tue.start_time, tue.end_time) == ("13:00", "14:00")
        bad = [s for s in slots if s.weekday is None][0]
        assert "missing_day" in bad.issues
