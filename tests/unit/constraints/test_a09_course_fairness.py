"""A9 — Course satisfaction fairness."""

from __future__ import annotations

from scheduler.domain import CoursePreference, Instance
from tests.factory import ablation_a, fast_config, instance, offering, prof


def _inst() -> Instance:
    # Q has priority 3, so maximizing total satisfaction alone gives Q the course both want
    # and leaves P with nothing it ranked. Fairness (lambda = 2) prefers P: X, Q: Y.
    return instance(
        professors=[prof("P", 1, 1), prof("Q", 1, 1, priority=3.0)],
        offerings=[offering("X"), offering("Y")],
        course_preferences=[
            CoursePreference("P", "X", 1),
            CoursePreference("Q", "X", 1),
            CoursePreference("Q", "Y", 2),
        ],
    )


def test_a9_ablation_pair() -> None:
    cfg = fast_config(
        preferences={"unranked_policy": "allow_low", "unranked_weight": 0.0},
        objective={"lambda_course_fairness": 2.0},
    )
    off, on = ablation_a(_inst(), "A9", on_mode="soft", cfg=cfg)
    assert off == ["P got none of their preferred courses (course satisfaction 0)"]
    assert on == []
