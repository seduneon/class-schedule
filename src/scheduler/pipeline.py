"""Library entry points: run_stage_a / run_stage_b / run_integrated (SPEC §10)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from scheduler.config import Config
from scheduler.diagnostics.postsolve import SlackReport, explain_uncovered
from scheduler.diagnostics.presolve import Finding, presolve_checks
from scheduler.domain import Assignment, Instance, SectionType, Solution
from scheduler.model.context import LEVEL_SATISFACTION, ModelContext
from scheduler.solve.alternatives import Alternative, find_alternatives
from scheduler.solve.backend import SolveStatus
from scheduler.solve.lexicographic import LexResult, solve_lexicographic
from scheduler.solve.repair import add_repair_level
from scheduler.validation import Violation, check_pins, validate

SLACK_EPS = 1e-6


@dataclass
class StageResult:
    """Outcome of one stage: solution (if any), objective levels, findings and violations."""

    stage: str
    status: SolveStatus
    solution: Solution | None
    lex: LexResult
    findings: list[Finding] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)
    slacks: list[SlackReport] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    ctx: ModelContext | None = field(default=None, repr=False)

    @property
    def ok(self) -> bool:
        return self.status.has_solution and not any(v.severity == "error" for v in self.violations)

    def objective(self, level: int) -> float:
        return self.lex.value(level)


def slack_reports(ctx: ModelContext) -> list[SlackReport]:
    """Every slack with a value above SLACK_EPS."""
    out: list[SlackReport] = []
    for rec in ctx.slacks:
        value = ctx.value(rec.var)
        if value > SLACK_EPS:
            out.append(SlackReport(rec.cid, rec.entities, rec.description, round(value, 6)))
    return out


def _stats(ctx: ModelContext, lex: LexResult) -> dict[str, Any]:
    return {
        "variables": ctx.num_variables,
        "constraints": ctx.num_constraints,
        "wall_time_s": round(lex.wall_time_s, 3),
        "levels": [lv.as_dict() for lv in lex.levels],
    }


def _meta(stage: str, lex: LexResult) -> dict[str, object]:
    return {
        "stage": stage,
        "status": lex.status.value,
        "objectives": {lv.level.name: lv.value for lv in lex.levels},
    }


# ----- Stage A ------------------------------------------------------------------------


def extract_stage_a(ctx: ModelContext) -> Solution:
    """Labeled assignments from the current Stage A variable values."""
    from scheduler.model.stage_a.build import extract_counts
    from scheduler.model.stage_a.labels import attach_labels, external_assignments

    assignments = attach_labels(ctx.instance, extract_counts(ctx)) + external_assignments(
        ctx.instance, ctx.config
    )
    return Solution(assignments, None)


def run_stage_a(
    instance: Instance,
    config: Config,
    *,
    presolve: bool = True,
    previous: Solution | None = None,
) -> StageResult:
    """Build, solve lexicographically, attach labels, validate (SPEC §5).

    With ``previous`` (L5 repair), changes in z are minimized right after coverage.
    """
    from scheduler.model.stage_a.build import build_stage_a

    findings = presolve_checks(instance, config) if presolve else []
    ctx = build_stage_a(instance, config)
    if previous is not None:
        add_repair_level(ctx, previous)
    lex = solve_lexicographic(ctx, config.solver)
    result = StageResult("A", lex.status, None, lex, findings, ctx=ctx, stats=_stats(ctx, lex))
    if not lex.status.has_solution:
        return result
    base = extract_stage_a(ctx)
    solution = Solution(base.assignments, None, _meta("A", lex))
    result.solution = solution
    result.violations = validate(instance, solution, config) + check_pins(instance, solution)
    result.slacks = _explain_a(instance, config, slack_reports(ctx), solution.assignments)
    return result


def _explain_a(
    instance: Instance,
    config: Config,
    reports: list[SlackReport],
    assignments: Sequence[Assignment],
) -> list[SlackReport]:
    out = []
    for r in reports:
        if r.cid == "A1":
            c, k = r.entities
            why = explain_uncovered(instance, config, c, SectionType(k), assignments)
            out.append(SlackReport(r.cid, r.entities, r.description, r.value, why))
        else:
            out.append(r)
    return out


# ----- Stage B ------------------------------------------------------------------------


def extract_stage_b(ctx: ModelContext) -> Solution:
    """Placements from the current Stage B variable values."""
    from scheduler.model.stage_b.build import extract_placements

    assignments = tuple(ctx.data["assignments"])
    return Solution(assignments, extract_placements(ctx))


def run_stage_b(
    instance: Instance,
    config: Config,
    assignments: Sequence[Assignment],
    *,
    presolve: bool = True,
    previous: Solution | None = None,
) -> StageResult:
    """Timetable the assigned sections: build, solve lexicographically, validate (SPEC §6).

    With ``previous`` (L5 repair), moved sections are minimized right after coverage.
    """
    from scheduler.model.stage_b.build import build_stage_b
    from scheduler.model.stage_b.variables import by_section

    findings = presolve_checks(instance, config, assignments) if presolve else []
    ctx = build_stage_b(instance, config, assignments)
    ctx.data["assignments"] = tuple(assignments)
    if previous is not None:
        add_repair_level(ctx, previous)
    lex = solve_lexicographic(ctx, config.solver)
    result = StageResult("B", lex.status, None, lex, findings, ctx=ctx, stats=_stats(ctx, lex))
    if not lex.status.has_solution:
        return result
    base = extract_stage_b(ctx)
    solution = Solution(base.assignments, base.placements, _meta("B", lex))
    result.solution = solution
    result.violations = validate(instance, solution, config) + check_pins(instance, solution)
    candidates = by_section(ctx)
    reports = []
    for r in slack_reports(ctx):
        if r.cid == "B1":
            key = next(sb.key for sb in ctx.data["sections"] if sb.id == r.entities[0])
            why = (
                "no feasible (pattern, room): check room sizes and types, allowed section "
                "types, blocked slots and unavailability"
                if not candidates[key]
                else f"all {len(candidates[key])} feasible (pattern, room) choices clash with "
                "other sections of the professor, the rooms or a conflict group"
            )
            r = SlackReport(r.cid, r.entities, r.description, r.value, why)
        reports.append(r)
    result.slacks = reports
    return result


# ----- L3 alternatives --------------------------------------------------------------------


def alternatives(
    result: StageResult, config: Config, count: int | None = None
) -> list[Alternative]:
    """L3: alternatives to a solved stage (reuses and then modifies ``result.ctx``)."""
    if result.ctx is None or result.solution is None:
        raise ValueError("alternatives need a solved stage result")
    extract = extract_stage_a if result.stage == "A" else extract_stage_b
    return find_alternatives(
        result.ctx,
        result.solution,
        result.objective(LEVEL_SATISFACTION),
        extract,
        config,
        count,
    )


# ----- L7 integrated mode --------------------------------------------------------------


def run_integrated(instance: Instance, config: Config) -> StageResult:
    """L7: one model for professors, times and rooms (must-rules only; experiments)."""
    from scheduler.model.integrated import build_integrated, extract_integrated

    ctx = build_integrated(instance, config)
    lex = solve_lexicographic(ctx, config.solver)
    result = StageResult("integrated", lex.status, None, lex, ctx=ctx, stats=_stats(ctx, lex))
    if lex.status.has_solution:
        base = extract_integrated(ctx)
        result.solution = Solution(base.assignments, base.placements, _meta("integrated", lex))
        result.slacks = slack_reports(ctx)
    return result
