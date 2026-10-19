"""Assemble the Stage B model and read its solution."""

from __future__ import annotations

from collections.abc import Sequence

from scheduler.config import Config, Stage
from scheduler.derived import stage_b_sections
from scheduler.domain import Assignment, Instance, Placement
from scheduler.model.context import ModelContext
from scheduler.model.registry import builders_for
from scheduler.model.stage_b import constraints as _constraints  # noqa: F401  (registers builders)
from scheduler.model.stage_b.objective import add_satisfaction_terms, stage_b_levels
from scheduler.model.stage_b.variables import build_variables, triples, y


def build_stage_b(
    instance: Instance, config: Config, assignments: Sequence[Assignment]
) -> ModelContext:
    """Variables over F, every enabled Stage B constraint, and the level-3 terms."""
    ctx = ModelContext("stage_b", instance, config, Stage.B, stage_b_levels(config))
    build_variables(ctx, stage_b_sections(instance, assignments))
    for builder in builders_for(Stage.B):
        if config.enabled(builder.id):
            builder().build(ctx, config.settings(builder.id))
    add_satisfaction_terms(ctx)
    return ctx


def extract_placements(ctx: ModelContext) -> tuple[Placement, ...]:
    """Placements with y_{s,t,r} = 1."""
    out = []
    for tr in triples(ctx):
        if ctx.value(y(ctx, tr)) > 0.5:
            c, k, label = tr.section.key
            out.append(Placement(c, k, label, tr.pattern_id, tr.room_id))
    return tuple(out)
