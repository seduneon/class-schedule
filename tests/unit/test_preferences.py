"""Rank -> weight strategies (SPEC §3.4)."""

from __future__ import annotations

import pytest

from scheduler.config import PreferencesConfig
from scheduler.preferences import course_weights, weights_for


def test_linear() -> None:
    w = weights_for({"a": 1, "b": 2, "c": 3}, ["a", "b", "c", "d"], PreferencesConfig())
    assert w == pytest.approx({"a": 1.0, "b": 2 / 3, "c": 1 / 3, "d": 0.0})


def test_exponential_and_top_k() -> None:
    cfg = PreferencesConfig(strategy="exponential", beta=0.5)
    assert weights_for({"a": 1, "b": 3}, ["a", "b"], cfg) == pytest.approx({"a": 1, "b": 0.25})
    cfg = PreferencesConfig(strategy="top_k", top_k=1)
    assert weights_for({"a": 1, "b": 2}, ["a", "b"], cfg) == {"a": 1.0, "b": 0.0}


def test_cannot_and_unranked() -> None:
    cfg = PreferencesConfig(unranked_policy="allow_low", unranked_weight=0.2)
    w = weights_for({"a": 1, "x": None}, ["a", "x", "u"], cfg)
    assert w == pytest.approx({"a": 1.0, "x": 0.0, "u": 0.2})


def test_normalized_so_max_is_one() -> None:
    # Ranking more items does not buy more influence: the best item always has weight 1.
    cfg = PreferencesConfig(strategy="exponential", beta=0.5)
    w = weights_for({"a": 2, "b": 3}, ["a", "b"], cfg)
    assert max(w.values()) == pytest.approx(1.0)
    assert weights_for({}, ["a"], PreferencesConfig()) == {"a": 0.0}


def test_rank_gaps_keep_linear_weights_non_negative() -> None:
    w = weights_for({"a": 1, "b": 5}, ["a", "b"], PreferencesConfig())
    assert w == pytest.approx({"a": 1.0, "b": 0.2})


def test_course_weights_per_section_type() -> None:
    """SPEC §3.4: a typed row beats the course row; m counts all preference rows."""
    from scheduler.domain import CoursePreference, SectionType
    from tests.factory import instance, offering, prof

    inst = instance(
        professors=[prof("P")],
        offerings=[offering("M1"), offering("M1", kind="R"), offering("M2")],
        course_preferences=[
            CoursePreference("P", "M1", 3, SectionType.L),
            CoursePreference("P", "M1", 1, SectionType.R),
            CoursePreference("P", "M2", 2),
        ],
    )
    w = course_weights(inst, PreferencesConfig())
    assert w[("P", "M1", SectionType.R)] == 1.0
    assert w[("P", "M2", SectionType.L)] == pytest.approx(2 / 3)
    assert w[("P", "M1", SectionType.L)] == pytest.approx(1 / 3)
