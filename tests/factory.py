"""Helpers to build tiny instances in code."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scheduler.config import Config
from scheduler.domain import (
    Assignment,
    Instance,
    Offering,
    Placement,
    Professor,
    Room,
    SectionType,
    Solution,
    Source,
    TimePattern,
)
from scheduler.time import make_meetings, parse_clock, parse_days

ROOT = Path(__file__).resolve().parents[1]
TINY = ROOT / "data" / "examples" / "tiny"


def pattern(pid: str, days: str, start: str, end: str, types: str = "L;R;LAB") -> TimePattern:
    return TimePattern(
        pid,
        make_meetings(parse_days(days), parse_clock(start), parse_clock(end)),
        frozenset(SectionType(t) for t in types.split(";")),
    )


def prof(pid: str, lo: float = 0, hi: float = 3, **kw: Any) -> Professor:
    return Professor(pid, f"Prof {pid}", lo, hi, **kw)


def offering(
    course: str,
    n: int = 1,
    kind: str = "L",
    cap: int = 30,
    units: float | None = None,
    level: int | None = None,
    room_type: str = "lecture",
) -> Offering:
    k = SectionType(kind)
    default_units = 1.0 if k is SectionType.L else 0.5
    lvl = level if level is not None else int("".join(ch for ch in course if ch.isdigit()) or 0)
    return Offering(
        course, course, lvl, k, n, cap, units if units is not None else default_units, room_type
    )


def room(rid: str, cap: int = 50, room_type: str = "lecture", building: str = "B7") -> Room:
    return Room(rid, building, cap, room_type)


def instance(**kw: Any) -> Instance:
    """Instance with sensible defaults: one room, two non-overlapping patterns."""
    kw.setdefault("rooms", (room("R1"),))
    kw.setdefault(
        "patterns",
        (pattern("MWF0900", "MWF", "09:00", "09:50"), pattern("TR0900", "TR", "09:00", "10:15")),
    )
    kw.setdefault("professors", ())
    kw.setdefault("offerings", ())
    for key, value in list(kw.items()):
        if isinstance(value, list):
            kw[key] = tuple(value)
    return Instance(**kw)


# ----- hand-built solutions ------------------------------------------------------


def asg(
    inst: Instance, professor: str, course: str, label: str, source: str = "model"
) -> Assignment:
    """Assignment of an existing section of ``inst`` to ``professor``."""
    kind = SectionType(label.lstrip("0123456789"))
    sec = inst.section_by_key[(course, kind, label)]
    return Assignment(professor, course, kind, label, sec.capacity, sec.units, Source(source))


def plc(course: str, label: str, pattern_id: str, room_id: str) -> Placement:
    kind = SectionType(label.lstrip("0123456789"))
    return Placement(course, kind, label, pattern_id, room_id)


def tiny_assignments(inst: Instance) -> tuple[Assignment, ...]:
    """Hand-derived optimal Stage A solution of the tiny example."""
    return (
        asg(inst, "A", "MATH161", "1L"),
        asg(inst, "A", "MATH161", "2L"),
        asg(inst, "B", "MATH351", "1L"),
        asg(inst, "C", "MATH361", "1L"),
    )


def tiny_solution(inst: Instance) -> Solution:
    """Hand-derived optimal Stage B solution of the tiny example (all rules satisfied)."""
    return Solution(
        tiny_assignments(inst),
        (
            plc("MATH161", "1L", "MWF0900", "7.101"),
            plc("MATH161", "2L", "MWF1000", "7.101"),
            plc("MATH351", "1L", "TR1030", "7.102"),
            plc("MATH361", "1L", "TR0900", "7.101"),
        ),
    )


def with_placements(sol: Solution, *placements: Placement) -> Solution:
    """Replace the placements of the given sections."""
    keys = {p.section_key for p in placements}
    kept = tuple(p for p in sol.placements or () if p.section_key not in keys)
    return Solution(sol.assignments, kept + placements)


# ----- ablation helpers (SPEC §11 step 3) -------------------------------------------


def fast_config(**updates: Any) -> Config:
    """Default config with a single solver thread (deterministic, quick)."""
    cfg = Config().with_updates(solver={"threads": 1, "time_limit_s": 60})
    return cfg.with_updates(**updates) if updates else cfg


def ablation_a(
    inst: Instance, cid: str, on_mode: str = "hard", cfg: Config | None = None
) -> tuple[list[str], list[str]]:
    """Solve Stage A with ``cid`` off and on; return the validator messages for ``cid``
    (validated with the constraint enabled) for both runs."""
    from scheduler.pipeline import run_stage_a
    from scheduler.validation import validate

    base = cfg or fast_config()
    on = base.with_mode(cid, on_mode)
    msgs = []
    for run_cfg in (base.with_mode(cid, "off"), on):
        result = run_stage_a(inst, run_cfg, presolve=False)
        assert result.solution is not None, result.status
        msgs.append([v.message for v in validate(inst, result.solution, on, ids=[cid])])
    return msgs[0], msgs[1]


def ablation_b(
    inst: Instance,
    assignments: tuple[Assignment, ...],
    cid: str,
    on_mode: str = "hard",
    cfg: Config | None = None,
) -> tuple[list[str], list[str]]:
    """Stage B counterpart of :func:`ablation_a`."""
    from scheduler.pipeline import run_stage_b
    from scheduler.validation import validate

    base = cfg or fast_config()
    on = base.with_mode(cid, on_mode)
    msgs = []
    for run_cfg in (base.with_mode(cid, "off"), on):
        result = run_stage_b(inst, run_cfg, assignments, presolve=False)
        assert result.solution is not None, result.status
        msgs.append([v.message for v in validate(inst, result.solution, on, ids=[cid])])
    return msgs[0], msgs[1]


def two_pattern_instance(**kw: Any) -> Instance:
    """MWF0900 and TR0900 patterns; every professor ranks MWF0900 first."""
    from scheduler.domain import TimePreference

    profs = kw.pop("professors")
    prefs = [TimePreference(p.id, "MWF0900", 1) for p in profs] + [
        TimePreference(p.id, "TR0900", 2) for p in profs
    ]
    return instance(professors=profs, time_preferences=prefs, **kw)
