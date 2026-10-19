"""CLI end-to-end on the tiny example (M7)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pandas as pd
from pytest import MonkeyPatch
from typer.testing import CliRunner

from scheduler import cli
from scheduler.cli import app
from scheduler.pipeline import StageResult, run_stage_a
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


def _only_run(runs: Path) -> Path:
    folders = sorted(p for p in runs.iterdir() if not p.is_symlink())
    assert len(folders) == 1, folders
    return folders[0]


def test_run_writes_a_timestamped_run_folder(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    r = runner.invoke(app, ["run", str(TINY), "-c", CONFIG, "--runs-dir", str(runs)])
    assert r.exit_code == 0, r.output
    folder = _only_run(runs)
    assert folder.name.endswith("_tiny")
    assert (runs / "latest").resolve() == folder.resolve()
    for name in (
        "run.json",
        "config.yaml",
        "log.txt",
        "check.txt",
        "assignments.csv",
        "stage_a.json",
        "solution.json",
        "report.xlsx",
        "timetable.html",
    ):
        assert (folder / name).exists(), name
    meta = json.loads((folder / "run.json").read_text())
    assert meta["status"] == "ok" and meta["command"] == "run"
    assert set(meta["stages"]) == {"A", "B"}
    assert meta["config"] == CONFIG and meta["from_run"] is None
    log = (folder / "log.txt").read_text()
    assert "Stage A: optimal" in log and "Stage B: optimal" in log and "\x1b[" not in log
    r = runner.invoke(app, ["validate", str(TINY), str(runs / "latest" / "solution.json")])
    assert r.exit_code == 0, r.output


def test_run_with_edited_assignments_skips_stage_a(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runner.invoke(app, ["run", str(TINY), "--runs-dir", str(runs)])
    first = _only_run(runs)
    r = runner.invoke(
        app,
        [
            "run",
            str(TINY),
            "--assignments",
            str(runs / "latest" / "assignments.csv"),
            "--runs-dir",
            str(runs),
        ],
    )
    assert r.exit_code == 0, r.output
    second = (runs / "latest").resolve()
    assert second != first.resolve()
    meta = json.loads((second / "run.json").read_text())
    assert meta["from_run"] == first.name and set(meta["stages"]) == {"B"}
    assert not (second / "stage_a.json").exists() and (second / "solution.json").exists()


def test_l1_errors_are_reported_but_do_not_stop_the_run(tmp_path: Path) -> None:
    inst = tmp_path / "small_rooms"
    inst.mkdir()
    for f in TINY.iterdir():
        (inst / f.name).write_bytes(f.read_bytes())
    rooms = pd.read_csv(inst / "rooms.csv")
    rooms["capacity"] = 1  # no section fits anywhere: L1 errors, nothing placed
    rooms.to_csv(inst / "rooms.csv", index=False)
    runs = tmp_path / "runs"
    r = runner.invoke(app, ["run", str(inst), "--runs-dir", str(runs)])
    assert r.exit_code == 0, r.output
    assert "Check: " in r.output and "see check.txt" in r.output
    folder = _only_run(runs)
    assert "no_room" in (folder / "check.txt").read_text()
    assert (folder / "solution.json").exists()


def test_failed_stage_marks_the_run_failed(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    def no_solution(*args: object, **kwargs: object) -> StageResult:
        return replace(run_stage_a(*args, **kwargs), solution=None)  # type: ignore[arg-type]

    monkeypatch.setattr(cli, "run_stage_a", no_solution)
    runs = tmp_path / "runs"
    r = runner.invoke(app, ["run", str(TINY), "--runs-dir", str(runs)])
    assert r.exit_code == 1, r.output
    folder = _only_run(runs)
    meta = json.loads((folder / "run.json").read_text())
    assert meta["status"] == "failed" and set(meta["stages"]) == {"A"}
    assert not (folder / "assignments.csv").exists()


def test_commands_default_to_run_folders(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    r = runner.invoke(app, ["assign", str(TINY), "--runs-dir", str(runs)])
    assert r.exit_code == 0, r.output
    folder = _only_run(runs)
    assert (folder / "assignments.csv").exists()
    assert json.loads((folder / "run.json").read_text())["command"] == "assign"


def test_bad_or_missing_files_give_one_line_errors(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("solver: [unclosed\n")
    unknown_key = tmp_path / "unknown.yaml"
    unknown_key.write_text("nope: 1\n")
    for args in (
        ["check", str(tmp_path / "missing")],
        ["timetable", str(TINY), "--assignments", str(tmp_path / "missing.csv")],
        ["validate", str(TINY), str(tmp_path / "missing.json")],
        ["check", str(TINY), "-c", str(bad_yaml)],
        ["check", str(TINY), "-c", str(unknown_key)],
    ):
        r = runner.invoke(app, args)
        assert r.exit_code == 2, (args, r.output)
        assert r.output.startswith("Error: "), (args, r.output)
        assert not isinstance(r.exception, Exception) or isinstance(r.exception, SystemExit)
