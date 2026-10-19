"""Exact time logic: overlap, cliques, adjacency (SPEC §3.2).

Conflicts always come from actual meeting intervals, never from pattern labels.
Intervals are half-open ``[start, end)``; a buffer extends each *end*.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from scheduler.domain import DAYS, Interval, Meeting, TimePattern


def intervals_overlap(s1: int, e1: int, s2: int, e2: int, buffer: int = 0) -> bool:
    """``[s1, e1 + buffer)`` and ``[s2, e2 + buffer)`` intersect."""
    return s1 < e2 + buffer and s2 < e1 + buffer


def meetings_overlap(a: Meeting, b: Meeting, buffer: int = 0) -> bool:
    """Same day and intersecting (buffered) intervals."""
    return a.day == b.day and intervals_overlap(a.start, a.end, b.start, b.end, buffer)


def patterns_overlap(t: TimePattern, u: TimePattern, buffer: int = 0) -> bool:
    """t ~ u: some meeting of t and some meeting of u overlap (SPEC §3.2)."""
    return any(meetings_overlap(m, n, buffer) for m in t.meetings for n in u.meetings)


def pattern_hits_interval(t: TimePattern, interval: Interval) -> bool:
    """Some meeting of ``t`` intersects ``interval`` (unavailability, blocked slot)."""
    return any(
        m.day == interval.day and intervals_overlap(m.start, m.end, interval.start, interval.end)
        for m in t.meetings
    )


def overlap_graph(patterns: Sequence[TimePattern], buffer: int = 0) -> dict[str, frozenset[str]]:
    """Neighbours of every pattern in the overlap graph (a pattern is not its own neighbour)."""
    ordered = sorted(patterns, key=lambda t: t.id)
    adj: dict[str, set[str]] = {t.id: set() for t in ordered}
    for i, t in enumerate(ordered):
        for u in ordered[i + 1 :]:
            if patterns_overlap(t, u, buffer):
                adj[t.id].add(u.id)
                adj[u.id].add(t.id)
    return {k: frozenset(v) for k, v in adj.items()}


def overlap_cliques(patterns: Sequence[TimePattern], buffer: int = 0) -> tuple[frozenset[str], ...]:
    """Maximal cliques K of the overlap graph (SPEC §3.2).

    For every day d and every meeting start tau on d, the set of patterns with a meeting
    active at tau (``start <= tau < end + buffer``) is a clique. Every overlapping pair
    shares at least one such clique: the later of the two starts lies in both intervals.
    Only maximal sets are kept. Every pattern belongs to at least one clique.
    """
    by_day: dict[str, list[tuple[str, Meeting]]] = {}
    for t in patterns:
        for m in t.meetings:
            by_day.setdefault(m.day, []).append((t.id, m))
    candidates: set[frozenset[str]] = set()
    for day in sorted(by_day, key=_day_index):
        items = by_day[day]
        for tau in sorted({m.start for _, m in items}):
            active = frozenset(pid for pid, m in items if m.start <= tau < m.end + buffer)
            if active:
                candidates.add(active)
    maximal = [c for c in candidates if not any(c < other for other in candidates)]
    return tuple(sorted(maximal, key=lambda c: tuple(sorted(c))))


@dataclass(frozen=True, order=True)
class AdjacentPair:
    """``first -> second`` on ``day``: second starts 0..gap minutes after first ends."""

    first: str
    second: str
    day: str


def adjacent_pairs(patterns: Sequence[TimePattern], gap: int) -> tuple[AdjacentPair, ...]:
    """All adjacent pairs (SPEC §3.2), one entry per (first, second, day)."""
    out: set[AdjacentPair] = set()
    for t in patterns:
        for u in patterns:
            if t.id == u.id:
                continue
            for m in t.meetings:
                for n in u.meetings:
                    if m.day == n.day and 0 <= n.start - m.end <= gap:
                        out.add(AdjacentPair(t.id, u.id, m.day))
    return tuple(sorted(out))


def adjacent_pattern_pairs(
    patterns: Sequence[TimePattern], gap: int
) -> tuple[tuple[str, str], ...]:
    """Distinct ordered pattern pairs (t, t') that are adjacent on at least one day."""
    return tuple(sorted({(p.first, p.second) for p in adjacent_pairs(patterns, gap)}))


def consecutive_chains(
    patterns: Sequence[TimePattern], gap: int, length: int
) -> tuple[tuple[str, ...], ...]:
    """Chains t_1 -> ... -> t_length of adjacent patterns on a single day (B10 windows)."""
    pairs = adjacent_pairs(patterns, gap)
    succ: dict[tuple[str, str], list[str]] = {}
    for p in pairs:
        succ.setdefault((p.day, p.first), []).append(p.second)
    chains: set[tuple[str, ...]] = set()

    def extend(day: str, chain: tuple[str, ...]) -> None:
        if len(chain) == length:
            chains.add(chain)
            return
        for nxt in sorted(succ.get((day, chain[-1]), [])):
            if nxt not in chain:
                extend(day, (*chain, nxt))

    for day, first in sorted({(p.day, p.first) for p in pairs}):
        extend(day, (first,))
    return tuple(sorted(chains))


def meeting_days(patterns: Iterable[TimePattern]) -> tuple[str, ...]:
    """Days used by any of the patterns, in week order."""
    used = {m.day for t in patterns for m in t.meetings}
    return tuple(d for d in DAYS if d in used)


def earliest_meeting(t: TimePattern) -> tuple[int, int]:
    """(day index, start) of the earliest weekly meeting of ``t`` (B7 ordering)."""
    return min((_day_index(m.day), m.start) for m in t.meetings)


def _day_index(day: str) -> int:
    return DAYS.index(day)


def max_independent_set_size(patterns: Sequence[TimePattern], buffer: int = 0) -> int:
    """Exact maximum number of pairwise non-overlapping patterns, in pure Python.

    Branching rule: some maximum independent set contains v or one of its neighbours, so
    MIS(G) = max_{u in N[v]} 1 + MIS(G - N[u]) for a minimum-degree vertex v (memoized on
    bit masks). Used by the validator, which must not depend on a MIP solver.
    """
    graph = overlap_graph(patterns, buffer)
    ids = sorted(graph)
    index = {pid: i for i, pid in enumerate(ids)}
    nbr = [sum(1 << index[u] for u in graph[pid]) for pid in ids]
    memo: dict[int, int] = {}

    def mis(mask: int) -> int:
        if mask == 0:
            return 0
        if mask in memo:
            return memo[mask]
        best_v, best_deg = -1, len(ids) + 1
        rest = mask
        while rest:
            v = (rest & -rest).bit_length() - 1
            rest &= rest - 1
            deg = (nbr[v] & mask).bit_count()
            if deg < best_deg:
                best_v, best_deg = v, deg
                if deg <= 1:
                    break
        if best_deg <= 1:
            result = 1 + mis(mask & ~(1 << best_v) & ~nbr[best_v])
        else:
            result = 0
            cand = (nbr[best_v] & mask) | (1 << best_v)
            while cand:
                u = (cand & -cand).bit_length() - 1
                cand &= cand - 1
                result = max(result, 1 + mis(mask & ~(1 << u) & ~nbr[u]))
        memo[mask] = result
        return result

    return mis((1 << len(ids)) - 1)
