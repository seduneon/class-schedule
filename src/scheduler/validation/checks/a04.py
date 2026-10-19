"""A4 — Pre-assignments: n_{p,c,k} >= pre_{p,c,k}; pre-assigned labels stay with their professor."""

from __future__ import annotations

from collections import Counter

from scheduler.config import Config, ConstraintSettings
from scheduler.domain import Instance, Solution
from scheduler.validation.core import Violation, check, severity_for


@check("A4")
def check_a4(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """Count per (p, c, k) against pre-assignments; check explicit labels."""
    out: list[Violation] = []
    sev = severity_for(settings)
    counts = Counter((a.professor_id, a.course_id, a.section_type) for a in solution.assignments)
    for (pid, cid, k), need in sorted(
        instance.pre_assigned.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2].value)
    ):
        have = counts.get((pid, cid, k), 0)
        if have < need:
            out.append(
                Violation(
                    "A4",
                    sev,
                    f"{pid} was pre-assigned {need} {cid} {k.value} section(s) but has {have}",
                    (pid, cid, k.value),
                    size=need - have,
                )
            )
    owner = {a.section_key: a.professor_id for a in solution.assignments}
    for pa in instance.pre_assignments:
        for label in pa.section_labels:
            got = owner.get((pa.course_id, pa.section_type, label))
            if got != pa.professor_id:
                out.append(
                    Violation(
                        "A4",
                        sev,
                        f"{pa.course_id}-{label} is pre-assigned to {pa.professor_id} "
                        f"but assigned to {got or 'nobody'}",
                        (pa.professor_id, f"{pa.course_id}-{label}"),
                    )
                )
    return out
