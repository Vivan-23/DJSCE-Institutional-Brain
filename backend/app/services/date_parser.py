"""
Natural-language due-date parser.

LLM extraction returns a free-text "due" field — "by Friday", "next week",
"in 3 days", "end of month", "2026-07-01", "July 1, 2026". This turns those into
a concrete UTC datetime (end of the target day, so it reads as a deadline), or
None when the phrase carries no resolvable date.

Dependency-free and deterministic (accepts an injectable ``now`` for testing).
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

_WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

# Explicit formats tried after ISO. Year-optional formats are handled separately.
_EXPLICIT_FORMATS = (
    "%Y/%m/%d", "%m/%d/%Y", "%d-%m-%Y",
    "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y",
    "%d %B %Y", "%d %b %Y",
)
_MONTH_DAY_FORMATS = ("%B %d", "%b %d", "%d %B", "%d %b")

# Filler words an LLM tends to prefix a due phrase with.
_LEADING_FILLER = re.compile(
    r"^(?:by|due|due\s+by|before|on|until|no\s+later\s+than|end\s+of\s+the)\s+",
    re.IGNORECASE,
)


def _end_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=23, minute=59, second=59, microsecond=0)


def parse_due_date(phrase: Optional[str], *, now: Optional[datetime] = None) -> Optional[datetime]:
    """Resolve a free-text due phrase to a UTC datetime, or None if unresolvable."""
    if not phrase or not isinstance(phrase, str):
        return None
    raw = phrase.strip()
    if not raw:
        return None
    now = now or datetime.now(timezone.utc)

    # 1. Explicit machine/standard dates first (most precise).
    explicit = _parse_explicit(raw, now)
    if explicit is not None:
        return explicit

    # 2. Normalize for relative-phrase matching.
    text = _LEADING_FILLER.sub("", raw.lower()).strip().rstrip(".")
    text = re.sub(r"\s+", " ", text)
    if not text:
        return None

    # today / tonight / end of day
    if text in ("today", "tonight", "eod", "end of day", "cob", "close of business"):
        return _end_of_day(now)
    if text in ("tomorrow", "tmrw"):
        return _end_of_day(now + timedelta(days=1))

    # "in N day(s)/week(s)/month(s)"
    m = re.match(r"in (\d+) (day|days|week|weeks|month|months)$", text)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit.startswith("day"):
            return _end_of_day(now + timedelta(days=n))
        if unit.startswith("week"):
            return _end_of_day(now + timedelta(weeks=n))
        return _end_of_day(_add_months(now, n))

    # end of week / this week  → upcoming Friday
    if text in ("end of week", "eow", "this week"):
        return _end_of_day(_weekday(now, 4, which="this"))
    # next week → one week out (Friday of next week reads as a deadline)
    if text in ("next week",):
        return _end_of_day(_weekday(now, 4, which="next"))
    # end of month / eom
    if text in ("end of month", "eom", "month end"):
        return _end_of_day(_end_of_month(now))

    # "(this|next) <weekday>" or bare "<weekday>"
    m = re.match(r"(?:(this|next|coming) )?([a-z]+)$", text)
    if m and m.group(2) in _WEEKDAYS:
        which = "next" if m.group(1) == "next" else "this"
        return _end_of_day(_weekday(now, _WEEKDAYS[m.group(2)], which=which))

    return None


def _parse_explicit(raw: str, now: datetime) -> Optional[datetime]:
    # ISO 8601 (with or without time / Z).
    for candidate in (raw, raw.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(candidate)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    cleaned = _LEADING_FILLER.sub("", raw).strip().rstrip(".")
    for fmt in _EXPLICIT_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    # Month/day without a year → assume the next occurrence (this year or next).
    for fmt in _MONTH_DAY_FORMATS:
        try:
            parsed = datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
        candidate = parsed.replace(year=now.year, tzinfo=timezone.utc)
        if candidate.date() < now.date():
            candidate = candidate.replace(year=now.year + 1)
        return _end_of_day(candidate)
    return None


def _weekday(now: datetime, target: int, *, which: str) -> datetime:
    """Resolve a weekday relative to ``now``. 'this' = next occurrence (today if it
    matches); 'next' = that weekday in the following week."""
    days_ahead = (target - now.weekday()) % 7  # 0 == today
    if which == "next":
        days_ahead += 7
    return now + timedelta(days=days_ahead)


def _add_months(dt: datetime, months: int) -> datetime:
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = min(dt.day, _days_in_month(year, month))
    return dt.replace(year=year, month=month, day=day)


def _end_of_month(dt: datetime) -> datetime:
    return dt.replace(day=_days_in_month(dt.year, dt.month))


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        nxt = datetime(year + 1, 1, 1)
    else:
        nxt = datetime(year, month + 1, 1)
    return (nxt - timedelta(days=1)).day
