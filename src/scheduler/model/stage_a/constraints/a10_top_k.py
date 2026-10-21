"""A10 — Top-k course preference."""

from __future__ import annotations

from scheduler.config import A10Settings, ConstraintSettings, Mode
from scheduler.derived import outside_top_k
from scheduler.model.context import ModelContext
from scheduler.model.registry import constraint
from scheduler.model.stage_a.variables import n_vars
from scheduler.preferences import ranked_count, top_k_distance


@constraint("A10")
class TopK:
    """Hard: no n_{p,c,k} exists for (p, c, k) outside the top K -- enforced when variables
    are created (filter, never big-M). Soft: each section taught outside the top K is a
    slack e_{p,c,k} >= n_{p,c,k}, penalized with weight * d_{p,c,k} (distance past K,
    0 < d <= 1).
    """

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None:
        if settings.mode is not Mode.SOFT:
            return
        inst = ctx.instance
        k_max = ctx.config.typed_settings("A10", A10Settings).max_rank
        rows: dict[str, list[int | None]] = {}
        for cp in inst.course_preferences:
            rows.setdefault(cp.professor_id, []).append(cp.rank)
        for (p, c, k), n in n_vars(ctx).items():
            reason = outside_top_k(inst, ctx.config, p, c, k)
            if reason is None:
                continue
            m = ranked_count(rows.get(p, []))
            d = top_k_distance(inst.course_type_rank.get((p, c, k)), k_max, m)
            e = ctx.add_slack(
                "A10",
                (p, c, k),
                [p, c, k.value],
                f"{p} teaches {c} {k.value}: {reason}",
                settings.weight * d,
                settings.level,
            )
            ctx.add_constraint(e >= n, "A10", [p, c, k.value])
