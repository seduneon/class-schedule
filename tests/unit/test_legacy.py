"""Legacy converter (SPEC §8.1) on a synthetic legacy folder (no real data)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import openpyxl
import pytest
from typer.testing import CliRunner

from scheduler.cli import app
from scheduler.domain import FamilyMixing, ScheduleStyle, SectionType
from scheduler.io import read_instance
from scheduler.io.legacy import ExtraOffering, convert_legacy, course_id, write_legacy


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
    assert ann.day_family_mixing is FamilyMixing.AVOID
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
