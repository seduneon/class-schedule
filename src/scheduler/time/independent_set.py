"""alpha_p: maximum number of pairwise non-overlapping patterns (A8, L1).

Kept out of ``scheduler.time.__init__`` because it imports PuLP and
``scheduler.validation`` (which uses the time engine) must never import PuLP.
"""

from __future__ import annotations

from collections.abc import Sequence

import pulp

from scheduler.config import SolverConfig
from scheduler.domain import Instance, TimePattern
from scheduler.solve.backend import SolveStatus, solve
from scheduler.time.availability import professor_patterns
from scheduler.time.overlap import overlap_cliques

_SOLVER = SolverConfig(threads=1, time_limit_s=60)


def max_independent_patterns(patterns: Sequence[TimePattern], buffer: int = 0) -> int:
    """Size of a maximum independent set in the overlap graph.

    max sum_t x_t  s.t.  sum_{t in Q} x_t <= 1 for every clique Q, x binary.
    The clique cover is exact because every overlapping pair shares a clique.
    """
    if not patterns:
        return 0
    cliques = [q for q in overlap_cliques(patterns, buffer) if len(q) > 1]
    if not cliques:
        return len(patterns)
    prob = pulp.LpProblem("alpha", pulp.LpMaximize)
    x = {
        t.id: prob.add_variable(f"x_{i}", cat="Binary")
        for i, t in enumerate(sorted(patterns, key=lambda t: t.id))
    }
    prob.setObjective(pulp.lpSum(x.values()))
    for i, q in enumerate(cliques):
        prob += (pulp.lpSum(x[t] for t in sorted(q)) <= 1, f"clique_{i}")
    result = solve(prob, _SOLVER)
    if result.status is not SolveStatus.OPTIMAL or result.objective is None:
        raise RuntimeError(f"independent-set MIP ended with status {result.status}")
    return round(result.objective)


def alpha(instance: Instance, professor_id: str, days: Sequence[str], buffer: int) -> int:
    """alpha_p for professor ``p`` on its available patterns (cached per pattern set)."""
    patterns = professor_patterns(instance, professor_id, days)
    key = ("alpha", frozenset(t.id for t in patterns), buffer)
    return instance.memo(key, lambda: max_independent_patterns(patterns, buffer))
