"""A3 — Eligibility: nobody teaches a course they cannot (or, under ``forbid``, did not rank)."""

from __future__ import annotations

from scheduler.config import Config, ConstraintSettings
from scheduler.derived import ineligibility_reason, is_overridden
from scheduler.domain import Instance, Solution
from scheduler.validation.core import Violation, check, severity_for


@check("A3")
def check_a3(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """Flag assignments of (p, c, k) with p ineligible for (c, k), unless a
    pre-assignment/pin overrides."""
    out: list[Violation] = []
    triples = sorted(
        {(a.professor_id, a.course_id, a.section_type) for a in solution.assignments},
        key=lambda t: (t[0], t[1], t[2].value),
    )
    for pid, cid, k in triples:
        if pid not in instance.professor_by_id or is_overridden(instance, pid, cid, k):
            continue
        reason = ineligibility_reason(instance, config, pid, cid, k)
        if reason is not None:
            n = sum(
                1
                for a in solution.assignments
                if (a.professor_id, a.course_id, a.section_type) == (pid, cid, k)
            )
            out.append(
                Violation(
                    "A3",
                    severity_for(settings),
                    f"{pid} teaches {cid} {k.value}: {reason}",
                    (pid, cid, k.value),
                    n,
                )
            )
    return out
