"""Legacy converter (SPEC §8.1) on a synthetic legacy folder (no real data)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import openpyxl
import pytest
from typer.testing import CliRunner

from scheduler.cli import app
from scheduler.domain import FamilyMixing, ScheduleStyle, SectionType
from scheduler.io import InputError, read_instance
from scheduler.io.legacy import (
    ExtraOffering,
    Fixes,
    convert_legacy,
    course_id,
    load_fixes,
    write_legacy,
)


def _xlsx(path: Path, rows: list[list[object]]) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    for r in rows:
        ws.append(r)
    wb.save(path)


def _survey_row(
    when: datetime, last: str, first: str, email: str | None, answers: list[object]
) -> list[object]:
    meta: list[object] = [when, when, 0, "0.0.0.0", 100, 1, 1, when, f"R_{last}{when.day}"]
    return [*meta, last, first, email, None, 0, 0, "email", "EN", *answers]


META = [
    "StartDate", "EndDate", "Status", "IPAddress", "Progress", "Duration (in seconds)",
    "Finished", "RecordedDate", "ResponseId", "RecipientLastName", "RecipientFirstName",
    "RecipientEmail", "ExternalReference", "LocationLatitude", "LocationLongitude",
    "DistributionChannel", "UserLanguage",
]  # fmt: skip
Q = ["Q1_1", "Q1_2", "Q1_3", "Q1_4", "Q2", "Q3", "Q4_1", "Q4_2", "Q5_1", "Q6", "Q7"]
TEXT = [
    "Rank - MATH 161\tCalculus I",
    "Rank - MATH 161\tCalculus I Reciation",
    "Rank - MATH 351\tNumerical Methods",
    "Rank - MATH 571 (MATH 721) \tNonlinear ODE",
    "Two or more sections?",
    "Which days?",
    "Rank MWF - M W F \t09:00 AM-09:50 AM",
    "Rank MWF - M W F \t10:00 AM-10:50 AM",
    "Rank TR - T R  09:00 AM-10:15 AM",
    "Break?",
    "Leave any comments",
]


@pytest.fixture
def legacy(tmp_path: Path) -> Path:
    src = tmp_path / "legacy"
    src.mkdir()
    _xlsx(
        src / "courses.xlsx",
        [
            ["Course_code", "Course_title", "Section_number", "Section_type", "Capacity"],
            ["MATH 161", "Calculus I", 1, "L", 200],
            ["MATH 161", "Calculus I", 2, "L", 200],
            ["MATH 351", "Numerical Methods", 1, "L", 60],
            ["MATH 571 (MATH 721) ", "Nonlinear ODE", 1, "L", 30],
        ],
    )
    _xlsx(
        src / "time_room.xlsx",
        [
            ["day", "time", "room", "cap", None],
            ["M W F ", "09:00 AM-09:50 AM", "Big Hall", 200, None],
            ["M W F ", "10:00 AM-10:50 AM", "Big Hall", 200, None],
            ["M W F ", "09:00 AM-09:50 AM", "7.101", "60", None],
            ["M W F ", "10:00 AM-10:50 AM", "7.101", "60", None],
            ["T R ", "09:00 AM-10:15 AM", "7.101", "60", None],
            [None, None, None, None, None],
        ],
    )
    head = ["first_name", "second_name", "email", "load", "course_points", "time_points"]
    _xlsx(
        src / "professors.xlsx",
        [
            [*head, "MWForTR", "course1", "section1"],
            ["Ann", "Alpha", "ann.alpha@uni.edu", 2, 100, 100, 1, "MATH 351", 1],
            ["Bob", "Beta", "bob.beta@uni.edu", 1.5, 100, 50, 0, None, None],
            ["Cy", "Gamma", "cy.gamma@uni.edu", 1, 100, 100, 1, None, None],
        ],
    )
    old = datetime(2025, 9, 1)
    new = datetime(2025, 9, 2)
    _xlsx(
        src / "preferences.xlsx",
        [
            [None] * 17 + ["MATH 161", "MATH 161", "MATH 351", "MATH 571 (MATH 721) "],
            META + Q,
            [m.lower() for m in META] + TEXT,
            _survey_row(
                old, "Alpha", "Ann", "ann.alpha@uni.edu", [9, 9, 9, 9, 2, 2, 2, 1, 1, 2, None]
            ),
            _survey_row(
                new, "Alpha", "Ann", "ann.alpha@uni.edu", [2, 4, 1, 3, 1, 3, 1, 2, 1, 1, "Hi"]
            ),
            _survey_row(new, "Beta", "Bobby", None, [1, 2, 3, 4, 3, 2, 1, 2, 1, 2, None]),
            _survey_row(new, "Zeta", "Zed", "zed@uni.edu", [1, 2, 3, 4, 3, 2, 1, 2, 1, 2, None]),
        ],
    )
    return src


EXTRA = (ExtraOffering.parse("MATH 161:R:3:50"),)


def test_course_id_drops_spaces_and_cross_listing() -> None:
    assert course_id("MATH 571 (MATH 721) ") == "MATH571"
    assert ExtraOffering.parse("math161:r:3:50") == ExtraOffering("math161", SectionType.R, 3, 50)


def test_convert_round_trips_through_the_readers(legacy: Path, tmp_path: Path) -> None:
    inst = read_instance(write_legacy(convert_legacy(legacy, EXTRA), tmp_path / "out"))
    info = inst.offering_info
    assert info[("MATH161", SectionType.L)].num_sections == 2
    assert info[("MATH161", SectionType.R)].num_sections == 3
    assert info[("MATH161", SectionType.R)].units == 0.5
    assert inst.course_level["MATH571"] == 500
    assert inst.pattern_ids == ("MWF0900", "MWF1000", "TR0900")
    assert inst.room_by_id["7.101"].building == "7"
    assert inst.room_patterns["Big Hall"] == frozenset({"MWF0900", "MWF1000"})
    assert [(p.professor_id, p.course_id, p.section_labels) for p in inst.pre_assignments] == [
        ("ann.alpha", "MATH351", ("1L",))
    ]


def test_survey_mapping(legacy: Path, tmp_path: Path) -> None:
    inst = read_instance(write_legacy(convert_legacy(legacy, EXTRA), tmp_path / "out"))
    ann = inst.professor_by_id["ann.alpha"]
    # latest response wins; Q3 = either-not-mixed; MWForTR = 1 is ignored (SPEC D9)
    assert (ann.multi_section_pref, ann.schedule_style) == (1, ScheduleStyle.SPREAD)
    assert ann.day_families == frozenset({"MWF", "TR"})
    assert ann.day_family_mixing is FamilyMixing.FORBID
    assert (ann.load_min, ann.load_max, ann.priority) == (2, 2, 1.0)
    ranks = inst.course_type_rank
    assert ranks[("ann.alpha", "MATH161", SectionType.L)] == 2
    assert ranks[("ann.alpha", "MATH161", SectionType.R)] == 4
    assert ranks[("ann.alpha", "MATH351", SectionType.L)] == 1
    assert inst.time_rank[("ann.alpha", "TR0900")] == 1
    bob = inst.professor_by_id["bob.beta"]  # matched by last name; Q3 = TR only
    assert (bob.day_families, bob.multi_section_pref) == (frozenset({"TR"}), 0)
    assert "cy.gamma" not in {p for p, _c in inst.course_rank}


def test_review_rows(legacy: Path) -> None:
    review = {(r["kind"], r["professor_id"]) for r in convert_legacy(legacy, EXTRA).review}
    assert review == {
        ("duplicate_response", "ann.alpha"),
        ("comment", "ann.alpha"),
        ("name_match", "bob.beta"),
        ("priority", "bob.beta"),
        ("unmatched_response", ""),
        ("no_response", "cy.gamma"),
        ("mwfortr", "cy.gamma"),  # MWForTR = 1 without a Q3 answer (Ann has one)
    }


def test_anonymize_removes_names_ids_and_comments(legacy: Path, tmp_path: Path) -> None:
    out = write_legacy(convert_legacy(legacy, EXTRA, anonymize=True), tmp_path / "anon")
    text = " ".join(p.read_text(encoding="utf-8") for p in sorted(out.glob("*.csv")))
    for secret in ("Ann", "Alpha", "Beta", "Gamma", "uni.edu", "ann.alpha", "Hi", "Zeta"):
        assert secret not in text
    inst = read_instance(out)
    assert inst.professor_ids == ("P01", "P02", "P03")
    assert inst.professor_by_id["P01"].name == "Professor 01"


def test_cli_refuses_real_data_outside_data_private(legacy: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    res = runner.invoke(app, ["convert-legacy", str(legacy), "-o", str(tmp_path / "x")])
    assert res.exit_code != 0
    res = runner.invoke(
        app, ["convert-legacy", str(legacy), "-o", str(tmp_path / "x"), "--anonymize"]
    )
    assert res.exit_code == 0, res.output
    assert (tmp_path / "x" / "review.csv").exists()


# ----- layout tolerance and fixes (SPEC §8.1.1, §8.1.2, D12-D14) --------------------------

PER_COURSE = [
    ["Course_code", "Course_title", "Section_number", "Section_type", "Capacity", None],
    ["MATH 161", "Calculus I", 2, "L", 200, None],
    ["MATH 161", "Calculus I Recitation", 3, "R", 50, None],
    ["MATH 351", "Numerical Methods", 1, "L", 60, None],
    ["MATH 571 (MATH 721) ", "Nonlinear ODE", 1, "L", 30, None],
]


def _spring_survey(src: Path, extra_column: list[object] | None = None) -> None:
    """The Spring 2027 export: header on the first row, labels without tabs, a preview row."""
    labels = [
        "Rank - MATH 161 Calculus I",
        "Rank - MATH 161 Calculus I Recitation",
        "Rank - MATH 351  Numerical Methods",
        "Rank - MATH 702/682 Applied Functional Analysis",
        *TEXT[4:],
    ]
    when = datetime(2026, 11, 2)
    preview = _survey_row(when, "", "", None, [1, 2, 3, 4, 1, 1, 1, 2, 1, 1, None])
    preview[15] = "preview"
    rows = [
        META + Q,
        [m.lower() for m in META] + labels,
        preview,
        _survey_row(when, "Alpha", "Ann", "ann.alpha@uni.edu", [2, 4, 1, 3, 1, 3, 1, 2, 1, 1, ""]),
    ]
    if extra_column is not None:
        rows = [[*r, v] for r, v in zip(rows, extra_column, strict=True)]
    _xlsx(src / "preferences.xlsx", rows)


def _fixes(**kw: object) -> Fixes:
    return Fixes.model_validate(kw)


def test_per_course_format_and_spring_layout(legacy: Path, tmp_path: Path) -> None:
    _xlsx(legacy / "courses.xlsx", PER_COURSE)
    _spring_survey(legacy)
    result = convert_legacy(legacy, fixes=_fixes(courses_format="per_course"))
    inst = read_instance(write_legacy(result, tmp_path / "out"))
    info = inst.offering_info
    assert info[("MATH161", SectionType.L)].num_sections == 2
    assert info[("MATH161", SectionType.R)].num_sections == 3
    # T3: code and title split by spaces; D14: slash cross-listing keeps the first code
    ranks = inst.course_type_rank
    assert ranks[("ann.alpha", "MATH161", SectionType.R)] == 4
    assert ranks[("ann.alpha", "MATH351", SectionType.L)] == 1
    assert ("ann.alpha", "MATH702") in inst.course_rank
    kinds = [(r["kind"], r["detail"]) for r in result.review]
    assert ("fix", "courses.xlsx read per course: Section_number = number of sections") in kinds
    assert any(k == "preview_response" for k, _d in kinds)
    assert ("survey_course", "survey Q1 ranks MATH702, which is not offered") in kinds
    assert ("survey_course", "MATH571 is offered but has no survey Q1 column (no ranks)") in kinds


def test_slash_cross_listing_keeps_the_full_code_in_the_title(legacy: Path) -> None:
    assert course_id("MATH 702/682") == "MATH702"
    _xlsx(legacy / "courses.xlsx", [*PER_COURSE[:1], ["MATH 742/542", "Stat Prog", 1, "L", 20]])
    rows = convert_legacy(legacy, fixes=_fixes(courses_format="per_course")).tables["offerings"]
    assert [(r["course_id"], r["title"]) for r in rows] == [("MATH742", "Stat Prog (MATH 742/542)")]


def test_per_course_file_read_per_section_is_an_error(legacy: Path) -> None:
    _xlsx(legacy / "courses.xlsx", PER_COURSE)
    with pytest.raises(InputError, match="looks like one row per course: MATH161 L"):
        convert_legacy(legacy)


def test_per_course_repeated_row_is_an_error(legacy: Path) -> None:
    _xlsx(legacy / "courses.xlsx", [*PER_COURSE, PER_COURSE[1]])
    with pytest.raises(InputError, match=r"courses\.xlsx row 6: MATH 161 L capacity 200 appears"):
        convert_legacy(legacy, fixes=_fixes(courses_format="per_course"))


def test_header_must_be_in_the_first_rows(legacy: Path) -> None:
    _xlsx(legacy / "courses.xlsx", [[None]] * 5 + PER_COURSE)
    with pytest.raises(InputError, match="'Course_code' not found in the first 5 rows"):
        convert_legacy(legacy)
    _xlsx(legacy / "courses.xlsx", [[None]] * 2 + PER_COURSE)  # T1: blank rows above are fine
    convert_legacy(legacy, fixes=_fixes(courses_format="per_course"))


def test_unnamed_column_with_data_needs_a_fix(legacy: Path) -> None:
    _spring_survey(legacy, extra_column=[None, None, 1, 5])
    with pytest.raises(InputError, match=r"preferences\.xlsx row 3: column AC has data but no"):
        convert_legacy(legacy)
    fixes = _fixes(survey_columns={"AC": {"question": "Q1", "course": "MATH 818"}})
    result = convert_legacy(legacy, fixes=fixes)
    ranks = {
        (r["professor_id"], r["course_id"]): r["rank"] for r in result.tables["course_preferences"]
    }
    assert ranks[("ann.alpha", "MATH818")] == 5
    assert {
        "kind": "fix",
        "professor_id": "",
        "detail": "preferences.xlsx column AC (no header) read as Q1 ranks for MATH 818",
    } in result.review


def test_stale_and_bad_survey_column_fixes(legacy: Path) -> None:
    _spring_survey(legacy)
    for letter, match in (
        ("AB", "column AB now has the header 'Q7'; remove the stale fix"),
        ("ZZ", "column ZZ does not exist"),
        ("A1", "'A1' is not an Excel column letter"),
    ):
        fixes = _fixes(survey_columns={letter: {"question": "Q1", "course": "MATH 818"}})
        with pytest.raises(InputError, match=match):
            convert_legacy(legacy, fixes=fixes)


def test_course_aliases_apply_everywhere_and_stale_ones_fail(legacy: Path) -> None:
    fixes = _fixes(course_aliases={"MATH 571 (MATH 721)": "MATH721"})
    result = convert_legacy(legacy, fixes=fixes)
    assert "MATH721" in {r["course_id"] for r in result.tables["offerings"]}
    assert "MATH721" in {r["course_id"] for r in result.tables["course_preferences"]}
    assert [r["detail"] for r in result.review if r["kind"] == "fix"] == [
        "course code 'MATH 571 (MATH 721)' read as MATH721 (alias)"
    ]
    with pytest.raises(InputError, match="course_aliases never used \\(stale\\): MATH 999"):
        convert_legacy(legacy, fixes=_fixes(course_aliases={"MATH 999": "X"}))


def test_without_time_room_stage_b_tables_are_absent(legacy: Path, tmp_path: Path) -> None:
    (legacy / "time_room.xlsx").unlink()
    out = tmp_path / "out"
    out.mkdir()
    (out / "rooms.csv").write_text("room_id\nOLD\n")  # left over from an earlier conversion
    result = convert_legacy(legacy, EXTRA)
    inst = read_instance(write_legacy(result, out))
    assert not (out / "rooms.csv").exists()
    assert inst.stage_b_missing == ("time_patterns", "rooms")
    assert inst.time_rank[("ann.alpha", "TR0900")] == 1  # kept for when the patterns arrive
    assert [r["detail"] for r in result.review if r["kind"] == "missing_table"] == [
        "no time_room.xlsx: no time_patterns, rooms, room_availability table; Stage B (times "
        "and rooms) cannot run"
    ]


def test_time_patterns_from_survey(legacy: Path, tmp_path: Path) -> None:
    fixes = _fixes(time_patterns_from_survey=True)
    with pytest.raises(InputError, match="time_patterns_from_survey is stale"):
        convert_legacy(legacy, fixes=fixes)
    (legacy / "time_room.xlsx").unlink()
    inst = read_instance(write_legacy(convert_legacy(legacy, fixes=fixes), tmp_path / "out"))
    assert inst.pattern_ids == ("MWF0900", "MWF1000", "TR0900")
    assert inst.stage_b_missing == ("rooms",)


def test_load_fixes_rejects_unknown_keys(tmp_path: Path) -> None:
    path = tmp_path / "fixes.yaml"
    path.write_text("courses_format: per_course\nsurvey_cols: {}\n")
    with pytest.raises(InputError, match="survey_cols: Extra inputs are not permitted"):
        load_fixes(path)
    path.write_text("courses_format: per_row\n")
    with pytest.raises(InputError, match="courses_format"):
        load_fixes(path)
    path.write_text("")
    assert load_fixes(path) == Fixes()


def test_cli_fixes_option(legacy: Path, tmp_path: Path) -> None:
    _xlsx(legacy / "courses.xlsx", PER_COURSE)
    fixes = tmp_path / "fixes.yaml"
    fixes.write_text("courses_format: per_course\n")
    out = tmp_path / "x"
    res = CliRunner().invoke(
        app, ["convert-legacy", str(legacy), "-o", str(out), "--anonymize", "--fixes", str(fixes)]
    )
    assert res.exit_code == 0, res.output
    assert read_instance(out).offering_info[("MATH161", SectionType.R)].num_sections == 3
    res = CliRunner().invoke(app, ["convert-legacy", str(legacy), "-o", str(out), "--anonymize"])
    assert res.exit_code == 2 and "looks like one row per course" in res.output
