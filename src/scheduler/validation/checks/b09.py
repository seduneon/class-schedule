"""B9 — Back-to-back preference."""

from __future__ import annotations

from collections import defaultdict

from scheduler.config import Config, ConstraintSettings
from scheduler.domain import Instance, ScheduleStyle, Solution
from scheduler.time import adjacency
from scheduler.validation.core import Violation, check, severity_for
from scheduler.validation.view import placed_sections


@check("B9")
def check_b9(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """``spread`` professors: busy_{p,t} + busy_{p,t'} <= 1 for adjacent (t, t').
    (``compact`` is only an objective reward and cannot be violated.)"""
    patterns: dict[str, set[str]] = defaultdict(set)
    for x in placed_sections(instance, solution):
        patterns[x.professor_id].add(x.pattern.id)
    pairs = sorted(
        {(p.first, p.second) for p in adjacency(instance, config.time.adjacency_gap_minutes)}
    )
    out = []
    for prof in instance.professors:
        if prof.schedule_style is not ScheduleStyle.SPREAD:
            continue
        mine = patterns.get(prof.id, set())
        for t, u in pairs:
            if t in mine and u in mine:
                out.append(
                    Violation(
                        "B9",
                        severity_for(settings),
                        f"{prof.id} prefers spread-out teaching but has back-to-back {t} -> {u}",
                        (prof.id, t, u),
                    )
                )
    return out
