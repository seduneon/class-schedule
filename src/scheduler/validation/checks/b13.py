"""B13 — Day-family preference."""

from __future__ import annotations

from collections import defaultdict

from scheduler.config import Config, ConstraintSettings
from scheduler.derived import family_mixing, off_family
from scheduler.domain import FamilyMixing, Instance, Solution
from scheduler.validation.core import Violation, check, severity_for
from scheduler.validation.view import placed_sections


@check("B13")
def check_b13(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """Per professor: sections whose family f(t) is outside Phi_p, and families used beyond
    one when chi_p is ``avoid`` (severity of the mode) or ``forbid`` (always an error)."""
    off: dict[str, list[str]] = defaultdict(list)
    families: dict[str, set[str]] = defaultdict(set)
    for x in placed_sections(instance, solution):
        if off_family(instance, x.professor_id, x.pattern.id):
            off[x.professor_id].append(x.label)
        families[x.professor_id].add(x.pattern.family)
    out: list[Violation] = []
    for pid in sorted(off):
        prefs = ";".join(sorted(instance.professor_by_id[pid].day_families))
        out.append(
            Violation(
                "B13",
                severity_for(settings),
                f"{pid} teaches {', '.join(off[pid])} outside preferred days {prefs}",
                (pid,),
                size=len(off[pid]),
            )
        )
    for pid in sorted(families):
        used = families[pid]
        mixing = family_mixing(instance, config, pid)
        if len(used) <= 1 or mixing is FamilyMixing.ALLOW:
            continue
        out.append(
            Violation(
                "B13",
                "error" if mixing is FamilyMixing.FORBID else severity_for(settings),
                f"{pid} mixes day families {' and '.join(sorted(used))}",
                (pid,),
                size=len(used) - 1,
            )
        )
    return out
