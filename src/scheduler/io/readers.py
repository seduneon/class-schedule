"""Readers: CSV folder or single .xlsx -> validated domain objects (SPEC §8)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

import pandas as pd
from pydantic import BaseModel, ValidationError

from scheduler.domain import (
    Assignment,
    BlockedSlot,
    ConflictGroup,
    CoursePreference,
    Instance,
    Offering,
    Placement,
    PreAssignment,
    Professor,
    Room,
    RoomAvailability,
    SectionLink,
    SectionType,
    Solution,
    Source,
    StageAPin,
    StageBPin,
    TimePattern,
    TimePreference,
    Unavailability,
)
from scheduler.io.schemas import (
    REQUIRED_TABLES,
    TABLES,
    AssignmentRow,
    BlockedSlotRow,
    ConflictGroupRow,
    CoursePreferenceRow,
    OfferingRow,
    PinRow,
    PreAssignmentRow,
    ProfessorRow,
    RoomAvailabilityRow,
    RoomRow,
    Row,
    SectionLinkRow,
    TimePatternRow,
    TimePreferenceRow,
    UnavailabilityRow,
)
from scheduler.time import make_meetings

R = TypeVar("R", bound=Row)


@dataclass(frozen=True)
class RowError:
    table: str
    row: int | None
    message: str

    def __str__(self) -> str:
        where = f"{self.table}" + (f" row {self.row}" if self.row is not None else "")
        return f"{where}: {self.message}"


class InputError(ValueError):
    """Raised with every row-level problem found while reading an instance."""

    def __init__(self, errors: Sequence[RowError]) -> None:
        self.errors = tuple(errors)
        super().__init__("invalid input:\n" + "\n".join(f"  - {e}" for e in self.errors))


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    frame = frame.rename(columns=lambda c: str(c).strip())
    frame = frame.dropna(how="all")
    return [
        {str(k): (None if pd.isna(v) else v) for k, v in rec.items()}
        for rec in frame.to_dict(orient="records")
    ]


def load_tables(path: Path) -> dict[str, list[dict[str, object]]]:
    """Read raw table records from a folder of CSVs or a single .xlsx workbook."""
    path = Path(path)
    out: dict[str, list[dict[str, object]]] = {}
    if path.is_dir():
        for name in TABLES:
            csv = path / f"{name}.csv"
            if csv.exists():
                out[name] = _records(pd.read_csv(csv, dtype=str, keep_default_na=False))
    elif path.suffix.lower() in (".xlsx", ".xlsm"):
        sheets = pd.read_excel(path, sheet_name=None, dtype=str)
        for name, frame in sheets.items():
            if name in TABLES:
                out[name] = _records(frame)
    else:
        raise FileNotFoundError(f"{path}: expected a folder of CSV files or an .xlsx workbook")
    return out


def parse_rows[R: Row](
    table: str, records: list[dict[str, object]], schema: type[R], errors: list[RowError]
) -> list[R]:
    """Validate each record; collect row-level errors (row numbers as in the file, header = 1)."""
    rows: list[R] = []
    for i, rec in enumerate(records):
        try:
            rows.append(schema.model_validate(rec))
        except ValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(x) for x in err["loc"]) or "row"
                errors.append(RowError(table, i + 2, f"{loc}: {err['msg']}"))
    return rows


def _check_unique(
    table: str,
    tables: dict[str, list[dict[str, object]]],
    cols: tuple[str, ...],
    errors: list[RowError],
) -> None:
    """Report rows whose key columns repeat an earlier row (row numbers as in the file)."""
    seen: dict[tuple[str, ...], int] = {}
    for i, rec in enumerate(tables.get(table, [])):
        key = tuple(str(rec.get(c) or "").strip() for c in cols)
        if key in seen:
            errors.append(
                RowError(table, i + 2, f"duplicate key {key} (first at row {seen[key] + 2})")
            )
        else:
            seen[key] = i


def build_instance(tables: dict[str, list[dict[str, object]]]) -> Instance:
    """Validate raw records and build an :class:`Instance` (raises :class:`InputError`)."""
    errors: list[RowError] = [
        RowError(name, None, "required table is missing")
        for name in REQUIRED_TABLES
        if name not in tables
    ]

    def rows(name: str, schema: type[R]) -> list[R]:
        return parse_rows(name, tables.get(name, []), schema, errors)

    profs = rows("professors", ProfessorRow)
    offers = rows("offerings", OfferingRow)
    rooms = rows("rooms", RoomRow)
    room_avail = rows("room_availability", RoomAvailabilityRow)
    pats = rows("time_patterns", TimePatternRow)
    cprefs = rows("course_preferences", CoursePreferenceRow)
    tprefs = rows("time_preferences", TimePreferenceRow)
    unav = rows("unavailability", UnavailabilityRow)
    blocked = rows("blocked_slots", BlockedSlotRow)
    pre = rows("pre_assignments", PreAssignmentRow)
    groups = rows("conflict_groups", ConflictGroupRow)
    pins = rows("pins", PinRow)
    links = rows("section_links", SectionLinkRow)

    for name, cols in (
        ("professors", ("professor_id",)),
        ("rooms", ("room_id",)),
        ("time_patterns", ("pattern_id",)),
        ("course_preferences", ("professor_id", "course_id", "section_type")),
        ("room_availability", ("room_id", "pattern_id")),
        ("time_preferences", ("professor_id", "pattern_id")),
        ("conflict_groups", ("group_id", "course_id")),
    ):
        _check_unique(name, tables, cols, errors)
    _check_offering_consistency(offers, errors)
    _check_group_settings(groups, errors)
    if errors:
        raise InputError(errors)

    group_rows: dict[str, list[ConflictGroupRow]] = {}
    for g in groups:
        group_rows.setdefault(g.group_id, []).append(g)

    return Instance(
        professors=tuple(
            Professor(
                id=r.professor_id,
                name=r.name,
                load_min=r.load_min,
                load_max=r.load_max,
                priority=r.priority,
                max_preps=r.max_preps,
                max_days=r.max_days,
                multi_section_pref=r.multi_section_pref,
                schedule_style=r.schedule_style,
                day_families=r.day_families,
                day_family_mixing=r.day_family_mixing,
            )
            for r in sorted(profs, key=lambda r: r.professor_id)
        ),
        offerings=tuple(
            Offering(
                course_id=r.course_id,
                title=r.title,
                level=r.level,
                section_type=r.section_type,
                num_sections=r.num_sections,
                capacity=r.capacity,
                units=r.effective_units,
                room_type=r.room_type,
            )
            for r in offers
        ),
        rooms=tuple(
            Room(r.room_id, r.building, r.capacity, r.room_type)
            for r in sorted(rooms, key=lambda r: r.room_id)
        ),
        patterns=tuple(
            TimePattern(
                r.pattern_id, make_meetings(r.days, r.start, r.end), r.allowed_section_types
            )
            for r in sorted(pats, key=lambda r: r.pattern_id)
        ),
        course_preferences=tuple(
            CoursePreference(r.professor_id, r.course_id, r.rank, r.section_type) for r in cprefs
        ),
        time_preferences=tuple(
            TimePreference(r.professor_id, r.pattern_id, r.rank) for r in tprefs
        ),
        unavailability=tuple(
            Unavailability(r.professor_id, r.day, r.start, r.end, r.reason) for r in unav
        ),
        blocked_slots=tuple(BlockedSlot(r.day, r.start, r.end, r.reason) for r in blocked),
        pre_assignments=tuple(
            PreAssignment(r.professor_id, r.course_id, r.section_type, r.count, r.labels)
            for r in pre
        ),
        conflict_groups=tuple(
            ConflictGroup(
                id=gid,
                course_ids=frozenset(r.course_id for r in grs),
                mode=grs[0].mode,
                weight=grs[0].weight,
            )
            for gid, grs in sorted(group_rows.items())
        ),
        stage_a_pins=tuple(
            StageAPin(r.professor_id or "", r.course_id, r.section_type, r.count or 0)
            for r in pins
            if r.count is not None
        ),
        stage_b_pins=tuple(
            StageBPin(r.course_id, r.section_type, r.section_label or "", r.pattern_id, r.room_id)
            for r in pins
            if r.section_label is not None
        ),
        section_links=tuple(
            SectionLink(r.course_id, r.recitation_label, r.lecture_label) for r in links
        ),
        room_availability=tuple(
            RoomAvailability(r.room_id, r.pattern_id)
            for r in sorted(room_avail, key=lambda r: (r.room_id, r.pattern_id))
        ),
    )


def _check_offering_consistency(offers: list[OfferingRow], errors: list[RowError]) -> None:
    """All rows of one (course, type) must agree on units; all rows of a course on level/title."""
    units: dict[tuple[str, SectionType], float] = {}
    course: dict[str, tuple[int, str]] = {}
    for i, r in enumerate(offers):
        key = (r.course_id, r.section_type)
        if key in units and units[key] != r.effective_units:
            errors.append(RowError("offerings", i + 2, f"units differ between rows of {key}"))
        units.setdefault(key, r.effective_units)
        if r.course_id in course and course[r.course_id] != (r.level, r.title):
            errors.append(RowError("offerings", i + 2, f"level/title differ for {r.course_id}"))
        course.setdefault(r.course_id, (r.level, r.title))


def _check_group_settings(groups: list[ConflictGroupRow], errors: list[RowError]) -> None:
    first: dict[str, tuple[str | None, float | None]] = {}
    for i, g in enumerate(groups):
        settings = (g.mode, g.weight)
        if g.group_id in first and first[g.group_id] != settings:
            errors.append(
                RowError("conflict_groups", i + 2, f"mode/weight differ within group {g.group_id}")
            )
        first.setdefault(g.group_id, settings)


def read_instance(path: Path | str) -> Instance:
    """Read and validate an instance from a CSV folder or .xlsx workbook."""
    return build_instance(load_tables(Path(path)))


def read_assignments(path: Path | str) -> tuple[Assignment, ...]:
    """Read the Stage A hand-off file (CSV or .xlsx, SPEC §5.4)."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        return read_solution(path).assignments
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        sheets = pd.read_excel(path, sheet_name=None, dtype=str)
        frame = sheets.get("assignments", next(iter(sheets.values())))
    else:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    errors: list[RowError] = []
    rows = parse_rows("assignments", _records(frame), AssignmentRow, errors)
    if errors:
        raise InputError(errors)
    return tuple(
        Assignment(
            r.professor_id,
            r.course_id,
            r.section_type,
            r.section_label,
            r.capacity,
            r.units,
            r.source,
        )
        for r in rows
    )


class _SolutionFile(BaseModel):
    assignments: list[dict[str, object]]
    placements: list[dict[str, object]] | None = None
    meta: dict[str, object] = {}


def solution_from_dict(data: dict[str, object]) -> Solution:
    """Parse the canonical JSON solution format (SPEC L6)."""
    raw = _SolutionFile.model_validate(data)
    assignments = tuple(
        Assignment(
            professor_id=str(a["professor_id"]),
            course_id=str(a["course_id"]),
            section_type=SectionType(str(a["section_type"])),
            section_label=str(a["section_label"]),
            capacity=int(str(a["capacity"])),
            units=float(str(a["units"])),
            source=Source(str(a.get("source", "manual"))),
        )
        for a in raw.assignments
    )
    placements = (
        None
        if raw.placements is None
        else tuple(
            Placement(
                course_id=str(p["course_id"]),
                section_type=SectionType(str(p["section_type"])),
                section_label=str(p["section_label"]),
                pattern_id=str(p["pattern_id"]),
                room_id=str(p["room_id"]),
            )
            for p in raw.placements
        )
    )
    return Solution(assignments, placements, dict(raw.meta))


def read_solution(path: Path | str) -> Solution:
    """Read a JSON solution file."""
    with Path(path).open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return solution_from_dict(data)
