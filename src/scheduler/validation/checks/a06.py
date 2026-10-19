"""A6 — Max distinct preparations."""

from __future__ import annotations

from scheduler.config import Config, ConstraintSettings
from scheduler.domain import Instance, Solution
from scheduler.validation.core import Violation, check, severity_for


@check("A6")
def check_a6(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """sum_c z_{p,c} <= preps_p for professors with preps_p set."""
    out = []
    for prof in instance.professors:
        if prof.max_preps is None:
            continue
        courses = sorted({a.course_id for a in solution.assignments if a.professor_id == prof.id})
        if len(courses) > prof.max_preps:
            out.append(
                Violation(
                    "A6",
                    severity_for(settings),
                    f"{prof.id} teaches {len(courses)} distinct courses ({', '.join(courses)}), "
                    f"more than {prof.max_preps}",
                    (prof.id,),
                    size=len(courses) - prof.max_preps,
                )
            )
    return out
