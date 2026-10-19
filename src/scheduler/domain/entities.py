"""Immutable domain entities (SPEC §3, §8).

Times are stored as minutes since midnight. Days use the three-letter names in
:data:`DAYS`. Every entity is a frozen dataclass so instances can be shared and cached.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

DAYS: tuple[str, ...] = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
"""Canonical day names, in week order."""

DAY_LETTERS: dict[str, str] = {
    "Mon": "M",
    "Tue": "T",
    "Wed": "W",
    "Thu": "R",
    "Fri": "F",
    "Sat": "S",
    "Sun": "U",
}
"""One-letter day codes used in day families (``MWF``, ``TR``)."""

TBA_PREFIX = "TBA-"
"""Prefix of placeholder instructors (A7 `external`); exempt from B3."""


class SectionType(StrEnum):
    """Section types K (SPEC §3.1)."""

    L = "L"
    R = "R"
    LAB = "LAB"


class ScheduleStyle(StrEnum):
    """Back-to-back preference sigma_p (SPEC §3.3)."""

    COMPACT = "compact"
    SPREAD = "spread"
    NONE = "none"


class FamilyMixing(StrEnum):
    """chi_p: may a professor mix day families (B13, SPEC §3.3)."""

    ALLOW = "allow"
    AVOID = "avoid"
    FORBID = "forbid"


class Source(StrEnum):
    """Origin of an assignment row (SPEC §5.4)."""

    PRE = "pre"
    MODEL = "model"
    MANUAL = "manual"


def is_placeholder(professor_id: str) -> bool:
    """Return True for placeholder instructors such as ``TBA-MATH161``."""
    return professor_id.startswith(TBA_PREFIX)


def placeholder_for(course_id: str) -> str:
    """Placeholder instructor ID for a course (A7 `external`)."""
    return f"{TBA_PREFIX}{course_id}"


def section_label(index: int, section_type: SectionType) -> str:
    """Label of the ``index``-th (1-based) section of a type, e.g. ``2L`` (SPEC §5.4)."""
    return f"{index}{section_type.value}"


def label_index(label: str) -> int:
    """Numeric part of a section label (``"12L"`` -> 12); 0 if there is none."""
    digits = ""
    for ch in label:
        if not ch.isdigit():
            break
        digits += ch
    return int(digits) if digits else 0


def label_sort_key(label: str) -> tuple[int, str]:
    """Sort labels numerically first (``2L`` before ``10L``)."""
    return (label_index(label), label)


@dataclass(frozen=True, order=True)
class Meeting:
    """One weekly meeting: ``day`` from ``start`` (inclusive) to ``end`` (exclusive), minutes."""

    day: str
    start: int
    end: int


@dataclass(frozen=True)
class Interval:
    """A day-bound interval (unavailability, blocked slot)."""

    day: str
    start: int
    end: int


@dataclass(frozen=True)
class TimePattern:
    """A weekly meeting pattern t in T, e.g. MWF 09:00-09:50."""

    id: str
    meetings: tuple[Meeting, ...]
    allowed_types: frozenset[SectionType]

    @property
    def days(self) -> tuple[str, ...]:
        """Days on which the pattern meets, in week order."""
        return tuple(d for d in DAYS if any(m.day == d for m in self.meetings))

    @property
    def family(self) -> str:
        """Day family f(t), e.g. ``MWF`` or ``TR`` (SPEC §3.1)."""
        return "".join(DAY_LETTERS[d] for d in self.days)

    def allows(self, section_type: SectionType) -> bool:
        """Whether the pattern may host sections of ``section_type``."""
        return section_type in self.allowed_types


@dataclass(frozen=True)
class Professor:
    """A professor p in P with the parameters of SPEC §3.3."""

    id: str
    name: str
    load_min: float
    load_max: float
    priority: float = 1.0
    max_preps: int | None = None
    max_days: int | None = None
    multi_section_pref: int = 0
    schedule_style: ScheduleStyle = ScheduleStyle.NONE
    day_families: frozenset[str] = frozenset()
    day_family_mixing: FamilyMixing = FamilyMixing.ALLOW


@dataclass(frozen=True)
class Offering:
    """One row of ``offerings``: ``num_sections`` sections of (course, type)."""

    course_id: str
    title: str
    level: int
    section_type: SectionType
    num_sections: int
    capacity: int
    units: float
    room_type: str


@dataclass(frozen=True)
class Room:
    """A room r in R."""

    id: str
    building: str
    capacity: int
    room_type: str


@dataclass(frozen=True)
class RoomAvailability:
    """Room ``room_id`` may be used at pattern ``pattern_id`` (A_r, SPEC §3.1)."""

    room_id: str
    pattern_id: str


@dataclass(frozen=True)
class Section:
    """A labeled section s in S (expanded from offerings, SPEC §5.4)."""

    course_id: str
    section_type: SectionType
    label: str
    capacity: int
    units: float
    room_type: str
    level: int

    @property
    def id(self) -> str:
        """Readable section ID, e.g. ``MATH161-1L``."""
        return f"{self.course_id}-{self.label}"

    @property
    def key(self) -> SectionKey:
        """``(course_id, section_type, label)``."""
        return (self.course_id, self.section_type, self.label)


SectionKey = tuple[str, SectionType, str]
OfferingKey = tuple[str, SectionType]


@dataclass(frozen=True)
class CoursePreference:
    """Rank of a course for a professor; ``rank is None`` means *cannot teach*.

    ``section_type`` None applies the rank to every type of the course (SPEC §3.4).
    """

    professor_id: str
    course_id: str
    rank: int | None
    section_type: SectionType | None = None

    @property
    def cannot(self) -> bool:
        return self.rank is None


@dataclass(frozen=True)
class TimePreference:
    """Rank of a time pattern for a professor; ``rank is None`` means *cannot*."""

    professor_id: str
    pattern_id: str
    rank: int | None

    @property
    def cannot(self) -> bool:
        return self.rank is None


@dataclass(frozen=True)
class Unavailability:
    """Professor unavailable on ``day`` in ``[start, end)``."""

    professor_id: str
    day: str
    start: int
    end: int
    reason: str = ""

    @property
    def interval(self) -> Interval:
        return Interval(self.day, self.start, self.end)


@dataclass(frozen=True)
class BlockedSlot:
    """Time nobody may be scheduled in (e.g. university hour)."""

    day: str
    start: int
    end: int
    reason: str = ""

    @property
    def interval(self) -> Interval:
        return Interval(self.day, self.start, self.end)


@dataclass(frozen=True)
class PreAssignment:
    """Pre-assigned section count (A4); optional explicit section labels."""

    professor_id: str
    course_id: str
    section_type: SectionType
    count: int
    section_labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConflictGroup:
    """Courses students take together (B5). ``mode``/``weight`` None = inherit from B5."""

    id: str
    course_ids: frozenset[str]
    mode: str | None = None
    weight: float | None = None


@dataclass(frozen=True)
class StageAPin:
    """L4: fix the number of (course, type) sections a professor teaches."""

    professor_id: str
    course_id: str
    section_type: SectionType
    count: int


@dataclass(frozen=True)
class StageBPin:
    """L4: fix the pattern and/or room of one section (partial pins allowed)."""

    course_id: str
    section_type: SectionType
    section_label: str
    pattern_id: str | None = None
    room_id: str | None = None


@dataclass(frozen=True)
class SectionLink:
    """Recitation linked to a specific lecture (B7)."""

    course_id: str
    recitation_label: str
    lecture_label: str


@dataclass(frozen=True)
class Assignment:
    """One row of the Stage A hand-off file (SPEC §5.4)."""

    professor_id: str
    course_id: str
    section_type: SectionType
    section_label: str
    capacity: int
    units: float
    source: Source = Source.MODEL

    @property
    def section_key(self) -> SectionKey:
        return (self.course_id, self.section_type, self.section_label)


@dataclass(frozen=True)
class Placement:
    """Stage B decision: a section meets in ``pattern_id`` in ``room_id``."""

    course_id: str
    section_type: SectionType
    section_label: str
    pattern_id: str
    room_id: str

    @property
    def section_key(self) -> SectionKey:
        return (self.course_id, self.section_type, self.section_label)


@dataclass(frozen=True)
class Solution:
    """A (possibly human-edited) solution: Stage A assignments, optional Stage B placements."""

    assignments: tuple[Assignment, ...]
    placements: tuple[Placement, ...] | None = None
    meta: dict[str, object] = field(default_factory=dict, compare=False, hash=False)
