"""B8 — Max teaching days."""

from __future__ import annotations

from collections import defaultdict

from scheduler.config import Config, ConstraintSettings
from scheduler.domain import DAYS, Instance, Solution
from scheduler.validation.core import Violation, check, severity_for
from scheduler.validation.view import placed_sections


@check("B8")
def check_b8(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """sum_d day_{p,d} <= days_p for professors with a maximum."""
    days: dict[str, set[str]] = defaultdict(set)
    for x in placed_sections(instance, solution):
        days[x.professor_id].update(x.pattern.days)
    out = []
    for prof in instance.professors:
        used = days.get(prof.id, set())
        if prof.max_days is not None and len(used) > prof.max_days:
            ordered = [d for d in DAYS if d in used]
            out.append(
                Violation(
                    "B8",
                    severity_for(settings),
                    f"{prof.id} teaches on {len(used)} days ({' '.join(ordered)}), more than {prof.max_days}",
                    (prof.id,),
                    size=len(used) - prof.max_days,
                )
            )
    return out
