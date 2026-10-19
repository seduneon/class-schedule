"""Row-level pydantic schemas for the input tables (SPEC §8)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from scheduler.domain import DAY_LETTERS, FamilyMixing, ScheduleStyle, SectionType, Source
from scheduler.time import parse_clock, parse_day, parse_days

DEFAULT_UNITS: dict[SectionType, float] = {
    SectionType.L: 1.0,
    SectionType.R: 0.5,
    SectionType.LAB: 0.5,
}


class Row(BaseModel):
    """Base row: unknown columns are ignored; blank cells count as absent, so optional
    columns fall back to their defaults and required ones report "Field required"."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True, frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _drop_blanks(cls, data: object) -> object:
        if isinstance(data, dict):
            return {
                k: v
                for k, v in data.items()
                if v is not None and not (isinstance(v, str) and not v.strip())
            }
        return data


def _clock(v: object) -> int:
    if isinstance(v, int):
        return v
    return parse_clock(str(v))


def _rank(v: object) -> int | None:
    """Parse a rank: positive integer, or the literal ``cannot`` (returned as None)."""
    text = str(v).strip()
    if text.lower() == "cannot":
        return None
    try:
        num = float(text)
    except ValueError:
        raise ValueError(f"rank must be a positive integer or 'cannot', got {text!r}") from None
    if num != int(num) or num < 1:
        raise ValueError(f"rank must be a positive integer or 'cannot', got {text!r}")
    return int(num)


def day_family(text: str) -> str:
    """Normalize a day family: ``"M W F"``, ``"MWF"`` and ``"Mon Wed Fri"`` -> ``"MWF"``."""
    return "".join(DAY_LETTERS[d] for d in parse_days(text))


def _families(v: object) -> frozenset[str]:
    """Parse ``day_families`` (``MWF;TR``) into normalized families; blank = any."""
    if v is None:
        return frozenset()
    if isinstance(v, frozenset | set | tuple | list):
        return frozenset(day_family(str(x)) for x in v)
    parts = [p.strip() for p in str(v).replace(",", ";").split(";") if p.strip()]
    return frozenset(day_family(p) for p in parts)


def _int(v: object) -> object:
    """Accept ``"3"`` and ``"3.0"`` (Excel) as integers."""
    if isinstance(v, str):
        try:
            f = float(v)
        except ValueError:
            return v
        if f == int(f):
            return int(f)
    if isinstance(v, float) and v == int(v):
        return int(v)
    return v


class ProfessorRow(Row):
    professor_id: str
    name: str
    load_min: float = Field(ge=0)
    load_max: float = Field(ge=0)
    priority: float = Field(default=1.0, gt=0)
    max_preps: int | None = Field(default=None, ge=0)
    max_days: int | None = Field(default=None, ge=0)
    multi_section_pref: Literal[-1, 0, 1] = 0
    schedule_style: ScheduleStyle = ScheduleStyle.NONE
    day_families: frozenset[str] = frozenset()
    day_family_mixing: FamilyMixing = FamilyMixing.ALLOW

    _fam = field_validator("day_families", mode="before")(lambda v: _families(v))
    _ints = field_validator("max_preps", "max_days", "multi_section_pref", mode="before")(
        lambda v: _int(v)
    )

    @model_validator(mode="after")
    def _range(self) -> ProfessorRow:
        if self.load_min > self.load_max:
            raise ValueError(f"load_min {self.load_min} > load_max {self.load_max}")
        return self


class OfferingRow(Row):
    course_id: str
    title: str
    level: int = Field(ge=0)
    section_type: SectionType
    num_sections: int = Field(ge=0)
    capacity: int = Field(ge=0)
    units: float | None = Field(default=None, ge=0)
    room_type: str

    _ints = field_validator("level", "num_sections", "capacity", mode="before")(lambda v: _int(v))

    @property
    def effective_units(self) -> float:
        return self.units if self.units is not None else DEFAULT_UNITS[self.section_type]


class RoomRow(Row):
    room_id: str
    building: str
    capacity: int = Field(ge=0)
    room_type: str

    _ints = field_validator("capacity", mode="before")(lambda v: _int(v))


class RoomAvailabilityRow(Row):
    room_id: str
    pattern_id: str


class TimePatternRow(Row):
    pattern_id: str
    days: tuple[str, ...]
    start: int
    end: int
    allowed_section_types: frozenset[SectionType]

    @field_validator("days", mode="before")
    @classmethod
    def _days(cls, v: object) -> tuple[str, ...]:
        return parse_days(str(v))

    _clocks = field_validator("start", "end", mode="before")(lambda v: _clock(v))

    @field_validator("allowed_section_types", mode="before")
    @classmethod
    def _types(cls, v: object) -> frozenset[SectionType]:
        parts = [p.strip() for p in str(v).replace(",", ";").split(";") if p.strip()]
        if not parts:
            raise ValueError("at least one section type is required")
        return frozenset(SectionType(p) for p in parts)

    @model_validator(mode="after")
    def _order(self) -> TimePatternRow:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class CoursePreferenceRow(Row):
    professor_id: str
    course_id: str
    rank: int | None
    section_type: SectionType | None = None

    _r = field_validator("rank", mode="before")(lambda v: _rank(v))


class TimePreferenceRow(Row):
    professor_id: str
    pattern_id: str
    rank: int | None

    _r = field_validator("rank", mode="before")(lambda v: _rank(v))


class _IntervalRow(Row):
    day: str
    start: int
    end: int
    reason: str = ""

    _day = field_validator("day", mode="before")(lambda v: parse_day(str(v)))
    _clocks = field_validator("start", "end", mode="before")(lambda v: _clock(v))

    @field_validator("reason", mode="before")
    @classmethod
    def _reason(cls, v: object) -> str:
        return "" if v is None else str(v)

    @model_validator(mode="after")
    def _order(self) -> _IntervalRow:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class UnavailabilityRow(_IntervalRow):
    professor_id: str


class BlockedSlotRow(_IntervalRow):
    pass


class PreAssignmentRow(Row):
    professor_id: str
    course_id: str
    section_type: SectionType
    count: int = Field(ge=1)
    section_label: str | None = None

    _ints = field_validator("count", mode="before")(lambda v: _int(v))

    @property
    def labels(self) -> tuple[str, ...]:
        if self.section_label is None:
            return ()
        return tuple(p.strip() for p in self.section_label.split(";") if p.strip())

    @model_validator(mode="after")
    def _labels_match(self) -> PreAssignmentRow:
        if self.labels and len(self.labels) != self.count:
            raise ValueError(
                f"count {self.count} does not match {len(self.labels)} section label(s)"
            )
        return self


class ConflictGroupRow(Row):
    group_id: str
    course_id: str
    mode: Literal["hard", "soft"] | None = None
    weight: float | None = Field(default=None, ge=0)


class PinRow(Row):
    """L4 pins: a Stage A pin has ``professor_id`` and ``count``; a Stage B pin has a label."""

    course_id: str
    section_type: SectionType
    professor_id: str | None = None
    count: int | None = Field(default=None, ge=0)
    section_label: str | None = None
    pattern_id: str | None = None
    room_id: str | None = None

    _ints = field_validator("count", mode="before")(lambda v: _int(v))

    @model_validator(mode="after")
    def _kind(self) -> PinRow:
        is_a = self.count is not None
        is_b = self.section_label is not None
        if is_a == is_b:
            raise ValueError(
                "a pin needs either professor_id+count (Stage A) or section_label (Stage B)"
            )
        if is_a and self.professor_id is None:
            raise ValueError("a Stage A pin needs professor_id")
        if is_b and self.pattern_id is None and self.room_id is None:
            raise ValueError("a Stage B pin needs pattern_id and/or room_id")
        return self


class SectionLinkRow(Row):
    course_id: str
    recitation_label: str
    lecture_label: str


class AssignmentRow(Row):
    professor_id: str
    course_id: str
    section_type: SectionType
    section_label: str
    capacity: int = Field(ge=0)
    units: float = Field(ge=0)
    source: Source = Source.MANUAL

    _ints = field_validator("capacity", mode="before")(lambda v: _int(v))


TABLES: dict[str, type[Row]] = {
    "professors": ProfessorRow,
    "offerings": OfferingRow,
    "rooms": RoomRow,
    "room_availability": RoomAvailabilityRow,
    "time_patterns": TimePatternRow,
    "course_preferences": CoursePreferenceRow,
    "time_preferences": TimePreferenceRow,
    "unavailability": UnavailabilityRow,
    "blocked_slots": BlockedSlotRow,
    "pre_assignments": PreAssignmentRow,
    "conflict_groups": ConflictGroupRow,
    "pins": PinRow,
    "section_links": SectionLinkRow,
}
REQUIRED_TABLES: tuple[str, ...] = ("professors", "offerings", "rooms", "time_patterns")
