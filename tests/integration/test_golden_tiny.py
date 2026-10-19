"""Golden test on the tiny example (SPEC §12), with hand-computed optima.

Stage A, linear weights (SPEC §3.4):
  A: 161 -> 1, 351 -> 1/2          B: 351 -> 1, 361 -> 2/3, 161 -> 1/3      C: 361 -> 1, 161 -> 1/2
  Unranked courses are forbidden (A3). Loads: A [1, 2], B [1, 2], C [1, 1].
  Optimum: A takes MATH161 x2, B MATH351, C MATH361. Every section is covered (level 1 = 0),
  every load is within range (level 2 = 0) and
    sat^C = A: 2*1/2 = 1,  B: 1/2,  C: 1/1 = 1  ->  sum = 2.5
  The runner-up (B takes 351+361, A and C one 161 each) scores 0.5 + 5/6 + 0.5 = 1.83.
"""

from __future__ import annotations

import pytest

from scheduler.config import Config
from scheduler.domain import Instance
from scheduler.pipeline import run_stage_a, run_stage_b
from tests.factory import fast_config, tiny_assignments


def test_golden_stage_a_without_fairness(tiny: Instance) -> None:
    result = run_stage_a(tiny, fast_config().with_mode("A9", "off"))
    assert result.status.value == "optimal"
    assert result.objective(1) == pytest.approx(0)
    assert result.objective(2) == pytest.approx(0)
    assert result.objective(3) == pytest.approx(2.5)
    assert result.solution is not None
    assert set(result.solution.assignments) == set(tiny_assignments(tiny))
    assert result.violations == []


# Stage B, linear time weights:
#   A: MWF0900 -> 1, MWF1000 -> 1/2          (two MATH161 sections, 40 seats -> room 7.101)
#   B: TR0900 -> 1, TR1030 -> 2/3, MWF1000 -> 1/3      (MATH351)
#   C: TR0900 -> 1, MWF0900 -> 1/2                      (MATH361)
# MATH351 and MATH361 share the level_300 conflict group, so B and C cannot both get TR0900.
#   option 1: B TR0900, C MWF0900 -> 1 + 1/2 = 1.5
#   option 2: B TR1030, C TR0900  -> 2/3 + 1 = 1.667   (best)
# A gets MWF0900 + MWF1000 (B3 forbids both at 9am): sat = (1 + 1/2)/2 = 3/4.
# Level 3 = 3/4 + 2/3 + 1 = 29/12.


def test_golden_stage_b_without_fairness(tiny: Instance) -> None:
    cfg = fast_config().with_mode("B12", "off")
    result = run_stage_b(tiny, cfg, tiny_assignments(tiny))
    assert result.status.value == "optimal"
    assert result.objective(1) == pytest.approx(0)
    assert result.objective(2) == pytest.approx(0)
    assert result.objective(3) == pytest.approx(29 / 12)
    assert result.solution is not None and result.solution.placements is not None
    times = {(p.course_id, p.pattern_id) for p in result.solution.placements}
    assert times == {
        ("MATH161", "MWF0900"),
        ("MATH161", "MWF1000"),
        ("MATH351", "TR1030"),
        ("MATH361", "TR0900"),
    }
    assert all(p.room_id == "7.101" for p in result.solution.placements if p.course_id == "MATH161")
    assert result.violations == []


# With the default config, fairness (A9, B12) adds lambda * min satisfaction (lambda = 0.5):
#   Stage A: min(sat^C) over professors with load_min > 0 = min(1, 1/2, 1) = 1/2
#            level 3 = 2.5 + 0.5 * 1/2 = 2.75     (the runner-up: 1.83 + 0.5 * 1/2 = 2.08)
#   Stage B: min(sat^T) = min(3/4, 2/3, 1) = 2/3
#            level 3 = 29/12 + 0.5 * 2/3 = 2.75   (option 1: 2.25 + 0.5 * 1/2 = 2.5)
# No other default rule binds (no multi-section dislikes, preps, max days or styles; the two
# MATH161 sections are already spread), so levels 1 and 2 stay 0.


def test_golden_default_config(tiny: Instance, default_config: Config) -> None:
    cfg = default_config.with_updates(solver={"threads": 1})
    a = run_stage_a(tiny, cfg)
    assert [a.objective(k) for k in (1, 2)] == [pytest.approx(0), pytest.approx(0)]
    assert a.objective(3) == pytest.approx(2.75)
    assert a.solution is not None and set(a.solution.assignments) == set(tiny_assignments(tiny))
    b = run_stage_b(tiny, cfg, a.solution.assignments)
    assert [b.objective(k) for k in (1, 2)] == [pytest.approx(0), pytest.approx(0)]
    assert b.objective(3) == pytest.approx(2.75)
    assert b.violations == [] and b.slacks == [] and a.findings == []


def test_golden_is_deterministic(tiny: Instance) -> None:
    runs = [run_stage_b(tiny, fast_config(), tiny_assignments(tiny)).solution for _ in range(2)]
    assert runs[0] is not None and runs[1] is not None
    assert runs[0].placements == runs[1].placements
