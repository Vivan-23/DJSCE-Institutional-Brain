"""Tests for the natural-language due-date parser."""
from datetime import datetime, timedelta, timezone

import pytest

from app.services.date_parser import parse_due_date

# Fixed reference point so tests are deterministic regardless of the real date.
NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)  # a Monday


def p(phrase):
    return parse_due_date(phrase, now=NOW)


class TestExplicitDates:
    def test_iso_date(self):
        assert p("2026-07-01").date() == datetime(2026, 7, 1).date()

    def test_iso_datetime_with_z(self):
        d = p("2026-07-01T09:30:00Z")
        assert (d.year, d.month, d.day, d.hour) == (2026, 7, 1, 9)
        assert d.tzinfo is not None

    def test_month_name_with_year(self):
        assert p("July 1, 2026").date() == datetime(2026, 7, 1).date()

    def test_slash_format(self):
        assert p("07/01/2026").date() == datetime(2026, 7, 1).date()

    def test_month_day_without_year_rolls_forward(self):
        # "June 1" has already passed relative to NOW (Jun 15) → next year.
        assert p("June 1").year == 2027
        # "July 1" is still ahead this year.
        assert p("July 1").year == 2026


class TestRelativePhrases:
    def test_today_and_eod(self):
        assert p("today").date() == NOW.date()
        assert p("EOD").date() == NOW.date()

    def test_tomorrow(self):
        assert p("tomorrow").date() == (NOW + timedelta(days=1)).date()

    def test_in_n_days(self):
        assert p("in 3 days").date() == (NOW + timedelta(days=3)).date()

    def test_in_n_weeks(self):
        assert p("in 2 weeks").date() == (NOW + timedelta(weeks=2)).date()

    def test_leading_filler_stripped(self):
        # "by Friday" should resolve the same as "Friday".
        assert p("by Friday") == p("Friday")

    def test_bare_weekday_is_upcoming(self):
        d = p("Friday")
        assert d.weekday() == 4
        assert NOW <= d <= NOW + timedelta(days=7)

    def test_next_weekday_is_following_week(self):
        this_fri = p("Friday")
        next_fri = p("next Friday")
        assert next_fri.weekday() == 4
        assert next_fri == this_fri + timedelta(days=7)

    def test_next_week(self):
        d = p("next week")
        assert d > NOW + timedelta(days=6)

    def test_end_of_month(self):
        d = p("end of month")
        assert d.month == 6 and d.day == 30  # June has 30 days


class TestUnresolvable:
    @pytest.mark.parametrize("phrase", [None, "", "   ", "soon", "later", "asap", "whenever"])
    def test_returns_none(self, phrase):
        assert parse_due_date(phrase, now=NOW) is None


class TestDeadlineSemantics:
    def test_relative_dates_are_end_of_day(self):
        # Relative phrases resolve to end-of-day so they read as a deadline.
        d = p("tomorrow")
        assert (d.hour, d.minute) == (23, 59)
