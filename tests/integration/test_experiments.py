"""M10 experiments: a smoke run (slow) and a fast shape check."""

from __future__ import annotations

import pytest

from scheduler.config import Config
from scheduler.experiment import fairness, scaling

CFG = Config().with_updates(solver={"threads": 1, "time_limit_s": 30})


def test_scaling_rows_have_model_sizes() -> None:
    rows = scaling([3], [0], CFG)
    assert rows[0]["A_status"] == "optimal" and rows[0]["A_variables"] > 0


@pytest.mark.slow
def test_fairness_raises_minimum_satisfaction() -> None:
    rows = fairness([0.0, 4.0], [0, 1], CFG)
    by = {(r["seed"], r["lambda"]): r for r in rows}
    for seed in (0, 1):
        assert by[(seed, 4.0)]["min_sat_course"] >= by[(seed, 0.0)]["min_sat_course"] - 1e-9
