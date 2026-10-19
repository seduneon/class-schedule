"""A7 — Lecture–recitation staffing."""

from __future__ import annotations

from collections import Counter

from scheduler.config import Config, ConstraintSettings
from scheduler.derived import courses_with_lectures_and_recitations, recitation_band
from scheduler.domain import Instance, SectionType, Solution, is_placeholder, placeholder_for
from scheduler.validation.core import Violation, check, severity_for

L, R = SectionType.L, SectionType.R


@check("A7")
def check_a7(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """``faculty``: nothing beyond A1. ``external``: recitations go to TBA-<course> only.
    ``same_as_lecture``: floor(N_R share) <= n_{p,c,R} <= ceil(N_R share), share = n_{p,c,L} / N_L."""
    staffing = config.recitations.staffing
    sev = severity_for(settings)
    out: list[Violation] = []
    if staffing == "external":
        for a in solution.assignments:
            if a.section_type is R and a.professor_id != placeholder_for(a.course_id):
                out.append(
                    Violation(
                        "A7",
                        sev,
                        f"{a.course_id}-{a.section_label} is a recitation (external staffing) but "
                        f"is assigned to {a.professor_id}",
                        (a.professor_id, a.course_id),
                    )
                )
        return out
    if staffing != "same_as_lecture":
        return out
    counts = Counter(
        (a.professor_id, a.course_id, a.section_type)
        for a in solution.assignments
        if not is_placeholder(a.professor_id)
    )
    for c in courses_with_lectures_and_recitations(instance):
        n_l = instance.offering_info[(c, L)].num_sections
        n_r = instance.offering_info[(c, R)].num_sections
        profs = sorted({p for (p, cc, _k) in counts if cc == c})
        for p in profs:
            lo, hi = recitation_band(counts.get((p, c, L), 0), n_l, n_r)
            have = counts.get((p, c, R), 0)
            if not lo <= have <= hi:
                out.append(
                    Violation(
                        "A7",
                        sev,
                        f"{p} teaches {counts.get((p, c, L), 0)} of {n_l} {c} lectures and should take "
                        f"{lo}-{hi} of {n_r} recitations, but takes {have}",
                        (p, c),
                        size=max(lo - have, have - hi),
                    )
                )
    return out
