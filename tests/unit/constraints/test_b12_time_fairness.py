"""B12 — Time satisfaction fairness."""

from __future__ import annotations

from scheduler.domain import Instance, TimePreference
from tests.factory import ablation_b, asg, fast_config, instance, offering, prof, room


def _inst() -> Instance:
    # One room; P and Q both want MWF0900. Q has priority 3, so total satisfaction alone
    # gives Q the slot and P nothing it ranked; fairness (lambda = 2) gives P MWF0900.
    return instance(
        professors=[prof("P"), prof("Q", priority=3.0)],
        offerings=[offering("M1"), offering("M2")],
        rooms=[room("R1")],
        time_preferences=[
            TimePreference("P", "MWF0900", 1),
            TimePreference("Q", "MWF0900", 1),
            TimePreference("Q", "TR0900", 2),
        ],
    )


def test_b12_ablation_pair() -> None:
    inst = _inst()
    sections = (asg(inst, "P", "M1", "1L"), asg(inst, "Q", "M2", "1L"))
    cfg = fast_config(objective={"lambda_time_fairness": 2.0})
    off, on = ablation_b(inst, sections, "B12", on_mode="soft", cfg=cfg)
    assert off == ["P got none of their preferred times (time satisfaction 0)"]
    assert on == []
