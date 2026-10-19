"""Assemble the Stage A model and read its solution."""

from __future__ import annotations

from scheduler.config import Config, Stage
from scheduler.domain import Instance
from scheduler.model.context import ModelContext
from scheduler.model.registry import builders_for
from scheduler.model.stage_a import constraints as _constraints  # noqa: F401  (registers builders)
from scheduler.model.stage_a.objective import add_satisfaction_terms, stage_a_levels
from scheduler.model.stage_a.variables import NKey, build_variables, n_vars


def build_stage_a(instance: Instance, config: Config) -> ModelContext:
    """Variables, every enabled Stage A constraint, and the level-3 satisfaction terms."""
    ctx = ModelContext("stage_a", instance, config, Stage.A, stage_a_levels(config))
    build_variables(ctx)
    for builder in builders_for(Stage.A):
        settings = config.settings(builder.id)
        if config.enabled(builder.id):
            builder().build(ctx, settings)
    add_satisfaction_terms(ctx)
    return ctx


def extract_counts(ctx: ModelContext) -> dict[NKey, int]:
    """Solved n_{p,c,k} values (rounded), zeros dropped."""
    out: dict[NKey, int] = {}
    for key, var in n_vars(ctx).items():
        value = round(ctx.value(var))
        if value > 0:
            out[key] = value
    return out
