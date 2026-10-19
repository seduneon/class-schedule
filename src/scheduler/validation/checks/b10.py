"""B10 — Max consecutive teaching."""

from __future__ import annotations

from collections import defaultdict

from scheduler.config import B10Settings, Config, ConstraintSettings
from scheduler.domain import Instance, Solution
from scheduler.time import consecutive_chains
from scheduler.validation.core import Violation, check, severity_for
from scheduler.validation.view import placed_sections


@check("B10")
def check_b10(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """No professor teaches a chain t_1 -> ... -> t_{k+1} of adjacent patterns on one day
    (sum_i busy_{p,t_i} <= k, k = ``max_consecutive``)."""
    k = settings.max_consecutive if isinstance(settings, B10Settings) else 3
    taught: dict[str, dict[str, object]] = defaultdict(dict)
    for x in placed_sections(instance, solution):
        if not x.section.placeholder:
            taught[x.professor_id][x.pattern.id] = x.pattern
    out = []
    for pid in sorted(taught):
        pats = [instance.pattern_by_id[t] for t in sorted(taught[pid])]
        for chain in consecutive_chains(pats, config.time.adjacency_gap_minutes, k + 1):
            out.append(
                Violation(
                    "B10",
                    severity_for(settings),
                    f"{pid} teaches {k + 1} back-to-back patterns ({' -> '.join(chain)}), more than {k}",
                    (pid, *chain),
                )
            )
    return out
