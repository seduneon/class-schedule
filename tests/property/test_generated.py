"""Property tests on generated instances (SPEC §12)."""

from __future__ import annotations

from typing import Any

import pulp
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from scheduler.config import Config, Mode
from scheduler.domain import Instance
from scheduler.generate import GeneratorSpec, generate_instance
from scheduler.model.stage_a.build import build_stage_a
from scheduler.pipeline import run_stage_a, run_stage_b
from scheduler.validation import validate

CFG = Config().with_updates(solver={"threads": 1, "time_limit_s": 30})

specs = st.builds(
    GeneratorSpec,
    n_professors=st.integers(2, 5),
    n_courses=st.integers(2, 5),
    max_lecture_sections=st.integers(1, 2),
    recitation_share=st.sampled_from([0.0, 0.5]),
    load_tightness=st.sampled_from([0.6, 1.0, 1.4]),
    preference_correlation=st.sampled_from([0.0, 0.5, 1.0]),
    seed=st.integers(0, 10_000),
)
SETTINGS = settings(max_examples=8, deadline=None, suppress_health_check=[HealthCheck.too_slow])


def _hard_errors(inst: Instance, sol: Any, cfg: Config) -> list[str]:
    hard = [
        cid for cid, s in cfg.constraints.items() if s.mode is Mode.HARD and cid not in ("A1", "B1")
    ]
    return [str(v) for v in validate(inst, sol, cfg, ids=hard) if v.severity == "error"]


@SETTINGS
@given(specs)
def test_hard_constraints_hold_on_generated_instances(spec: GeneratorSpec) -> None:
    inst = generate_instance(spec)
    a = run_stage_a(inst, CFG, presolve=False)
    assert a.solution is not None
    assert _hard_errors(inst, a.solution, CFG) == []
    b = run_stage_b(inst, CFG, a.solution.assignments, presolve=False)
    assert b.solution is not None
    assert _hard_errors(inst, b.solution, CFG) == []


@SETTINGS
@given(specs)
def test_same_seed_same_solution(spec: GeneratorSpec) -> None:
    first = run_stage_a(generate_instance(spec), CFG, presolve=False).solution
    second = run_stage_a(generate_instance(spec), CFG, presolve=False).solution
    assert first is not None and second is not None
    assert first.assignments == second.assignments


@settings(max_examples=6, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    specs.map(lambda s: GeneratorSpec(**{**s.__dict__, "load_tightness": 0.5, "cannot_rate": 0.0}))
)
def test_coverage_matches_lp_bound_when_coverable(spec: GeneratorSpec) -> None:
    """Level-1 (uncovered sections) of the MIP equals the LP-relaxation bound, rounded up."""
    inst = generate_instance(spec)
    cfg = CFG.with_mode("A8", "off")  # alpha_p is integral information the LP cannot see
    mip = run_stage_a(inst, cfg, presolve=False).objective(1)
    ctx = build_stage_a(inst, cfg)
    ctx.prob.setObjective(ctx.level_expr(1))
    ctx.prob.sense = pulp.LpMinimize
    stats = ctx.prob.solve(pulp.COIN_CMD(msg=False, mip=False))  # LP relaxation
    assert stats.status == 1
    lp = pulp.value(ctx.prob.objective) or 0.0
    assert mip >= lp - 1e-6
    if lp <= 1e-6:
        assert mip == 0
