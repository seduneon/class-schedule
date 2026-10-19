"""A1 — Section coverage: every section of every (c, k) is assigned exactly once."""

from __future__ import annotations

from collections import Counter

from scheduler.config import Config, ConstraintSettings
from scheduler.derived import stage_a_offering_keys
from scheduler.domain import Instance, Solution, is_placeholder
from scheduler.validation.core import Violation, check, severity_for


@check("A1")
def check_a1(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """sum_p n_{p,c,k} = N_{c,k}: count distinct valid labels per (c, k); flag unknown/duplicate
    labels and sections given to an unknown professor (TBA placeholders allowed)."""
    out: list[Violation] = []
    for a in solution.assignments:
        if not is_placeholder(a.professor_id) and a.professor_id not in instance.professor_by_id:
            sid = f"{a.course_id}-{a.section_label}"
            out.append(
                Violation(
                    "A1",
                    "error",
                    f"{sid} is assigned to unknown professor {a.professor_id!r}",
                    (sid, a.professor_id),
                )
            )
    counts = Counter(a.section_key for a in solution.assignments)
    for key, n in sorted(counts.items(), key=lambda kv: (kv[0][0], kv[0][1].value, kv[0][2])):
        sid = f"{key[0]}-{key[2]}"
        if key not in instance.section_by_key:
            out.append(Violation("A1", "error", f"{sid}: no such section in the offerings", (sid,)))
        elif n > 1:
            out.append(Violation("A1", "error", f"{sid} is assigned {n} times", (sid,), size=n - 1))
    sev = severity_for(settings)
    for c, k in stage_a_offering_keys(instance, config):
        info = instance.offering_info[(c, k)]
        covered = sum(
            1
            for (cc, kk, _l) in counts
            if cc == c and kk == k and (cc, kk, _l) in instance.section_by_key
        )
        missing = info.num_sections - covered
        if missing > 0:
            out.append(
                Violation(
                    "A1",
                    sev,
                    f"{c} {k.value}: {missing} of {info.num_sections} section(s) uncovered",
                    (c, k.value),
                    size=missing,
                )
            )
    return out
