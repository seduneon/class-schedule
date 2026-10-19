"""L7 — integrated mode."""

from __future__ import annotations

import pytest

from scheduler.config import Mode
from scheduler.domain import Instance
from scheduler.experiment import MUST_ONLY, decomposition
from scheduler.model.integrated import proxy_objective
from scheduler.pipeline import run_integrated, run_stage_a, run_stage_b
from scheduler.validation import validate
from tests.factory import fast_config


def _must_only():  # type: ignore[no-untyped-def]
    cfg = fast_config()
    for cid in MUST_ONLY:
        cfg = cfg.with_mode(cid, Mode.OFF)
    return cfg


def test_integrated_on_tiny_is_valid_and_at_least_as_good(tiny: Instance) -> None:
    cfg = _must_only()
    integ = run_integrated(tiny, cfg)
    assert integ.solution is not None
    assert integ.objective(1) == 0
    assert [v for v in validate(tiny, integ.solution, cfg) if v.severity == "error"] == []
    a = run_stage_a(tiny, cfg)
    assert a.solution is not None
    b = run_stage_b(tiny, cfg, a.solution.assignments)
    assert b.solution is not None
    assert (
        proxy_objective(tiny, integ.solution, cfg) >= proxy_objective(tiny, b.solution, cfg) - 1e-6
    )
    assert integ.objective(3) == pytest.approx(proxy_objective(tiny, integ.solution, cfg))


def test_decomposition_rows() -> None:
    rows = decomposition([0], fast_config(), sizes=(3,))
    assert rows and rows[0]["relative_gap"] >= -1e-6
