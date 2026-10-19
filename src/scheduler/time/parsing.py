"""Parsing of days and clock times (SPEC §8)."""

from __future__ import annotations

import re

from scheduler.domain import DAYS, Meeting

_LETTER_DAYS: dict[str, str] = {
    "M": "Mon",
    "T": "Tue",
    "Tu": "Tue",
    "W": "Wed",
    "R": "Thu",
    "Th": "Thu",
    "F": "Fri",
    "S": "Sat",
    "Sa": "Sat",
    "U": "Sun",
    "Su": "Sun",
}
_TOKEN = re.compile(r"Th|Tu|Sa|Su|[MTWRFSU]")
_CLOCK = re.compile(r"^(\d{1,2}):(\d{2})$")


def parse_clock(text: str) -> int:
    """``"09:30"`` -> 570 minutes since midnight. ``24:00`` is allowed as end of day."""
    m = _CLOCK.match(text.strip())
    if not m:
        raise ValueError(f"invalid time {text!r}; expected HH:MM")
    hours, minutes = int(m.group(1)), int(m.group(2))
    if minutes >= 60 or hours > 24 or (hours == 24 and minutes > 0):
        raise ValueError(f"invalid time {text!r}")
    return hours * 60 + minutes


def format_clock(minutes: int) -> str:
    """570 -> ``"09:30"``."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_day(text: str) -> str:
    """Parse one day: a full name (``Mon``, ``monday``) or a letter code (``M``, ``R``, ``Th``)."""
    t = text.strip()
    for d in DAYS:
        if t.lower() in (d.lower(), _full_name(d).lower()):
            return d
    if t in _LETTER_DAYS:
        return _LETTER_DAYS[t]
    raise ValueError(f"unknown day {text!r}")


def parse_days(text: str) -> tuple[str, ...]:
    """Parse a day string such as ``MWF``, ``TR``, ``TTh`` or ``Mon;Wed``, in week order."""
    t = text.strip()
    if not t:
        raise ValueError("empty day string")
    if ";" in t or "," in t:
        days = [parse_day(part) for part in re.split(r"[;,]", t) if part.strip()]
    elif _consumes_fully(t):
        days = [_LETTER_DAYS[tok] for tok in _TOKEN.findall(t)]
    else:
        days = [parse_day(t)]
    if len(set(days)) != len(days):
        raise ValueError(f"repeated day in {text!r}")
    return tuple(d for d in DAYS if d in days)


def make_meetings(days: tuple[str, ...], start: int, end: int) -> tuple[Meeting, ...]:
    """One meeting per day with the same interval."""
    if end <= start:
        raise ValueError(f"end {format_clock(end)} must be after start {format_clock(start)}")
    return tuple(Meeting(d, start, end) for d in days)


def _consumes_fully(text: str) -> bool:
    return "".join(_TOKEN.findall(text)) == text


def _full_name(day: str) -> str:
    return {
        "Mon": "Monday",
        "Tue": "Tuesday",
        "Wed": "Wednesday",
        "Thu": "Thursday",
        "Fri": "Friday",
        "Sat": "Saturday",
        "Sun": "Sunday",
    }[day]
