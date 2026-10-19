"""Rank -> weight conversion (SPEC §3.4)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from scheduler.config import PreferencesConfig
from scheduler.domain import Instance, SectionType


def rank_weight(rank: int, m: int, cfg: PreferencesConfig) -> float:
    """Raw weight of an item ranked ``rank`` among ``m`` ranked items (before normalization).

    - linear:      w = (m - rank + 1) / m
    - exponential: w = beta^(rank - 1)
    - top_k:       w = 1 if rank <= k else 0
    """
    if rank < 1:
        raise ValueError(f"rank must be >= 1, got {rank}")
    if cfg.strategy == "linear":
        return (m - rank + 1) / m
    if cfg.strategy == "exponential":
        return float(cfg.beta ** (rank - 1))
    return 1.0 if rank <= cfg.top_k else 0.0


def weights_for(
    ranks: Mapping[str, int | None], universe: Iterable[str], cfg: PreferencesConfig
) -> dict[str, float]:
    """Normalized weights w_{p,item} for one professor over ``universe``.

    ``ranks`` maps ranked items to a rank (``None`` = cannot; such items get weight 0).
    Unranked items get ``unranked_weight``. ``m`` is the number of ranked items, raised to
    the largest rank if ranks have gaps so that linear weights stay in [0, 1].
    Weights are then divided by their maximum so the best item has weight 1.
    """
    m = ranked_count(ranks.values())
    raw = {item: _raw_weight(item, ranks, m, cfg) for item in sorted(set(universe))}
    return _normalized(raw)


def ranked_count(ranks: Iterable[int | None]) -> int:
    """m: number of ranked items, raised to the largest rank if ranks have gaps."""
    ranked = [r for r in ranks if r is not None]
    return max([len(ranked), *ranked]) if ranked else 0


def _raw_weight[K](item: K, ranks: Mapping[K, int | None], m: int, cfg: PreferencesConfig) -> float:
    if item not in ranks:
        return cfg.unranked_weight
    rank = ranks[item]
    return 0.0 if rank is None else rank_weight(rank, m, cfg)


def _normalized[K](raw: dict[K, float]) -> dict[K, float]:
    top = max(raw.values(), default=0.0)
    if top <= 0:
        return raw
    return {k: v / top for k, v in raw.items()}


def course_weights(
    instance: Instance, cfg: PreferencesConfig
) -> dict[tuple[str, str, SectionType], float]:
    """w^C_{p,c,k} for every professor and offered (c, k) (SPEC §3.4).

    m counts the professor's preference rows (typed or not); the rank of (p, c, k) is
    resolved by :attr:`Instance.course_type_rank`; weights are normalized over (c, k).
    """
    rows: dict[str, list[int | None]] = {}
    for cp in instance.course_preferences:
        rows.setdefault(cp.professor_id, []).append(cp.rank)
    resolved = instance.course_type_rank
    out: dict[tuple[str, str, SectionType], float] = {}
    for p in instance.professor_ids:
        m = ranked_count(rows.get(p, []))
        ranks = {(c, k): r for (pp, c, k), r in resolved.items() if pp == p}
        raw = {key: _raw_weight(key, ranks, m, cfg) for key in instance.offering_keys}
        for (c, k), w in _normalized(raw).items():
            out[(p, c, k)] = w
    return out


def time_weights(instance: Instance, cfg: PreferencesConfig) -> dict[tuple[str, str], float]:
    """w^T_{p,t} for every professor and time pattern."""
    out: dict[tuple[str, str], float] = {}
    for p in instance.professor_ids:
        ranks = {t: r for (pp, t), r in instance.time_rank.items() if pp == p}
        for t, w in weights_for(ranks, instance.pattern_ids, cfg).items():
            out[(p, t)] = w
    return out
