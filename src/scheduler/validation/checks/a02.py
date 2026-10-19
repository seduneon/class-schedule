"""A2 — Teaching load range: L_min_p <= sum u n <= L_max_p."""

from __future__ import annotations

from scheduler.config import A2Settings, Config, ConstraintSettings
from scheduler.domain import Instance, Solution
from scheduler.validation.core import Violation, check, severity_for

EPS = 1e-9


def professor_loads(instance: Instance, solution: Solution) -> dict[str, float]:
    """Units taught per professor (placeholders excluded)."""
    loads = dict.fromkeys(instance.professor_ids, 0.0)
    for a in solution.assignments:
        if a.professor_id in loads:
            loads[a.professor_id] += a.units
    return loads


@check("A2")
def check_a2(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """Underload and overload per professor. Overload is an error unless soft with allow_overload."""
    out: list[Violation] = []
    sev = severity_for(settings)
    allow_over = isinstance(settings, A2Settings) and settings.allow_overload
    for pid, load in professor_loads(instance, solution).items():
        prof = instance.professor_by_id[pid]
        if load < prof.load_min - EPS:
            out.append(
                Violation(
                    "A2",
                    sev,
                    f"{pid} teaches {load:g} units, below the minimum {prof.load_min:g}",
                    (pid,),
                    size=prof.load_min - load,
                )
            )
        if load > prof.load_max + EPS:
            out.append(
                Violation(
                    "A2",
                    sev if allow_over else "error",
                    f"{pid} teaches {load:g} units, above the maximum {prof.load_max:g}",
                    (pid,),
                    size=load - prof.load_max,
                )
            )
    return out
