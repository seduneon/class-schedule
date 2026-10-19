"""Shared, solver-free views of a solution used by several checks."""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from scheduler.config import Config
from scheduler.derived import StageBSection, stage_b_sections
from scheduler.domain import Instance, Placement, SectionKey, Solution, TimePattern, is_placeholder
from scheduler.time import patterns_overlap


@dataclass(frozen=True)
class PlacedSection:
    """A placement whose section, pattern and room exist in the instance."""

    placement: Placement
    section: StageBSection
    pattern: TimePattern

    @property
    def professor_id(self) -> str:
        return self.section.professor_id

    @property
    def course_id(self) -> str:
        return self.section.section.course_id

    @property
    def label(self) -> str:
        return self.section.id


def stage_b(instance: Instance, solution: Solution) -> dict[SectionKey, StageBSection]:
    return {s.key: s for s in stage_b_sections(instance, solution.assignments)}


def placed_sections(instance: Instance, solution: Solution) -> list[PlacedSection]:
    """Placements resolvable against the instance (invalid ones are B1's business)."""
    sections = stage_b(instance, solution)
    out: list[PlacedSection] = []
    for p in solution.placements or ():
        sec = sections.get(p.section_key)
        pat = instance.pattern_by_id.get(p.pattern_id)
        if sec is not None and pat is not None and p.room_id in instance.room_by_id:
            out.append(PlacedSection(p, sec, pat))
    return sorted(out, key=lambda x: (x.label, x.placement.pattern_id, x.placement.room_id))


def overlapping_pairs(
    placed: list[PlacedSection],
    config: Config,
    group_key: Callable[[PlacedSection], str | None],
) -> Iterator[tuple[str, PlacedSection, PlacedSection]]:
    """Pairs of placements sharing ``group_key`` (None = skip) whose patterns overlap."""
    groups: dict[str, list[PlacedSection]] = {}
    for x in placed:
        k = group_key(x)
        if k is not None:
            groups.setdefault(k, []).append(x)
    for k in sorted(groups):
        for a, b in itertools.combinations(groups[k], 2):
            if patterns_overlap(a.pattern, b.pattern, config.time.buffer_minutes):
                yield k, a, b


def professor_key(x: PlacedSection) -> str | None:
    return None if is_placeholder(x.professor_id) else x.professor_id
