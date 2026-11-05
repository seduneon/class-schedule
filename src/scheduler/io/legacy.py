"""Legacy converter: the supervisor's wide Excel files -> SPEC §8 tables (SPEC §8.1).

Inputs (one folder, never modified): ``courses.xlsx``, ``professors.xlsx``,
``preferences.xlsx`` (the Qualtrics export) and, optionally, ``time_room.xlsx``.
Corrections live in a separate fixes file (SPEC §8.1.2). Only the layout differences of
SPEC §8.1.1 (T1-T4) are tolerated; anything else is an error naming file, row and column.
Everything that needs a human decision goes to ``review.csv``; free text is never
interpreted.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, NoReturn

import openpyxl
import yaml
from openpyxl.utils import column_index_from_string, get_column_letter
from pydantic import BaseModel, ConfigDict, ValidationError

from scheduler.domain import SectionType
from scheduler.io.readers import InputError, RowError
from scheduler.io.schemas import DEFAULT_UNITS, TABLES, day_family

Record = dict[str, object]

_SLOT = re.compile(
    r"^(?P<days>[MTWRFSU ]+?)\s*(?P<start>\d{1,2}:\d{2}\s*[AP]M)\s*-\s*(?P<end>\d{1,2}:\d{2}\s*[AP]M)$",
    re.IGNORECASE,
)
_TIME = re.compile(r"^(?P<start>\d{1,2}:\d{2}\s*[AP]M)\s*-\s*(?P<end>\d{1,2}:\d{2}\s*[AP]M)$", re.I)
_RECITATION = re.compile(r"recitation|reciation", re.IGNORECASE)
_CODE = re.compile(r"^(?P<code>[A-Z]{2,5} ?\d{3}(?: ?/ ?\d{3})*(?: ?\([^)]*\))?)", re.IGNORECASE)
"""Leading course code of a survey Q1 label, with an optional cross-listing (SPEC §8.1)."""

HEADER_ROWS = 5
"""T1: the header is searched for in the first rows only."""
ANCHORS = {
    "courses.xlsx": "Course_code",
    "professors.xlsx": "first_name",
    "preferences.xlsx": "ResponseId",
    "time_room.xlsx": "room",
}
"""T1: the column name that marks each file's header row."""
COLUMNS = {
    "courses.xlsx": ("Course_code", "Course_title", "Section_number", "Section_type", "Capacity"),
    "professors.xlsx": ("first_name", "second_name", "load"),
    "preferences.xlsx": ("ResponseId", "RecordedDate", "RecipientLastName", "RecipientEmail"),
    "time_room.xlsx": ("day", "time", "room", "cap"),
}
"""Columns each file must have (found by name, in any order: T2)."""

MULTI_SECTION = {1: 1, 2: -1, 3: 0}
"""Survey Q2 choice -> multi_section_pref (Yes / No / No preference)."""
DAY_CHOICE = {
    1: ("MWF", "forbid"),
    2: ("TR", "forbid"),
    3: ("MWF;TR", "forbid"),
    4: ("MWF;TR", "allow"),
}
"""Survey Q3 choice -> (day_families, day_family_mixing); answers 1-3 never mix (D11)."""
BREAK_CHOICE = {1: "spread", 2: "none"}
"""Survey Q6 choice -> schedule_style."""


# ----- fixes file (SPEC §8.1.2) ------------------------------------------------------------


class SurveyColumnFix(BaseModel):
    """Meaning of a survey column whose header is empty."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    question: Literal["Q1"]
    course: str


class Fixes(BaseModel):
    """Declared corrections for one data source; every applied fix is a review row."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    courses_format: Literal["per_section", "per_course"] = "per_section"
    course_aliases: dict[str, str] = {}
    survey_columns: dict[str, SurveyColumnFix] = {}
    time_patterns_from_survey: bool = False


def load_fixes(path: Path | str) -> Fixes:
    """Read and validate a fixes file (unknown keys are errors)."""
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise InputError([RowError(str(path), None, "expected a mapping of fixes")])
    try:
        return Fixes.model_validate(data)
    except ValidationError as exc:
        raise InputError(
            [
                RowError(str(path), None, f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}")
                for e in exc.errors()
            ]
        ) from exc


# ----- small helpers -----------------------------------------------------------------------


@dataclass(frozen=True)
class ExtraOffering:
    """``--add-offering COURSE:TYPE:N:CAP``: sections missing from ``courses.xlsx``."""

    course_id: str
    section_type: SectionType
    num_sections: int
    capacity: int

    @classmethod
    def parse(cls, text: str) -> ExtraOffering:
        parts = [p.strip() for p in text.split(":")]
        if len(parts) != 4:
            raise ValueError(f"expected COURSE:TYPE:N:CAP, got {text!r}")
        course, kind, n, cap = parts
        return cls(course_id(course), SectionType(kind.upper()), int(n), int(cap))


@dataclass
class LegacyResult:
    """Converted tables (SPEC §8) plus the rows a human must review."""

    tables: dict[str, list[Record]]
    review: list[Record] = field(default_factory=list)


def _str(v: object) -> str:
    return "" if v is None else str(v).strip()


def _norm(v: object) -> str:
    """T3: trimmed, runs of spaces and tabs as one space."""
    return re.sub(r"\s+", " ", _str(v))


def _num(v: object) -> float | None:
    text = _str(v)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def course_id(code: str) -> str:
    """Course ID from a code: no spaces, no cross-listing part (SPEC §8.1, D14).

    ``MATH 571 (MATH 721)`` -> ``MATH571``; ``MATH 702/682`` -> ``MATH702``.
    """
    return _norm(code).split("(")[0].split("/")[0].replace(" ", "")


def _slash_listed(code: str) -> bool:
    """``MATH 702/682``: the title keeps the full code (D14)."""
    return "/" in code


def clock_24(text: str) -> str:
    """``01:30 PM`` -> ``13:30``."""
    t = datetime.strptime(_norm(text).upper(), "%I:%M %p")
    return t.strftime("%H:%M")


def pattern_id(family: str, start: str) -> str:
    """Pattern ID from family and 24-hour start, e.g. ``MWF0900``."""
    return f"{family}{start.replace(':', '')}"


def _rev(kind: str, professor_id: str, detail: str) -> Record:
    return {"kind": kind, "professor_id": professor_id, "detail": detail}


def _fail(file: str, row: int | None, message: str) -> NoReturn:
    raise InputError([RowError(file, row, message)])


def _sheet(path: Path) -> list[tuple[Any, ...]]:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        return [tuple(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    finally:
        wb.close()


@dataclass
class _Ctx:
    """Fixes being applied, which aliases were used, and the review rows so far."""

    fixes: Fixes
    review: list[Record] = field(default_factory=list)
    used_aliases: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.aliases = {_norm(k): v for k, v in self.fixes.course_aliases.items()}

    def course(self, raw: str) -> str:
        """Course ID of a raw code, via ``course_aliases`` first."""
        key = _norm(raw)
        if key in self.aliases:
            if key not in self.used_aliases:
                self.review.append(
                    _rev("fix", "", f"course code {key!r} read as {self.aliases[key]} (alias)")
                )
            self.used_aliases.add(key)
            return self.aliases[key]
        return course_id(key)


# ----- tables with the T1-T4 tolerances (SPEC §8.1.1) --------------------------------------


@dataclass(frozen=True)
class _Table:
    file: str
    header: tuple[str, ...]
    rows: tuple[tuple[int, tuple[Any, ...]], ...]  # (Excel row number, values), blanks skipped

    def records(self) -> list[dict[str, Any]]:
        out = []
        for number, values in self.rows:
            rec = {h: v for h, v in zip(self.header, values, strict=False) if h}
            rec["_row"] = number
            out.append(rec)
        return out


def _header_index(rows: list[tuple[Any, ...]], file: str) -> int:
    """T1: the first of the first HEADER_ROWS rows that contains the file's anchor."""
    anchor = ANCHORS[file]
    for i, row in enumerate(rows[:HEADER_ROWS]):
        if any(_norm(v) == anchor for v in row):
            return i
    _fail(file, None, f"no header row: {anchor!r} not found in the first {HEADER_ROWS} rows")


def _table(
    rows: list[tuple[Any, ...]], file: str, skip: int = 0, fixed: frozenset[int] = frozenset()
) -> _Table:
    """Header by anchor (T1), columns by name (T2), blank rows skipped (T4).

    ``skip`` rows below the header are not data (the survey's question texts); columns in
    ``fixed`` have an empty header that the fixes file names.
    """
    h = _header_index(rows, file)
    header = tuple(_norm(v) for v in rows[h])
    for name in COLUMNS[file]:
        if name not in header:
            _fail(file, h + 1, f"missing column {name!r}")
    data = []
    for i, values in enumerate(rows[h + 1 + skip :]):
        if not any(_str(v) for v in values):
            continue
        number = h + 2 + skip + i
        for j, v in enumerate(values):
            unnamed = j >= len(header) or not header[j]
            if unnamed and _str(v) and j not in fixed:
                _fail(
                    file,
                    number,
                    f"column {get_column_letter(j + 1)} has data but no header "
                    "(name it in the fixes file, SPEC §8.1.2)",
                )
        data.append((number, values))
    return _Table(file, header, tuple(data))


# ----- courses, rooms, patterns ------------------------------------------------------------


def _offerings(table: _Table, ctx: _Ctx, extra: tuple[ExtraOffering, ...]) -> list[Record]:
    per_course = ctx.fixes.courses_format == "per_course"
    if per_course:
        ctx.review.append(
            _rev("fix", "", "courses.xlsx read per course: Section_number = number of sections")
        )
    counts: Counter[tuple[str, str, int]] = Counter()
    titles: dict[str, str] = {}
    numbers: dict[tuple[str, str], list[float | None]] = {}
    for r in table.records():
        raw = _norm(r["Course_code"])
        cid = ctx.course(raw)
        kind = _norm(r["Section_type"]).upper()
        key = (cid, kind, int(_num(r["Capacity"]) or 0))
        number = _num(r["Section_number"])
        if per_course:
            if number is None or number < 1 or number != int(number):
                _fail(
                    table.file,
                    r["_row"],
                    "Section_number must be a positive whole number of sections "
                    "(courses_format: per_course)",
                )
            if key in counts:
                _fail(
                    table.file,
                    r["_row"],
                    f"{raw} {kind} capacity {key[2]} appears twice (courses_format: per_course)",
                )
            counts[key] += int(number)
        else:
            counts[key] += 1
            numbers.setdefault((cid, kind), []).append(number)
        title = _norm(r["Course_title"])
        titles.setdefault(cid, f"{title} ({raw})" if _slash_listed(raw) else title)
    looks_per_course = sorted(
        f"{c} {k} (Section_number {n:g})"
        for (c, k), nums in numbers.items()
        if len(nums) == 1 and (n := nums[0]) is not None and n > 1
    )
    if looks_per_course:
        _fail(
            table.file,
            None,
            "looks like one row per course: " + ", ".join(looks_per_course) + " appear once "
            "with Section_number > 1; set courses_format in the fixes file (SPEC §8.1.2)",
        )
    for e in extra:
        counts[(e.course_id, e.section_type.value, e.capacity)] += e.num_sections
    out: list[Record] = []
    for (cid, kind, cap), n in sorted(counts.items()):
        digits = "".join(ch for ch in cid if ch.isdigit())
        out.append(
            {
                "course_id": cid,
                "title": titles.get(cid, cid),
                "level": int(digits[0]) * 100 if digits else 0,
                "section_type": kind,
                "num_sections": n,
                "capacity": cap,
                "units": DEFAULT_UNITS[SectionType(kind)],
                "room_type": "classroom",
            }
        )
    return out


@dataclass(frozen=True)
class _Slot:
    family: str
    start: str
    end: str

    @property
    def id(self) -> str:
        return pattern_id(self.family, self.start)


def _slot(days: str, time_range: str) -> _Slot:
    m = _TIME.match(_norm(time_range))
    if m is None:
        raise ValueError(f"cannot parse time range {time_range!r}")
    return _Slot(day_family(days.replace(" ", "")), clock_24(m["start"]), clock_24(m["end"]))


def _pattern_rows(slots: list[_Slot]) -> list[Record]:
    unique = {s.id: s for s in slots}
    return [
        {
            "pattern_id": s.id,
            "days": s.family,
            "start": s.start,
            "end": s.end,
            "allowed_section_types": "L;R",
        }
        for s in sorted(unique.values(), key=lambda s: s.id)
    ]


def _time_room(table: _Table, review: list[Record]) -> dict[str, list[Record]]:
    slots: list[_Slot] = []
    rooms: dict[str, int] = {}
    pairs: set[tuple[str, str]] = set()
    for r in table.records():
        if not _str(r.get("room")):
            continue
        try:
            slot = _slot(_norm(r["day"]), _norm(r["time"]))
        except ValueError as exc:
            _fail(table.file, r["_row"], str(exc))
        slots.append(slot)
        rid = _str(r["room"])
        cap = int(_num(r["cap"]) or 0)
        if rid in rooms and rooms[rid] != cap:
            review.append(
                _rev("room_capacity", "", f"room {rid}: capacities {rooms[rid]} and {cap}")
            )
        rooms[rid] = max(cap, rooms.get(rid, 0))
        pairs.add((rid, slot.id))
    return {
        "time_patterns": _pattern_rows(slots),
        "rooms": [
            {
                "room_id": rid,
                "building": rid.split(".")[0] if "." in rid else rid,
                "capacity": cap,
                "room_type": "classroom",
            }
            for rid, cap in sorted(rooms.items())
        ],
        "room_availability": [{"room_id": r, "pattern_id": t} for r, t in sorted(pairs)],
    }


# ----- professors --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Prof:
    id: str
    first: str
    last: str
    email: str
    mwf_or_tr: bool = False  # MWForTR = 1; only reported, never applied (SPEC §8.1, D9)


def _professor_id(first: str, last: str, email: str) -> str:
    if email:
        return email.split("@")[0].lower()
    return re.sub(r"[^a-z0-9]+", ".", f"{first} {last}".lower()).strip(".")


def _professors(table: _Table, ctx: _Ctx) -> tuple[list[Record], list[Record], list[_Prof]]:
    profs: list[Record] = []
    pre: list[Record] = []
    who: list[_Prof] = []
    for r in table.records():
        first, last, email = _norm(r["first_name"]), _norm(r["second_name"]), _str(r.get("email"))
        if not (first or last):
            continue
        pid = _professor_id(first, last, email)
        load = _num(r.get("load")) or 0.0
        cpts, tpts = _num(r.get("course_points")), _num(r.get("time_points"))
        if cpts is not None and tpts is not None and cpts != tpts:
            ctx.review.append(
                _rev(
                    "priority",
                    pid,
                    f"course_points {cpts:g} != time_points {tpts:g}; used course_points",
                )
            )
        profs.append(
            {
                "professor_id": pid,
                "name": f"{first} {last}".strip(),
                "load_min": load,
                "load_max": load,
                "priority": (cpts or 100.0) / 100.0,
                # MWForTR is ignored: survey Q3 asks the professor directly (SPEC §8.1, D9)
                "day_family_mixing": "allow",
            }
        )
        who.append(_Prof(pid, first, last, email.lower(), _num(r.get("MWForTR")) == 1))
        for i in range(1, 10):
            course = _norm(r.get(f"course{i}"))
            if not course:
                continue
            section = _str(r.get(f"section{i}"))
            label = f"{int(float(section))}L" if _num(section) is not None else ""
            pre.append(
                {
                    "professor_id": pid,
                    "course_id": ctx.course(course),
                    "section_type": "L",
                    "count": 1,
                    "section_label": label,
                }
            )
    return profs, pre, who


# ----- survey ------------------------------------------------------------------------------

SURVEY = "preferences.xlsx"


@dataclass(frozen=True)
class _Column:
    index: int
    question: str  # Q1, Q2, ...
    course: str = ""
    recitation: bool = False
    slot: _Slot | None = None


def _q1_column(index: int, label: str, ctx: _Ctx) -> _Column:
    """A Q1 column from its label ``CODE title``: code and title split by tab or spaces."""
    m = _CODE.match(_norm(label))
    if m is None:
        _fail(SURVEY, None, f"column {get_column_letter(index + 1)}: no course code in {label!r}")
    return _Column(index, "Q1", ctx.course(m["code"]), bool(_RECITATION.search(label)))


def _fixed_columns(codes: tuple[Any, ...], ctx: _Ctx) -> dict[int, SurveyColumnFix]:
    """``survey_columns`` by 0-based index; a fix for a column that has a header is stale."""
    out: dict[int, SurveyColumnFix] = {}
    for letter, fix in sorted(ctx.fixes.survey_columns.items()):
        try:
            index = column_index_from_string(letter.strip().upper()) - 1
        except ValueError:
            _fail(SURVEY, None, f"survey_columns: {letter!r} is not an Excel column letter")
        if index >= len(codes):
            _fail(SURVEY, None, f"survey_columns: column {letter} does not exist")
        if _str(codes[index]):
            _fail(
                SURVEY,
                None,
                f"survey_columns: column {letter} now has the header {_str(codes[index])!r}; "
                "remove the stale fix",
            )
        out[index] = fix
    return out


def _survey_columns(
    codes: tuple[Any, ...], texts: tuple[Any, ...], fixed: dict[int, SurveyColumnFix], ctx: _Ctx
) -> list[_Column]:
    out = []
    for i, code in enumerate(codes):
        if i in fixed:
            ctx.review.append(
                _rev(
                    "fix",
                    "",
                    f"{SURVEY} column {get_column_letter(i + 1)} (no header) read as "
                    f"{fixed[i].question} ranks for {fixed[i].course}",
                )
            )
            out.append(_q1_column(i, fixed[i].course, ctx))
            continue
        q = _norm(code)
        if not re.match(r"^Q\d+(_\d+)?$", q):
            continue
        text = _str(texts[i] if i < len(texts) else "")
        tail = text.rsplit(" - ", 1)[-1].strip()
        question = q.split("_")[0]
        if question == "Q1":
            out.append(_q1_column(i, tail, ctx))
        elif question in ("Q4", "Q5"):
            m = _SLOT.match(_norm(tail))
            slot = _slot(m["days"], f"{m['start']}-{m['end']}") if m else None
            out.append(_Column(i, question, slot=slot))
        else:
            out.append(_Column(i, question))
    return out


def _match(resp: dict[str, str], who: list[_Prof]) -> tuple[_Prof | None, str]:
    email = resp["email"].lower()
    for p in who:
        if email and p.email == email:
            return p, ""
    same_last = [p for p in who if p.last.lower() == resp["last"].lower()]
    if len(same_last) == 1:
        return same_last[0], "survey response matched by last name (no e-mail match)"
    return None, ""


@dataclass
class _Survey:
    overrides: dict[str, Record]
    course_prefs: list[Record]
    time_prefs: list[Record]
    columns: list[_Column]


def _latest_responses(
    table: _Table, who: list[_Prof], ctx: _Ctx
) -> dict[str, tuple[datetime, dict[str, Any], tuple[Any, ...]]]:
    """Per professor: the latest response (review rows for every non-exact match)."""
    latest: dict[str, tuple[datetime, dict[str, Any], tuple[Any, ...]]] = {}
    for (_n, values), rec in zip(table.rows, table.records(), strict=True):
        rid = _str(rec.get("ResponseId"))
        if not rid.startswith("R_"):
            continue
        if _norm(rec.get("DistributionChannel")).lower() == "preview":
            ctx.review.append(_rev("preview_response", "", f"response {rid} is a survey preview"))
            continue
        resp = {"email": _str(rec.get("RecipientEmail")), "last": _norm(rec["RecipientLastName"])}
        prof, note = _match(resp, who)
        if prof is None:
            ctx.review.append(
                _rev("unmatched_response", "", f"response {rid} matches no professor")
            )
            continue
        if note:
            ctx.review.append(_rev("name_match", prof.id, note))
        when = rec["RecordedDate"]
        stamp = when if isinstance(when, datetime) else datetime.min
        if prof.id in latest:
            ctx.review.append(
                _rev("duplicate_response", prof.id, "answered twice; latest response used")
            )
            if stamp <= latest[prof.id][0]:
                continue
        latest[prof.id] = (stamp, rec, values)
    return latest


def _survey(rows: list[tuple[Any, ...]], who: list[_Prof], ctx: _Ctx) -> _Survey:
    """Per professor: professor-table overrides, course and time preference rows."""
    h = _header_index(rows, SURVEY)
    codes = rows[h]
    texts = rows[h + 1] if h + 1 < len(rows) else ()
    fixed = _fixed_columns(codes, ctx)
    table = _table(rows, SURVEY, skip=1, fixed=frozenset(fixed))
    cols = _survey_columns(codes, texts, fixed, ctx)
    rec_courses = {c.course for c in cols if c.question == "Q1" and c.recitation}
    latest = _latest_responses(table, who, ctx)

    overrides: dict[str, Record] = {}
    cprefs: list[Record] = []
    tprefs: list[Record] = []
    for pid in sorted(latest):
        values = latest[pid][2]
        over: Record = {}
        for col in cols:
            raw = values[col.index] if col.index < len(values) else None
            value = _num(raw)
            if col.question == "Q1" and value is not None:
                kind = "R" if col.recitation else ("L" if col.course in rec_courses else "")
                cprefs.append(
                    {
                        "professor_id": pid,
                        "course_id": col.course,
                        "section_type": kind,
                        "rank": int(value),
                    }
                )
            elif col.question in ("Q4", "Q5") and value is not None and col.slot is not None:
                tprefs.append({"professor_id": pid, "pattern_id": col.slot.id, "rank": int(value)})
            elif col.question == "Q2" and value is not None:
                over["multi_section_pref"] = MULTI_SECTION.get(int(value), 0)
            elif col.question == "Q3" and value is not None:
                fams, mix = DAY_CHOICE.get(int(value), ("", "allow"))
                over["day_families"], over["day_family_mixing"] = fams, mix
            elif col.question == "Q6" and value is not None:
                over["schedule_style"] = BREAK_CHOICE.get(int(value), "none")
            elif col.question == "Q7" and _str(raw):
                ctx.review.append(_rev("comment", pid, _str(raw)))
        overrides[pid] = over
    return _Survey(overrides, cprefs, tprefs, cols)


def _survey_vs_courses(survey: _Survey, offerings: list[Record], ctx: _Ctx) -> None:
    """Review rows for Q1 courses that are not offered and offered courses without Q1."""
    ranked = {c.course for c in survey.columns if c.question == "Q1"}
    offered = {str(o["course_id"]) for o in offerings}
    for c in sorted(ranked - offered):
        ctx.review.append(_rev("survey_course", "", f"survey Q1 ranks {c}, which is not offered"))
    for c in sorted(offered - ranked):
        ctx.review.append(
            _rev("survey_course", "", f"{c} is offered but has no survey Q1 column (no ranks)")
        )


# ----- entry points ------------------------------------------------------------------------

ROOM_TABLES = ("time_patterns", "rooms", "room_availability")


def _rooms_and_patterns(folder: Path, survey: _Survey, ctx: _Ctx) -> dict[str, list[Record]]:
    """``time_room`` tables, or (absent) survey slots if declared, with review rows."""
    path = folder / "time_room.xlsx"
    if path.exists():
        if ctx.fixes.time_patterns_from_survey:
            _fail(
                "time_room.xlsx",
                None,
                "exists, so time_patterns_from_survey is stale; remove it from the fixes file",
            )
        return _time_room(_table(_sheet(path), "time_room.xlsx"), ctx.review)
    if ctx.fixes.time_patterns_from_survey:
        slots = [c.slot for c in survey.columns if c.slot is not None]
        ctx.review.append(
            _rev(
                "fix",
                "",
                f"no time_room.xlsx: {len({s.id for s in slots})} time patterns taken from the "
                "survey Q4/Q5 slots (allowed section types L;R)",
            )
        )
        missing = "rooms, room_availability"
        tables = {"time_patterns": _pattern_rows(slots)}
    else:
        missing, tables = "time_patterns, rooms, room_availability", {}
    ctx.review.append(
        _rev(
            "missing_table",
            "",
            f"no time_room.xlsx: no {missing} table; Stage B (times and rooms) cannot run",
        )
    )
    return tables


def convert_legacy(
    folder: Path | str,
    extra: tuple[ExtraOffering, ...] = (),
    anonymize: bool = False,
    fixes: Fixes | None = None,
) -> LegacyResult:
    """Convert a legacy folder (SPEC §8.1) with the given fixes (§8.1.2); ``anonymize``
    renames professors ``P01, ...``."""
    folder = Path(folder)
    ctx = _Ctx(fixes or Fixes())
    courses = _table(_sheet(folder / "courses.xlsx"), "courses.xlsx")
    profs, pre, who = _professors(
        _table(_sheet(folder / "professors.xlsx"), "professors.xlsx"), ctx
    )
    survey = _survey(_sheet(folder / SURVEY), who, ctx)
    offerings = _offerings(courses, ctx, extra)
    _survey_vs_courses(survey, offerings, ctx)
    flagged = {w.id for w in who if w.mwf_or_tr}
    for p in profs:
        pid = str(p["professor_id"])
        over = survey.overrides.get(pid)
        if over is None:
            ctx.review.append(_rev("no_response", pid, "no survey response; no preferences"))
        else:
            p.update(over)
        if pid in flagged and (over is None or "day_family_mixing" not in over):
            ctx.review.append(_rev("mwfortr", pid, "MWForTR = 1 ignored; survey Q3 unanswered"))
    tables: dict[str, list[Record]] = {
        "professors": profs,
        "offerings": offerings,
        **_rooms_and_patterns(folder, survey, ctx),
        "course_preferences": survey.course_prefs,
        "time_preferences": survey.time_prefs,
        "pre_assignments": pre,
    }
    stale = sorted(set(ctx.aliases) - ctx.used_aliases)
    if stale:
        _fail("fixes", None, f"course_aliases never used (stale): {', '.join(stale)}")
    result = LegacyResult(tables, ctx.review)
    return _anonymized(result) if anonymize else result


def _anonymized(result: LegacyResult) -> LegacyResult:
    """Replace professor IDs and names; drop e-mail-derived IDs and free-text comments."""
    # numbered in hash order, not alphabetically, so P01.. does not follow the staff list
    ids = sorted(
        (str(p["professor_id"]) for p in result.tables["professors"]),
        key=lambda pid: hashlib.sha256(pid.encode()).hexdigest(),
    )
    width = max(2, len(str(len(ids))))
    new = {pid: f"P{i + 1:0{width}d}" for i, pid in enumerate(ids)}
    tables: dict[str, list[Record]] = {}
    for name, records in result.tables.items():
        out = []
        for rec in records:
            rec = dict(rec)
            if "professor_id" in rec:
                rec["professor_id"] = new[str(rec["professor_id"])]
            if name == "professors":
                rec["name"] = f"Professor {str(rec['professor_id'])[1:]}"
            out.append(rec)
        if name == "professors":
            out.sort(key=lambda r: str(r["professor_id"]))
        tables[name] = out
    review = [
        {**r, "professor_id": new.get(str(r["professor_id"]), "")}
        for r in result.review
        if r["kind"] not in ("comment", "unmatched_response")
    ]
    return LegacyResult(tables, review)


def write_legacy(result: LegacyResult, out: Path | str) -> Path:
    """Write the converted tables as CSV files plus ``review.csv``.

    Empty tables are not written, and a table CSV left over from an earlier conversion
    into the same folder is removed, so an absent table stays absent (SPEC D13).
    """
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    written = set()
    for name, records in result.tables.items():
        if records:
            _write_csv(out / f"{name}.csv", records)
            written.add(name)
    for name in TABLES:
        if name not in written and (out / f"{name}.csv").exists():
            (out / f"{name}.csv").unlink()
    _write_csv(out / "review.csv", result.review, ("kind", "professor_id", "detail"))
    return out


def _write_csv(path: Path, records: list[Record], columns: tuple[str, ...] = ()) -> None:
    cols = list(columns)
    for rec in records:
        cols += [k for k in rec if k not in cols]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        for rec in records:
            writer.writerow({k: rec.get(k, "") for k in cols})
