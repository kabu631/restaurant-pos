"""
Nepal time and fiscal-year helpers — the single source of truth for dates.

Storage convention: every timestamp is a *naive* datetime in Nepal Time
(NPT, UTC+5:45).  database.py pins the PostgreSQL session timezone to
Asia/Kathmandu so server-side defaults such as now() agree with values
written from Python.  API responses use iso(), which appends the +05:45
offset so browsers parse times correctly whatever their own clock zone.
"""
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

NPT = timezone(timedelta(hours=5, minutes=45))


def now() -> datetime:
    """Current Nepal time as a naive datetime (the storage format)."""
    return datetime.now(NPT).replace(tzinfo=None)


def today() -> date:
    return now().date()


def to_npt(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalise a stored (naive NPT) or timezone-aware datetime to naive NPT."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(NPT).replace(tzinfo=None)
    return dt


def iso(dt: Optional[datetime]) -> Optional[str]:
    """ISO-8601 string with the +05:45 offset, or None."""
    if dt is None:
        return None
    return to_npt(dt).replace(tzinfo=NPT).isoformat()


def day_bounds(d: date) -> tuple[datetime, datetime]:
    """Half-open [start, end) of an NPT calendar day, as naive datetimes."""
    start = datetime.combine(d, time.min)
    return start, start + timedelta(days=1)


def fiscal_year(d: Optional[date] = None) -> str:
    """Nepal fiscal year, which starts on 1 Shrawan (≈ 16 July): e.g. '2083/84'."""
    d = d or today()
    bs = d.year + 56 if (d.month, d.day) < (7, 16) else d.year + 57
    return f"{bs}/{str(bs + 1)[-2:]}"


def fiscal_year_bounds(fy: str) -> tuple[datetime, datetime]:
    """'2083/84' → half-open naive NPT range [16 Jul 2026, 16 Jul 2027)."""
    ad_start = int(fy.split("/")[0]) - 57
    return datetime(ad_start, 7, 16), datetime(ad_start + 1, 7, 16)
