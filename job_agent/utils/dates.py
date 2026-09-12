"""Date parsing utilities."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

ISO_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2})(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?"
)
UNIX_MS_PATTERN = re.compile(r"^\d{13}$")
UNIX_S_PATTERN = re.compile(r"^\d{10}$")


def parse_date(value: str | int | float | None) -> date | None:
    """Parse various date formats to date object."""
    if value is None:
        return None

    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc).date()

    text = str(value).strip()
    if not text:
        return None

    if UNIX_MS_PATTERN.match(text):
        ts = int(text) / 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc).date()

    if UNIX_S_PATTERN.match(text):
        return datetime.fromtimestamp(int(text), tz=timezone.utc).date()

    iso_match = ISO_PATTERN.match(text)
    if iso_match:
        try:
            return date.fromisoformat(iso_match.group(1))
        except ValueError:
            pass

    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
    ):
        try:
            return datetime.strptime(text[:30], fmt).date()
        except ValueError:
            continue

    return None


def today_utc() -> date:
    """Return today's date in UTC."""
    return datetime.now(timezone.utc).date()


def is_recent_posting(
    date_posted: date | None,
    max_age_days: int,
    *,
    reference: date | None = None,
    allow_unknown: bool = False,
) -> bool:
    """Return True if posting is within max_age_days.

    When allow_unknown is False (default), jobs without a posting date are excluded.
    """
    if max_age_days <= 0:
        return True
    if date_posted is None:
        return allow_unknown
    ref = reference or today_utc()
    age = (ref - date_posted).days
    return age <= max_age_days
