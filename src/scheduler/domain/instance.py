"""The problem instance (SPEC §3, §10 *Key interfaces*).

``Instance`` is immutable. Lookups and derived structures that do not depend on the
configuration are cached properties; config-dependent ones (cliques, feasible triples,
alpha_p) are cached through :meth:`Instance.memo`.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass, field
from functools import cached_property
from typing import TypeVar, cast

from scheduler.domain.entities import (
    BlockedSlot,
    ConflictGroup,
    CoursePreference,
    Offering,
    OfferingKey,
    PreAssignment,
    Professor,
    Room,
    RoomAvailability,
    Section,
    SectionKey,
    SectionLink,
    SectionType,
    StageAPin,
    StageBPin,
    TimePattern,
    TimePreference,
    Unavailability,
    section_label,
)

T = TypeVar("T")


@dataclass(frozen=True)
class OfferingInfo:
    """Aggregate of all offering rows of one (course, type): N_{c,k}, u_{c,k}."""

    course_id: str
    section_type: SectionType
    title: str
    level: int
    num_sections: int
    units: float


@dataclass(frozen=True, eq=False)
class Instance:
    """All input tables of SPEC §8, validated and immutable."""

    professors: tuple[Professor, ...]
    offerings: tuple[Offering, ...]
    rooms: tuple[Room, ...]
    patterns: tuple[TimePattern, ...]
    course_preferences: tuple[CoursePreference, ...] = ()
    time_preferences: tuple[TimePreference, ...] = ()
    unavailability: tuple[Unavailability, ...] = ()
    blocked_slots: tuple[BlockedSlot, ...] = ()
    pre_assignments: tuple[PreAssignment, ...] = ()
    conflict_groups: tuple[ConflictGroup, ...] = ()
    stage_a_pins: tuple[StageAPin, ...] = ()
    stage_b_pins: tuple[StageBPin, ...] = ()
    section_links: tuple[SectionLink, ...] = ()
    room_availability: tuple[RoomAvailability, ...] = ()
    _memo: dict[Hashable, object] = field(default_factory=dict, repr=False)

    def memo(self, key: Hashable, factory: Callable[[], T]) -> T:
        """Return the cached value for ``key``, computing it with ``factory`` once."""
        if key not in self._memo:
            self._memo[key] = factory()
        return cast(T, self._memo[key])

    # ----- lookups -------------------------------------------------------------

    @cached_property
    def professor_by_id(self) -> dict[str, Professor]:
        return {p.id: p for p in self.professors}

    @cached_property
    def room_by_id(self) -> dict[str, Room]:
        return {r.id: r for r in self.rooms}

    @cached_property
    def pattern_by_id(self) -> dict[str, TimePattern]:
        return {t.id: t for t in self.patterns}

    @cached_property
    def professor_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.professor_by_id))

    @cached_property
    def room_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.room_by_id))

    @cached_property
    def pattern_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.pattern_by_id))

    @cached_property
    def offering_info(self) -> dict[OfferingKey, OfferingInfo]:
        """N_{c,k} and u_{c,k} per (course, type), aggregating rows."""
        acc: dict[OfferingKey, OfferingInfo] = {}
        for o in self.offerings:
            key = (o.course_id, o.section_type)
            prev = acc.get(key)
            count = o.num_sections + (prev.num_sections if prev else 0)
            acc[key] = OfferingInfo(o.course_id, o.section_type, o.title, o.level, count, o.units)
        return {k: acc[k] for k in sorted(acc)}

    @cached_property
    def offering_keys(self) -> tuple[OfferingKey, ...]:
        return tuple(self.offering_info)

    @cached_property
    def course_ids(self) -> tuple[str, ...]:
        return tuple(sorted({o.course_id for o in self.offerings}))

    @cached_property
    def course_level(self) -> dict[str, int]:
        return {o.course_id: o.level for o in self.offerings}

    @cached_property
    def sections(self) -> tuple[Section, ...]:
        """Labeled sections. Per (c, k), larger capacities get lower labels (SPEC §5.4)."""
        rows: dict[OfferingKey, list[tuple[int, Offering]]] = {}
        for idx, o in enumerate(self.offerings):
            rows.setdefault((o.course_id, o.section_type), []).append((idx, o))
        out: list[Section] = []
        for key in sorted(rows):
            ordered = sorted(rows[key], key=lambda item: (-item[1].capacity, item[0]))
            i = 0
            for _, o in ordered:
                for _ in range(o.num_sections):
                    i += 1
                    out.append(
                        Section(
                            course_id=o.course_id,
                            section_type=o.section_type,
                            label=section_label(i, o.section_type),
                            capacity=o.capacity,
                            units=o.units,
                            room_type=o.room_type,
                            level=o.level,
                        )
                    )
        return tuple(out)

    @cached_property
    def section_by_key(self) -> dict[SectionKey, Section]:
        return {s.key: s for s in self.sections}

    @cached_property
    def sections_by_offering(self) -> dict[OfferingKey, tuple[Section, ...]]:
        acc: dict[OfferingKey, list[Section]] = {}
        for s in self.sections:
            acc.setdefault((s.course_id, s.section_type), []).append(s)
        return {k: tuple(v) for k, v in acc.items()}

    @cached_property
    def course_rank(self) -> dict[tuple[str, str], int | None]:
        """(professor, course) -> rank of rows without a section type, ``None`` = cannot."""
        return {
            (cp.professor_id, cp.course_id): cp.rank
            for cp in self.course_preferences
            if cp.section_type is None
        }

    @cached_property
    def course_type_rank(self) -> dict[tuple[str, str, SectionType], int | None]:
        """rho^C_{p,c,k} per offered (c, k) (SPEC §3.4): the typed row if present, else the
        untyped row of (p, c). ``None`` = cannot; missing key = unranked."""
        typed = {
            (cp.professor_id, cp.course_id, cp.section_type): cp.rank
            for cp in self.course_preferences
            if cp.section_type is not None
        }
        out: dict[tuple[str, str, SectionType], int | None] = {}
        for p in self.professor_ids:
            for c, k in self.offering_keys:
                if (p, c, k) in typed:
                    out[(p, c, k)] = typed[(p, c, k)]
                elif (p, c) in self.course_rank:
                    out[(p, c, k)] = self.course_rank[(p, c)]
        return out

    @cached_property
    def room_patterns(self) -> dict[str, frozenset[str]]:
        """A_r for rooms listed in ``room_availability`` (unlisted rooms: every pattern)."""
        acc: dict[str, set[str]] = {}
        for ra in self.room_availability:
            acc.setdefault(ra.room_id, set()).add(ra.pattern_id)
        return {r: frozenset(ts) for r, ts in sorted(acc.items())}

    def room_available(self, room_id: str, pattern_id: str) -> bool:
        """t in A_r (SPEC §3.2)."""
        allowed = self.room_patterns.get(room_id)
        return allowed is None or pattern_id in allowed

    @cached_property
    def time_rank(self) -> dict[tuple[str, str], int | None]:
        """(professor, pattern) -> rank, ``None`` = cannot. Missing key = unranked."""
        return {(tp.professor_id, tp.pattern_id): tp.rank for tp in self.time_preferences}

    @cached_property
    def unavailability_by_professor(self) -> dict[str, tuple[Unavailability, ...]]:
        acc: dict[str, list[Unavailability]] = {}
        for u in self.unavailability:
            acc.setdefault(u.professor_id, []).append(u)
        return {k: tuple(v) for k, v in acc.items()}

    @cached_property
    def pre_assigned(self) -> dict[tuple[str, str, SectionType], int]:
        """pre_{p,c,k}: summed pre-assigned counts."""
        acc: dict[tuple[str, str, SectionType], int] = {}
        for pa in self.pre_assignments:
            key = (pa.professor_id, pa.course_id, pa.section_type)
            acc[key] = acc.get(key, 0) + pa.count
        return acc

    @cached_property
    def stage_a_pin_counts(self) -> dict[tuple[str, str, SectionType], int]:
        return {(p.professor_id, p.course_id, p.section_type): p.count for p in self.stage_a_pins}

    @cached_property
    def stage_b_pin_by_section(self) -> dict[SectionKey, StageBPin]:
        return {(p.course_id, p.section_type, p.section_label): p for p in self.stage_b_pins}
