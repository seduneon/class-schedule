"""A9 — Course satisfaction fairness."""

from __future__ import annotations

from scheduler.config import Config, ConstraintSettings
from scheduler.domain import Instance, Solution
from scheduler.metrics import professor_metrics
from scheduler.validation.core import Violation, check

EPS = 1e-9


@check("A9")
def check_a9(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """A9 is an objective term (reward lambda^C m^C with m^C <= sat^C_p), so it cannot be
    "violated" as such. The check reports the unfair extreme it guards against: a professor
    with load_min > 0 whose course satisfaction sat^C_p is 0 (nothing they ranked).
    Always a warning."""
    out = []
    for m in professor_metrics(instance, solution, config):
        prof = instance.professor_by_id[m.professor_id]
        if prof.load_min > 0 and m.sat_course is not None and m.sat_course <= EPS:
            out.append(
                Violation(
                    "A9",
                    "warning",
                    f"{m.professor_id} got none of their preferred courses (course satisfaction 0)",
                    (m.professor_id,),
                )
            )
    return out
