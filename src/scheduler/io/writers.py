"""Writers: assignments hand-off, JSON solution, instance tables (SPEC §5.4, §8, L6)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scheduler.domain import Assignment, Instance, Solution, label_sort_key
from scheduler.time import format_clock

ASSIGNMENT_COLUMNS = (
    "professor_id",
    "course_id",
    "section_type",
    "section_label",
    "capacity",
    "units",
    "source",
)


def assignment_records(assignments: tuple[Assignment, ...]) -> list[dict[str, object]]:
    """Assignment rows sorted by professor, course, type, label."""
    ordered = sorted(
        assignments,
        key=lambda a: (
            a.professor_id,
            a.course_id,
            a.section_type.value,
            label_sort_key(a.section_label),
        ),
    )
    return [
        {
            "professor_id": a.professor_id,
            "course_id": a.course_id,
            "section_type": a.section_type.value,
            "section_label": a.section_label,
            "capacity": a.capacity,
            "units": a.units,
            "source": a.source.value,
        }
        for a in ordered
    ]


def write_assignments(assignments: tuple[Assignment, ...], path: Path | str) -> Path:
    """Write the editable Stage A hand-off as CSV or .xlsx (by extension)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(assignment_records(assignments), columns=list(ASSIGNMENT_COLUMNS))
    if path.suffix.lower() == ".xlsx":
        frame.to_excel(path, sheet_name="assignments", index=False)
    else:
        frame.to_csv(path, index=False)
    return path


def solution_to_dict(solution: Solution) -> dict[str, object]:
    """Canonical JSON form of a solution."""
    placements = (
        None
        if solution.placements is None
        else [
            {
                "course_id": p.course_id,
                "section_type": p.section_type.value,
                "section_label": p.section_label,
                "pattern_id": p.pattern_id,
                "room_id": p.room_id,
            }
            for p in sorted(
                solution.placements,
                key=lambda p: (p.course_id, p.section_type.value, label_sort_key(p.section_label)),
            )
        ]
    )
    return {
        "assignments": assignment_records(solution.assignments),
        "placements": placements,
        "meta": solution.meta,
    }


def write_solution(solution: Solution, path: Path | str) -> Path:
    """Write a solution as JSON (deterministic key order)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(solution_to_dict(solution), indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return path


def _days_code(days: tuple[str, ...]) -> str:
    letters = {"Mon": "M", "Tue": "T", "Wed": "W", "Thu": "R", "Fri": "F", "Sat": "S", "Sun": "U"}
    return "".join(letters[d] for d in days)


def instance_tables(instance: Instance) -> dict[str, list[dict[str, object]]]:
    """Long-format tables (SPEC §8) for an instance; inverse of the readers."""
    tables: dict[str, list[dict[str, object]]] = {
        "professors": [
            {
                "professor_id": p.id,
                "name": p.name,
                "load_min": p.load_min,
                "load_max": p.load_max,
                "priority": p.priority,
                "max_preps": p.max_preps if p.max_preps is not None else "",
                "max_days": p.max_days if p.max_days is not None else "",
                "multi_section_pref": p.multi_section_pref,
                "schedule_style": p.schedule_style.value,
                "day_families": ";".join(sorted(p.day_families)),
                "day_family_mixing": p.day_family_mixing.value,
            }
            for p in instance.professors
        ],
        "offerings": [
            {
                "course_id": o.course_id,
                "title": o.title,
                "level": o.level,
                "section_type": o.section_type.value,
                "num_sections": o.num_sections,
                "capacity": o.capacity,
                "units": o.units,
                "room_type": o.room_type,
            }
            for o in instance.offerings
        ],
        "rooms": [
            {
                "room_id": r.id,
                "building": r.building,
                "capacity": r.capacity,
                "room_type": r.room_type,
            }
            for r in instance.rooms
        ],
        "room_availability": [
            {"room_id": ra.room_id, "pattern_id": ra.pattern_id}
            for ra in instance.room_availability
        ],
        "time_patterns": [_pattern_record(instance, pid) for pid in instance.pattern_ids],
        "course_preferences": [
            {
                "professor_id": c.professor_id,
                "course_id": c.course_id,
                "section_type": c.section_type.value if c.section_type else "",
                "rank": c.rank or "cannot",
            }
            for c in instance.course_preferences
        ],
        "time_preferences": [
            {"professor_id": t.professor_id, "pattern_id": t.pattern_id, "rank": t.rank or "cannot"}
            for t in instance.time_preferences
        ],
        "unavailability": [
            {
                "professor_id": u.professor_id,
                "day": u.day,
                "start": format_clock(u.start),
                "end": format_clock(u.end),
                "reason": u.reason,
            }
            for u in instance.unavailability
        ],
        "blocked_slots": [
            {
                "day": b.day,
                "start": format_clock(b.start),
                "end": format_clock(b.end),
                "reason": b.reason,
            }
            for b in instance.blocked_slots
        ],
        "pre_assignments": [
            {
                "professor_id": a.professor_id,
                "course_id": a.course_id,
                "section_type": a.section_type.value,
                "count": a.count,
                "section_label": ";".join(a.section_labels),
            }
            for a in instance.pre_assignments
        ],
        "conflict_groups": [
            {
                "group_id": g.id,
                "course_id": c,
                "mode": g.mode or "",
                "weight": g.weight if g.weight is not None else "",
            }
            for g in instance.conflict_groups
            for c in sorted(g.course_ids)
        ],
    }
    return tables


def _pattern_record(instance: Instance, pid: str) -> dict[str, object]:
    t = instance.pattern_by_id[pid]
    starts = {(m.start, m.end) for m in t.meetings}
    if len(starts) != 1:
        raise ValueError(
            f"pattern {pid}: meetings with different times cannot be written as one row"
        )
    start, end = next(iter(starts))
    return {
        "pattern_id": t.id,
        "days": _days_code(t.days),
        "start": format_clock(start),
        "end": format_clock(end),
        "allowed_section_types": ";".join(sorted(k.value for k in t.allowed_types)),
    }


def write_instance(instance: Instance, folder: Path | str) -> Path:
    """Write an instance as a folder of CSV files."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for name, records in instance_tables(instance).items():
        if records or name in ("professors", "offerings", "rooms", "time_patterns"):
            pd.DataFrame(records).to_csv(folder / f"{name}.csv", index=False)
    return folder
