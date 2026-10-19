"""L1 — post-solve: report every non-zero slack with the entities involved, in plain words."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from scheduler.config import Config
from scheduler.derived import is_eligible
from scheduler.domain import Assignment, Instance, SectionType


@dataclass(frozen=True)
class SlackReport:
    """A non-zero slack after solving."""

    cid: str
    entities: tuple[str, ...]
    description: str
    value: float
    explanation: str = ""

    def __str__(self) -> str:
        amount = f"{self.value:g}"
        text = f"[{self.cid}] {self.description}: {amount}"
        return f"{text}; {self.explanation}" if self.explanation else text


def explain_uncovered(
    instance: Instance,
    config: Config,
    course_id: str,
    section_type: SectionType,
    assignments: Sequence[Assignment],
) -> str:
    """Why sections of (c, k) stayed uncovered: who was eligible and how loaded they are."""
    loads: dict[str, float] = defaultdict(float)
    for a in assignments:
        loads[a.professor_id] += a.units
    eligible = [
        p
        for p in instance.professors
        if is_eligible(instance, config, p.id, course_id, section_type)
    ]
    if not eligible:
        return "nobody is eligible to teach it"
    units = instance.offering_info[(course_id, section_type)].units
    full = [p for p in eligible if loads[p.id] + units > p.load_max + 1e-9]
    if len(full) == len(eligible):
        names = ", ".join(f"{p.id} ({loads[p.id]:g}/{p.load_max:g})" for p in eligible)
        return f"eligible professors all at max load: {names}"
    free = ", ".join(p.id for p in eligible if p not in full)
    return (
        f"eligible professors with spare load ({free}) could not take it without breaking "
        "another rule (timetable capacity, pre-assignments or pins)"
    )
