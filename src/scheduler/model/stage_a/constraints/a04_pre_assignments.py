"""A4 — Pre-assignments."""

from __future__ import annotations

from scheduler.config import ConstraintSettings, Mode
from scheduler.domain import SectionType
from scheduler.model.context import ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_a.variables import n_vars


def _type_order(item: tuple[tuple[str, str, SectionType], int]) -> tuple[str, str, str]:
    (p, c, k), _ = item
    return (p, c, k.value)


@constraint("A4")
class PreAssignments:
    """n_{p,c,k} >= pre_{p,c,k}. Soft: n_{p,c,k} + s_{p,c,k} >= pre_{p,c,k}, s penalized.

    Variables for pre-assigned pairs always exist (a pre-assignment overrides A3).
    Specific labels are honoured later, when labels are attached (§5.4).
    """

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        n = n_vars(ctx)
        for (p, c, k), need in sorted(ctx.instance.pre_assigned.items(), key=_type_order):
            var = n.get((p, c, k))
            if var is None:
                continue  # not offered / unknown professor: reported by L1 diagnostics
            lhs = var
            if settings.mode is Mode.SOFT:
                lhs = var + ctx.add_slack(
                    "A4",
                    (p, c, k),
                    [p, c, k.value],
                    f"{p}: pre-assigned {c} {k.value} not given",
                    settings.weight,
                    settings.level,
                )
            ctx.add_constraint(lhs >= need, "A4", [p, c, k.value])
