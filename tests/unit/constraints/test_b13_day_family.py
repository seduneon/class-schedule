"""B13 — Day-family preference."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.domain import FamilyMixing, Instance, Solution, TimePreference
from scheduler.validation import validate
from tests.factory import ablation_b, asg, instance, offering, pattern, plc, prof, room

PATTERNS = [
    pattern("MWF0900", "MWF", "09:00", "09:50"),
    pattern("TR0900", "TR", "09:00", "10:15"),
    pattern("MWF1000", "MWF", "10:00", "10:50"),
]
PREFS = ["MWF0900", "TR0900", "MWF1000"]  # P ranks them in this order


def _inst(**prof_kw: object) -> Instance:
    return instance(
        professors=[prof("P", **prof_kw)],
        offerings=[offering("M1"), offering("M2")],
        rooms=[room("R1"), room("R2")],
        patterns=PATTERNS,
        time_preferences=[TimePreference("P", t, i + 1) for i, t in enumerate(PREFS)],
    )


def _one(inst: Instance) -> tuple:  # type: ignore[type-arg]
    return (asg(inst, "P", "M1", "1L"),)


def _two(inst: Instance) -> tuple:  # type: ignore[type-arg]
    return (asg(inst, "P", "M1", "1L"), asg(inst, "P", "M2", "1L"))


def test_b13_family_of_pattern() -> None:
    assert [t.family for t in PATTERNS] == ["MWF", "TR", "MWF"]


def test_b13_validator_off_family() -> None:
    inst = _inst(day_families=frozenset({"TR"}))
    sol = Solution(_one(inst), (plc("M1", "1L", "MWF0900", "R1"),))
    assert [v.message for v in validate(inst, sol, Config(), ids=["B13"])] == [
        "P teaches M1-1L outside preferred days TR"
    ]
    ok = Solution(_one(inst), (plc("M1", "1L", "TR0900", "R1"),))
    assert validate(inst, ok, Config(), ids=["B13"]) == []


def test_b13_validator_mixing() -> None:
    sol_of = lambda inst: Solution(  # noqa: E731
        _two(inst), (plc("M1", "1L", "MWF0900", "R1"), plc("M2", "1L", "TR0900", "R1"))
    )
    allow = _inst()
    assert validate(allow, sol_of(allow), Config(), ids=["B13"]) == []
    avoid = _inst(day_family_mixing=FamilyMixing.AVOID)
    [v] = validate(avoid, sol_of(avoid), Config(), ids=["B13"])
    assert (v.message, v.severity) == ("P mixes day families MWF and TR", "warning")
    forbid = _inst(day_family_mixing=FamilyMixing.FORBID)
    [v] = validate(forbid, sol_of(forbid), Config(), ids=["B13"])
    assert v.severity == "error"


def test_b13_ablation_pair_off_family() -> None:
    inst = _inst(day_families=frozenset({"TR"}))
    off, on = ablation_b(inst, _one(inst), "B13", on_mode="soft")
    assert off == ["P teaches M1-1L outside preferred days TR"]
    assert on == []


def test_b13_ablation_pair_mixing() -> None:
    inst = _inst(day_family_mixing=FamilyMixing.AVOID)
    off, on = ablation_b(inst, _two(inst), "B13", on_mode="soft")
    assert off == ["P mixes day families MWF and TR"]
    assert on == []


def test_b13_hard_filters_off_family_patterns() -> None:
    from scheduler.pipeline import run_stage_b
    from tests.factory import fast_config

    inst = _inst(day_families=frozenset({"TR"}))
    result = run_stage_b(inst, fast_config().with_mode("B13", "hard"), _one(inst), presolve=False)
    assert result.ctx is not None
    assert {k[1] for k in result.ctx.family("y")} == {"TR0900"}


def test_b13_forbid_is_hard_even_in_soft_mode() -> None:
    from scheduler.pipeline import run_stage_b
    from tests.factory import fast_config

    inst = _inst(day_family_mixing=FamilyMixing.FORBID)
    result = run_stage_b(inst, fast_config(), _two(inst), presolve=False)
    assert result.solution is not None
    assert not [v for v in result.violations if v.id == "B13"]
    assert not any(s.cid == "B13" for s in result.slacks)
