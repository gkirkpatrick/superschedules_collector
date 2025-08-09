from __future__ import annotations

"""Utility helpers for event scrapers."""

from datetime import datetime, time
from zoneinfo import ZoneInfo
from hashlib import sha1
from urllib.parse import urlparse


def to_iso_datetime(value: str | None, tz: str | None = None, *, end: bool = False) -> str | None:
    """Return an ISO8601 string with timezone offset.

    Parameters
    ----------
    value:
        Input date or datetime string. Accepts ``YYYY-MM-DD`` or
        ``YYYY-MM-DDTHH:MM:SS`` forms. ``None`` values return ``None``.
    tz:
        Optional IANA timezone name used when ``value`` is naive.  Defaults
        to UTC.
    end:
        When ``True`` and ``value`` contains only a date, set the time
        component to ``23:59:59`` instead of midnight.
    """
    if not value:
        return None

    if "T" in value:
        dt = datetime.fromisoformat(value)
    else:
        y, m, d = map(int, value.split("-"))
        t = time(23, 59, 59) if end else time(0, 0, 0)
        dt = datetime(y, m, d, t.hour, t.minute, t.second)

    if dt.tzinfo is None:
        zone = ZoneInfo(tz) if tz else ZoneInfo("UTC")
        dt = dt.replace(tzinfo=zone)

    return dt.isoformat()


def make_external_id(page_url: str, title: str, start: str) -> str:
    """Create a stable external identifier from metadata."""
    host = urlparse(page_url).netloc
    raw = f"{host}|{title}|{start}"
    return f"{host}:{sha1(raw.encode()).hexdigest()[:16]}"
