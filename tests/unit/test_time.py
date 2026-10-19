"""M2: time parsing, overlap, cliques, adjacency, alpha_p (SPEC §3.2)."""

from __future__ import annotations

import itertools

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from scheduler.domain import Interval, Meeting, SectionType, TimePattern
from scheduler.time import (
    adjacent_pairs,
    adjacent_pattern_pairs,
    consecutive_chains,
    format_clock,
    max_independent_set_size,
    overlap_cliques,
    overlap_graph,
    parse_clock,
    parse_day,
    parse_days,
    pattern_hits_interval,
    patterns_overlap,
)
from scheduler.time.independent_set import max_independent_patterns
from tests.factory import pattern


def test_parse_clock_roundtrip() -> None:
    assert parse_clock("09:30") == 570
    assert parse_clock("9:05") == 545
    assert format_clock(570) == "09:30"
    with pytest.raises(ValueError):
        parse_clock("9.30")
    with pytest.raises(ValueError):
        parse_clock("10:60")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("MWF", ("Mon", "Wed", "Fri")),
        ("TR", ("Tue", "Thu")),
        ("TTh", ("Tue", "Thu")),
        ("Mon;Wed", ("Mon", "Wed")),
        ("Thu", ("Thu",)),
        ("FM", ("Mon", "Fri")),
    ],
)
def test_parse_days(text: str, expected: tuple[str, ...]) -> None:
    assert parse_days(text) == expected


def test_parse_days_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        parse_days("MXF")
    with pytest.raises(ValueError):
        parse_days("MM")
    assert parse_day("thursday") == "Thu"


def test_touching_intervals_do_not_overlap() -> None:
    a = pattern("A", "MWF", "09:00", "10:00")
    b = pattern("B", "MWF", "10:00", "11:00")
    assert not patterns_overlap(a, b)


def test_buffer_makes_touching_intervals_overlap() -> None:
    a = pattern("A", "MWF", "09:00", "10:00")
    b = pattern("B", "MWF", "10:05", "11:00")
    assert not patterns_overlap(a, b, buffer=5)
    assert patterns_overlap(a, b, buffer=10)


def test_overlapping_patterns_with_different_labels_conflict() -> None:
    """Regression: conflicts come from intervals, not from slot labels."""
    a = pattern("MWF0900", "MWF", "09:00", "09:50")
    b = pattern("W0930-long", "W", "09:30", "11:00")
    c = pattern("TR0900", "TR", "09:00", "10:15")
    assert patterns_overlap(a, b)
    assert not patterns_overlap(a, c)


def test_multi_day_pattern_overlaps_on_any_shared_day() -> None:
    a = pattern("MWF", "MWF", "09:00", "09:50")
    b = pattern("F", "F", "09:30", "10:30")
    assert patterns_overlap(a, b)


def test_pattern_hits_interval() -> None:
    a = pattern("A", "MWF", "09:00", "09:50")
    assert pattern_hits_interval(a, Interval("Wed", 9, 9 * 60 + 10))
    assert not pattern_hits_interval(a, Interval("Tue", 0, 24 * 60))
    assert not pattern_hits_interval(a, Interval("Mon", 590, 600))


def test_cliques_simple() -> None:
    pats = [
        pattern("A", "M", "09:00", "10:00"),
        pattern("B", "M", "09:30", "10:30"),
        pattern("C", "M", "10:15", "11:00"),
        pattern("D", "T", "09:00", "10:00"),
    ]
    assert overlap_cliques(pats) == (
        frozenset({"A", "B"}),
        frozenset({"B", "C"}),
        frozenset({"D"}),
    )


def test_adjacency() -> None:
    a = pattern("A", "MWF", "09:00", "09:50")
    b = pattern("B", "MWF", "10:00", "10:50")
    c = pattern("C", "MWF", "11:30", "12:20")
    assert adjacent_pattern_pairs([a, b, c], gap=15) == (("A", "B"),)
    assert {p.day for p in adjacent_pairs([a, b, c], gap=15)} == {"Mon", "Wed", "Fri"}
    assert adjacent_pattern_pairs([a, b, c], gap=60) == (("A", "B"), ("B", "C"))
    assert consecutive_chains([a, b, c], gap=60, length=3) == (("A", "B", "C"),)


def test_alpha_counts_non_overlapping_patterns() -> None:
    pats = [
        pattern("A", "M", "09:00", "10:00"),
        pattern("B", "M", "09:30", "10:30"),
        pattern("C", "M", "10:15", "11:00"),
        pattern("D", "T", "09:00", "10:00"),
    ]
    assert max_independent_patterns(pats) == 3  # A, C, D
    assert max_independent_patterns([]) == 0


# ----- property tests ---------------------------------------------------------

_days = st.sampled_from(["M", "T", "W", "R", "F", "MWF", "TR", "MW"])


@st.composite
def _patterns(draw: st.DrawFn) -> list[TimePattern]:
    n = draw(st.integers(min_value=1, max_value=9))
    out = []
    for i in range(n):
        start = draw(st.integers(min_value=8 * 12, max_value=17 * 12)) * 5
        length = draw(st.sampled_from([50, 75, 110, 170]))
        days = parse_days(draw(_days))
        out.append(
            TimePattern(
                f"P{i}",
                tuple(Meeting(d, start, start + length) for d in days),
                frozenset({SectionType.L}),
            )
        )
    return out


@settings(max_examples=150, deadline=None)
@given(_patterns(), st.sampled_from([0, 5, 10]))
def test_every_overlapping_pair_shares_a_clique(pats: list[TimePattern], buffer: int) -> None:
    cliques = overlap_cliques(pats, buffer)
    graph = overlap_graph(pats, buffer)
    for a, b in itertools.combinations(sorted(graph), 2):
        if b in graph[a]:
            assert any(a in q and b in q for q in cliques)
    for q in cliques:  # cliques really are cliques
        for a, b in itertools.combinations(sorted(q), 2):
            assert b in graph[a]
    assert set().union(*cliques) == {p.id for p in pats}
    for q in cliques:  # maximal
        assert not any(q < other for other in cliques)


@settings(max_examples=40, deadline=None)
@given(_patterns())
def test_alpha_matches_brute_force(pats: list[TimePattern]) -> None:
    graph = overlap_graph(pats)
    ids = sorted(graph)
    best = 0
    for r in range(len(ids), 0, -1):
        if any(
            all(b not in graph[a] for a, b in itertools.combinations(combo, 2))
            for combo in itertools.combinations(ids, r)
        ):
            best = r
            break
    assert max_independent_patterns(pats) == best
    assert max_independent_set_size(pats) == best
