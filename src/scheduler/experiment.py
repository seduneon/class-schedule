"""Reproducible experiments for the capstone report (SPEC §13 M10).

Every experiment returns a list of flat row dicts (written as CSV by the caller) and is
deterministic for a given list of seeds.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import Any

from scheduler.config import Config, Mode
from scheduler.domain import Instance, Solution
from scheduler.generate import GeneratorSpec, generate_instance
from scheduler.metrics import professor_metrics, summarize
from scheduler.pipeline import StageResult, run_stage_a, run_stage_b
from scheduler.validation import validate

Row = dict[str, Any]

ABLATION_IDS = ("A5", "A6", "A8", "A9", "B5", "B6", "B7", "B8", "B9", "B12")


def _both_stages(inst: Instance, cfg: Config) -> tuple[StageResult, StageResult | None, float]:
    t0 = time.perf_counter()
    a = run_stage_a(inst, cfg, presolve=False)
    b = None
    if a.solution is not None:
        b = run_stage_b(inst, cfg, a.solution.assignments, presolve=False)
    return a, b, time.perf_counter() - t0


def _levels(prefix: str, result: StageResult | None) -> Row:
    if result is None:
        return {}
    return {f"{prefix}_{lv.level.name}": round(lv.value, 6) for lv in result.lex.levels}


def ablation(seeds: Sequence[int], config: Config, spec: GeneratorSpec | None = None) -> list[Row]:
    """Each should-constraint switched off vs its default mode; violations counted with the
    default config, so "off" shows what the rule prevents."""
    spec = spec or GeneratorSpec(n_professors=8, n_courses=8)
    rows: list[Row] = []
    for seed in seeds:
        inst = generate_instance(replace(spec, seed=seed))
        for cid in ("baseline", *ABLATION_IDS):
            cfg = config if cid == "baseline" else config.with_mode(cid, Mode.OFF)
            a, b, wall = _both_stages(inst, cfg)
            final = b.solution if b and b.solution else a.solution
            vs = validate(inst, final, config) if final else []
            rows.append(
                {
                    "seed": seed,
                    "switched_off": cid,
                    "violations": len(vs),
                    "violations_of_id": sum(1 for v in vs if v.id == cid),
                    "wall_s": round(wall, 3),
                    **_levels("A", a),
                    **_levels("B", b),
                }
            )
    return rows


def scaling(sizes: Sequence[int], seeds: Sequence[int], config: Config) -> list[Row]:
    """Solve time and model size vs instance size (n professors = n courses)."""
    rows: list[Row] = []
    for n in sizes:
        for seed in seeds:
            inst = generate_instance(GeneratorSpec(n_professors=n, n_courses=n, seed=seed))
            a, b, wall = _both_stages(inst, config)
            rows.append(
                {
                    "size": n,
                    "seed": seed,
                    "sections": len(inst.sections),
                    "A_variables": a.stats.get("variables"),
                    "A_constraints": a.stats.get("constraints"),
                    "A_wall_s": a.stats.get("wall_time_s"),
                    "B_variables": b.stats.get("variables") if b else None,
                    "B_constraints": b.stats.get("constraints") if b else None,
                    "B_wall_s": b.stats.get("wall_time_s") if b else None,
                    "total_wall_s": round(wall, 3),
                    "A_status": a.status.value,
                    "B_status": b.status.value if b else None,
                }
            )
    return rows


def _rank_stats(inst: Instance, sol: Solution, cfg: Config) -> Row:
    ranks = [r for m in professor_metrics(inst, sol, cfg) for r in m.course_ranks]
    ranked = [r for r in ranks if r is not None]
    s = summarize(inst, sol, cfg)
    return {
        "mean_course_rank": round(sum(ranked) / len(ranked), 4) if ranked else None,
        "share_first_choice": round(sum(1 for r in ranked if r == 1) / len(ranks), 4)
        if ranks
        else None,
        "share_unranked": round(sum(1 for r in ranks if r is None) / len(ranks), 4)
        if ranks
        else None,
        "min_sat_course": s.min_sat_course,
    }


def weight_strategies(seeds: Sequence[int], config: Config) -> list[Row]:
    """linear vs exponential vs top_k: which ranks professors actually receive."""
    rows: list[Row] = []
    variants: list[tuple[str, dict[str, Any]]] = [
        ("linear", {"strategy": "linear"}),
        ("exponential_0.5", {"strategy": "exponential", "beta": 0.5}),
        ("exponential_0.8", {"strategy": "exponential", "beta": 0.8}),
        ("top_1", {"strategy": "top_k", "top_k": 1}),
        ("top_3", {"strategy": "top_k", "top_k": 3}),
    ]
    for seed in seeds:
        inst = generate_instance(GeneratorSpec(n_professors=8, n_courses=8, seed=seed))
        for name, prefs in variants:
            cfg = config.with_updates(preferences=prefs)
            a = run_stage_a(inst, cfg, presolve=False)
            if a.solution is None:
                continue
            rows.append({"seed": seed, "strategy": name, **_rank_stats(inst, a.solution, config)})
    return rows


def fairness(lambdas: Sequence[float], seeds: Sequence[int], config: Config) -> list[Row]:
    """Total vs minimum satisfaction as the fairness weight lambda grows (A9, B12)."""
    rows: list[Row] = []
    for seed in seeds:
        inst = generate_instance(
            GeneratorSpec(n_professors=8, n_courses=8, seed=seed, preference_correlation=0.9)
        )
        for lam in lambdas:
            cfg = config.with_updates(
                objective={"lambda_course_fairness": lam, "lambda_time_fairness": lam}
            )
            a, b, _ = _both_stages(inst, cfg)
            final = b.solution if b and b.solution else a.solution
            if final is None:
                continue
            s = summarize(inst, final, cfg)
            rows.append(
                {
                    "seed": seed,
                    "lambda": lam,
                    "total_sat_course": round(s.total_sat_course, 4),
                    "min_sat_course": s.min_sat_course,
                    "total_sat_time": s.total_sat_time,
                    "min_sat_time": s.min_sat_time,
                }
            )
    return rows


MUST_ONLY = ("A5", "A6", "A7", "A8", "A9", "B6", "B7", "B8", "B9", "B10", "B11", "B12")


def decomposition(
    seeds: Sequence[int], config: Config, sizes: Sequence[int] = (4, 6, 8)
) -> list[Row]:
    """L7: cost of the two-stage decomposition vs the integrated model (must-rules only),
    both scored with the integrated level-3 expression (:func:`proxy_objective`)."""
    from scheduler.model.integrated import proxy_objective
    from scheduler.pipeline import run_integrated

    cfg = config
    for cid in MUST_ONLY:
        cfg = cfg.with_mode(cid, Mode.OFF)
    rows: list[Row] = []
    for n in sizes:
        for seed in seeds:
            inst = generate_instance(GeneratorSpec(n_professors=n, n_courses=n, seed=seed))
            t0 = time.perf_counter()
            integ = run_integrated(inst, cfg)
            t_int = time.perf_counter() - t0
            _a, b, t_two = _both_stages(inst, cfg)
            two = b.solution if b and b.solution else None
            if integ.solution is None or two is None or b is None:
                continue
            scheduled_two = len(two.placements or ())
            scheduled_int = len(integ.solution.placements or ())
            p_int = proxy_objective(inst, integ.solution, cfg)
            p_two = proxy_objective(inst, two, cfg)
            rows.append(
                {
                    "size": n,
                    "seed": seed,
                    "sections": len(inst.sections),
                    "scheduled_integrated": scheduled_int,
                    "scheduled_two_stage": scheduled_two,
                    "proxy_integrated": round(p_int, 6),
                    "proxy_two_stage": round(p_two, 6),
                    "relative_gap": round((p_int - p_two) / p_int, 6) if p_int > 0 else 0.0,
                    "time_integrated_s": round(t_int, 3),
                    "time_two_stage_s": round(t_two, 3),
                }
            )
    return rows


EXPERIMENTS: dict[str, Callable[[Config, Sequence[int]], list[Row]]] = {
    "ablation": lambda cfg, seeds: ablation(seeds, cfg),
    "scaling": lambda cfg, seeds: scaling((5, 10, 15, 20, 30), seeds, cfg),
    "weights": lambda cfg, seeds: weight_strategies(seeds, cfg),
    "fairness": lambda cfg, seeds: fairness((0.0, 0.25, 0.5, 1.0, 2.0, 4.0), seeds, cfg),
    "decomposition": lambda cfg, seeds: decomposition(seeds, cfg),
}
