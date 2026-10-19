"""Excel workbook report (SPEC L6)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from scheduler.config import Config
from scheduler.derived import conflict_groups
from scheduler.diagnostics.postsolve import SlackReport
from scheduler.diagnostics.presolve import Finding
from scheduler.domain import Instance, Solution, label_sort_key
from scheduler.io.writers import assignment_records
from scheduler.metrics import professor_metrics
from scheduler.time import format_clock
from scheduler.validation import Violation


def timetable_rows(instance: Instance, solution: Solution) -> list[dict[str, Any]]:
    """One row per placement with professor, days and times."""
    owner = {a.section_key: a.professor_id for a in solution.assignments}
    rows = []
    for p in solution.placements or ():
        pat = instance.pattern_by_id.get(p.pattern_id)
        meetings = sorted({(m.start, m.end) for m in pat.meetings}) if pat else []
        rows.append(
            {
                "professor_id": owner.get(p.section_key, ""),
                "course_id": p.course_id,
                "section_label": p.section_label,
                "section_type": p.section_type.value,
                "pattern_id": p.pattern_id,
                "days": " ".join(pat.days) if pat else "",
                "time": "; ".join(f"{format_clock(s)}-{format_clock(e)}" for s, e in meetings),
                "room_id": p.room_id,
                "building": instance.room_by_id[p.room_id].building
                if p.room_id in instance.room_by_id
                else "",
            }
        )
    return rows


def _sorted_frame(rows: list[dict[str, Any]], keys: list[str], columns: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=columns)
    if frame.empty:
        return frame
    frame["_lbl"] = frame["section_label"].map(label_sort_key) if "section_label" in frame else 0
    return frame.sort_values([*keys, "_lbl"], kind="stable").drop(columns="_lbl")


def write_excel_report(
    path: Path | str,
    instance: Instance,
    solution: Solution,
    config: Config,
    *,
    violations: Sequence[Violation] = (),
    slacks: Sequence[SlackReport] = (),
    findings: Sequence[Finding] = (),
    stats: dict[str, Any] | None = None,
) -> Path:
    """Workbook: timetables per professor / room / conflict group, assignments, satisfaction,
    violations and slacks, diagnostics and solver statistics."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tt = timetable_rows(instance, solution)
    cols = (
        list(tt[0])
        if tt
        else ["professor_id", "course_id", "section_label", "pattern_id", "room_id"]
    )
    sheets: dict[str, pd.DataFrame] = {}
    if solution.placements is not None:
        sheets["by_professor"] = _sorted_frame(tt, ["professor_id", "course_id"], cols)
        sheets["by_room"] = _sorted_frame(tt, ["room_id", "pattern_id"], cols)
        group_rows = [
            {"group_id": g.id, **row}
            for g in conflict_groups(instance, config)
            for row in tt
            if row["course_id"] in g.course_ids
        ]
        sheets["by_conflict_group"] = _sorted_frame(
            group_rows, ["group_id", "pattern_id"], ["group_id", *cols]
        )
    sheets["assignments"] = pd.DataFrame(assignment_records(solution.assignments))
    sheets["satisfaction"] = pd.DataFrame(
        [
            {
                "professor_id": m.professor_id,
                "sections": m.sections,
                "load": m.load,
                "load_min": m.load_min,
                "load_max": m.load_max,
                "course_ranks_received": ", ".join(
                    "-" if r is None else str(r) for r in m.course_ranks
                ),
                "best_course_rank": m.best_course_rank,
                "sat_course": None if m.sat_course is None else round(m.sat_course, 4),
                "time_ranks_received": ", ".join(
                    "-" if r is None else str(r) for r in m.time_ranks
                ),
                "best_time_rank": m.best_time_rank,
                "sat_time": None if m.sat_time is None else round(m.sat_time, 4),
            }
            for m in professor_metrics(instance, solution, config)
        ]
    )
    sheets["violations"] = pd.DataFrame(
        [
            {
                "id": v.id,
                "severity": v.severity,
                "message": v.message,
                "size": v.size,
                "entities": ", ".join(v.entities),
            }
            for v in violations
        ],
        columns=["id", "severity", "message", "size", "entities"],
    )
    sheets["slacks"] = pd.DataFrame(
        [
            {
                "id": s.cid,
                "description": s.description,
                "value": s.value,
                "explanation": s.explanation,
                "entities": ", ".join(s.entities),
            }
            for s in slacks
        ],
        columns=["id", "description", "value", "explanation", "entities"],
    )
    sheets["diagnostics"] = pd.DataFrame(
        [{"severity": f.severity, "code": f.code, "message": f.message} for f in findings],
        columns=["severity", "code", "message"],
    )
    stat_rows: list[dict[str, Any]] = [
        {"key": k, "value": str(v)} for k, v in sorted(solution.meta.items())
    ]
    for k, v in sorted((stats or {}).items()):
        if k != "levels":
            stat_rows.append({"key": k, "value": str(v)})
    for lv in (stats or {}).get("levels", []):
        stat_rows.append(
            {"key": f"level {lv['level']} ({lv['name']}, {lv['sense']})", "value": str(lv["value"])}
        )
    sheets["solver_stats"] = pd.DataFrame(stat_rows, columns=["key", "value"])
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)
            ws = writer.sheets[name]
            for col in ws.columns:
                width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
                ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 8), 60)
    return path
