"""A10 — Top-k course preference: sections taught outside a professor's top K ranks."""

from __future__ import annotations

from scheduler.config import Config, ConstraintSettings
from scheduler.derived import outside_top_k
from scheduler.domain import Instance, Solution
from scheduler.validation.core import Violation, check, severity_for


@check("A10")
def check_a10(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """Flag (p, c, k) taught with rank rho^C_{p,c,k} > K, ``cannot`` or unranked, unless a
    pre-assignment/pin exempts it; size = sections taught."""
    out: list[Violation] = []
    triples = sorted(
        {(a.professor_id, a.course_id, a.section_type) for a in solution.assignments},
        key=lambda t: (t[0], t[1], t[2].value),
    )
    for pid, cid, k in triples:
        if pid not in instance.professor_by_id:
            continue
        reason = outside_top_k(instance, config, pid, cid, k)
        if reason is not None:
            n = sum(
                1
                for a in solution.assignments
                if (a.professor_id, a.course_id, a.section_type) == (pid, cid, k)
            )
            out.append(
                Violation(
                    "A10",
                    severity_for(settings),
                    f"{pid} teaches {cid} {k.value}: {reason}",
                    (pid, cid, k.value),
                    n,
                )
            )
    return out
