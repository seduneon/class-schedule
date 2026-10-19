"""CLI end-to-end on the tiny example (M7)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from scheduler.cli import app
from tests.factory import ROOT, TINY

runner = CliRunner()
CONFIG = str(ROOT / "configs" / "default.yaml")


def test_check_assign_timetable_validate_report(tmp_path: Path) -> None:
    r = runner.invoke(app, ["check", str(TINY)])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["assign", str(TINY), "-o", str(tmp_path), "-c", CONFIG])
    assert r.exit_code == 0, r.output
    assert "Stage A: optimal" in r.output
    r = runner.invoke(
        app,
        [
            "timetable",
            str(TINY),
            "--assignments",
            str(tmp_path / "assignments.csv"),
            "-o",
            str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output
    for name in ("solution.json", "report.xlsx", "timetable.html", "stage_a.json"):
        assert (tmp_path / name).exists()
    sheets = pd.read_excel(tmp_path / "report.xlsx", sheet_name=None)
    assert {"by_professor", "by_room", "by_conflict_group", "assignments", "satisfaction"} <= set(
        sheets
    )
    assert len(sheets["by_professor"]) == 4
    r = runner.invoke(app, ["validate", str(TINY), str(tmp_path / "solution.json")])
    assert r.exit_code == 0 and "all checks passed" in r.output
    r = runner.invoke(
        app, ["report", str(TINY), str(tmp_path / "solution.json"), "-o", str(tmp_path / "rep")]
    )
    assert r.exit_code == 0 and (tmp_path / "rep" / "timetable.html").exists()


def test_validate_flags_a_hand_edit(tmp_path: Path) -> None:
    runner.invoke(app, ["assign", str(TINY), "-o", str(tmp_path)])
    runner.invoke(
        app,
        [
            "timetable",
            str(TINY),
            "--assignments",
            str(tmp_path / "assignments.csv"),
            "-o",
            str(tmp_path),
        ],
    )
    data = json.loads((tmp_path / "solution.json").read_text())
    for p in data["placements"]:  # chair moves everything into one small room
        p["room_id"] = "7.102"
    (tmp_path / "edited.json").write_text(json.dumps(data))
    r = runner.invoke(app, ["validate", str(TINY), str(tmp_path / "edited.json")])
    assert r.exit_code == 1
    assert "[B1 error]" in r.output and "holds 30 < 40" in r.output


def test_edited_assignments_flow_into_stage_b(tmp_path: Path) -> None:
    runner.invoke(app, ["assign", str(TINY), "-o", str(tmp_path)])
    frame = pd.read_csv(tmp_path / "assignments.csv")
    frame.loc[frame["course_id"] == "MATH351", "professor_id"] = "C"  # manual edit
    frame.loc[frame["course_id"] == "MATH351", "source"] = "manual"
    frame.to_csv(tmp_path / "edited.csv", index=False)
    r = runner.invoke(app, ["validate", str(TINY), str(tmp_path / "edited.csv")])
    assert r.exit_code == 1  # C cannot take 351 (unranked, forbid) and is overloaded
    r = runner.invoke(
        app,
        [
            "timetable",
            str(TINY),
            "--assignments",
            str(tmp_path / "edited.csv"),
            "-o",
            str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output
    data = json.loads((tmp_path / "solution.json").read_text())
    assert {a["source"] for a in data["assignments"]} == {"model", "manual"}


def test_bad_input_gives_row_level_errors(tmp_path: Path) -> None:
    for csv in TINY.glob("*.csv"):
        (tmp_path / csv.name).write_text(csv.read_text())
    (tmp_path / "rooms.csv").write_text(
        "room_id,building,capacity,room_type\n7.101,B7,lots,lecture\n"
    )
    r = runner.invoke(app, ["check", str(tmp_path)])
    assert r.exit_code == 2
    assert "rooms row 2: capacity" in r.output


def test_alternatives_and_repair_commands(tmp_path: Path) -> None:
    runner.invoke(app, ["assign", str(TINY), "-o", str(tmp_path)])
    asg = str(tmp_path / "assignments.csv")
    r = runner.invoke(
        app,
        [
            "alternatives",
            str(TINY),
            "--assignments",
            asg,
            "--count",
            "2",
            "-o",
            str(tmp_path / "alt"),
        ],
    )
    assert r.exit_code == 0, r.output
    assert (tmp_path / "alt" / "alternatives.json").exists()
    runner.invoke(app, ["timetable", str(TINY), "--assignments", asg, "-o", str(tmp_path)])
    r = runner.invoke(
        app,
        [
            "repair",
            str(TINY),
            "--previous",
            str(tmp_path / "solution.json"),
            "-o",
            str(tmp_path / "rep"),
        ],
    )
    assert r.exit_code == 0, r.output
    assert "level 10 (repair, min): 0" in r.output
