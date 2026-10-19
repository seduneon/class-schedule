"""Time engine: parsing, overlap, cliques, adjacency (SPEC §3.2).

alpha_p lives in :mod:`scheduler.time.independent_set` (imports PuLP; import explicitly).
"""

from scheduler.time.availability import (
    adjacency,
    blocked_pattern_ids,
    cliques,
    neighbours,
    off_day_pattern_ids,
    professor_patterns,
    unavailable_pattern_ids,
    usable_patterns,
)
from scheduler.time.overlap import (
    AdjacentPair,
    adjacent_pairs,
    adjacent_pattern_pairs,
    consecutive_chains,
    earliest_meeting,
    intervals_overlap,
    max_independent_set_size,
    meetings_overlap,
    overlap_cliques,
    overlap_graph,
    pattern_hits_interval,
    patterns_overlap,
)
from scheduler.time.parsing import format_clock, make_meetings, parse_clock, parse_day, parse_days

__all__ = [
    "AdjacentPair",
    "adjacency",
    "adjacent_pairs",
    "adjacent_pattern_pairs",
    "blocked_pattern_ids",
    "cliques",
    "consecutive_chains",
    "earliest_meeting",
    "format_clock",
    "intervals_overlap",
    "make_meetings",
    "max_independent_set_size",
    "meetings_overlap",
    "neighbours",
    "off_day_pattern_ids",
    "overlap_cliques",
    "overlap_graph",
    "parse_clock",
    "parse_day",
    "parse_days",
    "pattern_hits_interval",
    "patterns_overlap",
    "professor_patterns",
    "unavailable_pattern_ids",
    "usable_patterns",
]
