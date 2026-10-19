"""Which time patterns are usable, globally and per professor (SPEC §3.2, B4)."""

from __future__ import annotations

from collections.abc import Sequence

from scheduler.domain import Instance, TimePattern, is_placeholder
from scheduler.time.overlap import (
    AdjacentPair,
    adjacent_pairs,
    overlap_cliques,
    overlap_graph,
    pattern_hits_interval,
)


def blocked_pattern_ids(instance: Instance) -> frozenset[str]:
    """Patterns with a meeting intersecting a blocked slot."""
    return instance.memo(
        ("blocked_patterns",),
        lambda: frozenset(
            t.id
            for t in instance.patterns
            if any(pattern_hits_interval(t, b.interval) for b in instance.blocked_slots)
        ),
    )


def off_day_pattern_ids(instance: Instance, days: Sequence[str]) -> frozenset[str]:
    """Patterns meeting on a day that is not a configured teaching day."""
    allowed = frozenset(days)
    return frozenset(
        t.id for t in instance.patterns if any(m.day not in allowed for m in t.meetings)
    )


def unavailable_pattern_ids(instance: Instance, professor_id: str) -> frozenset[str]:
    """Patterns professor ``p`` cannot teach: hits an unavailability, or time rank ``cannot``."""
    if is_placeholder(professor_id):
        return frozenset()

    def compute() -> frozenset[str]:
        unav = instance.unavailability_by_professor.get(professor_id, ())
        out: set[str] = set()
        for t in instance.patterns:
            if instance.time_rank.get((professor_id, t.id), 0) is None or any(
                pattern_hits_interval(t, u.interval) for u in unav
            ):
                out.add(t.id)
        return frozenset(out)

    return instance.memo(("unavailable_patterns", professor_id), compute)


def usable_patterns(instance: Instance, days: Sequence[str]) -> tuple[TimePattern, ...]:
    """Patterns that are neither blocked nor on a non-teaching day, sorted by ID."""
    bad = blocked_pattern_ids(instance) | off_day_pattern_ids(instance, days)
    return tuple(instance.pattern_by_id[pid] for pid in instance.pattern_ids if pid not in bad)


def professor_patterns(
    instance: Instance, professor_id: str, days: Sequence[str]
) -> tuple[TimePattern, ...]:
    """Usable patterns available to professor ``p`` (used for alpha_p, A8)."""
    unav = unavailable_pattern_ids(instance, professor_id)
    return tuple(t for t in usable_patterns(instance, days) if t.id not in unav)


def cliques(instance: Instance, buffer: int) -> tuple[frozenset[str], ...]:
    """Cached maximal overlap cliques over all patterns."""
    return instance.memo(("cliques", buffer), lambda: overlap_cliques(instance.patterns, buffer))


def neighbours(instance: Instance, buffer: int) -> dict[str, frozenset[str]]:
    """Cached overlap graph over all patterns."""
    return instance.memo(
        ("overlap_graph", buffer), lambda: overlap_graph(instance.patterns, buffer)
    )


def adjacency(instance: Instance, gap: int) -> tuple[AdjacentPair, ...]:
    """Cached adjacent pairs over all patterns."""
    return instance.memo(("adjacency", gap), lambda: adjacent_pairs(instance.patterns, gap))
