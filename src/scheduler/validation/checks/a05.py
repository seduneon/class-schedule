"""A5 — Multi-section preference."""

from __future__ import annotations

from collections import Counter

from scheduler.config import Config, ConstraintSettings
from scheduler.domain import Instance, Solution
from scheduler.validation.core import Violation, check, severity_for


@check("A5")
def check_a5(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """mu_p = -1: sum_k n_{p,c,k} <= 1 per course. (mu_p = +1 is only an objective bonus.)"""
    per_course = Counter((a.professor_id, a.course_id) for a in solution.assignments)
    out = []
    for (pid, cid), n in sorted(per_course.items()):
        prof = instance.professor_by_id.get(pid)
        if prof is not None and prof.multi_section_pref == -1 and n > 1:
            out.append(
                Violation(
                    "A5",
                    severity_for(settings),
                    f"{pid} prefers one section per course but teaches {n} of {cid}",
                    (pid, cid),
                    size=n - 1,
                )
            )
    return out
