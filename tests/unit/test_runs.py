"""Run folders (SPEC L9): naming, collisions, latest link, hashes, config round trip."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from scheduler.config import Config, load_config
from scheduler.io.runs import (
    RunRecord,
    from_run,
    instance_sha256,
    new_run_dir,
    run_dir_name,
    write_config,
)
from tests.factory import TINY

NOW = datetime(2026, 10, 19, 14, 30, 5)


def test_name_is_timestamp_and_instance(tmp_path: Path) -> None:
    assert run_dir_name(TINY, NOW) == "2026-10-19_14-30-05_tiny"
    book = tmp_path / "fall2026.xlsx"
    book.write_bytes(b"")
    assert run_dir_name(book, NOW) == "2026-10-19_14-30-05_fall2026"


def test_taken_names_get_a_suffix_and_latest_follows(tmp_path: Path) -> None:
    first = new_run_dir(tmp_path, TINY, NOW)
    second = new_run_dir(tmp_path, TINY, NOW)
    third = new_run_dir(tmp_path, TINY, NOW)
    assert [p.name for p in (first, second, third)] == [
        "2026-10-19_14-30-05_tiny",
        "2026-10-19_14-30-05_tiny-2",
        "2026-10-19_14-30-05_tiny-3",
    ]
    latest = tmp_path / "latest"
    assert latest.is_symlink() and latest.resolve() == third.resolve()


def test_instance_hash_tracks_content(tmp_path: Path) -> None:
    for f in TINY.iterdir():
        (tmp_path / f.name).write_bytes(f.read_bytes())
    before = instance_sha256(tmp_path)
    assert before == instance_sha256(TINY)
    (tmp_path / "rooms.csv").write_text("room_id,building,capacity,room_type\n")
    assert instance_sha256(tmp_path) != before


def test_config_yaml_round_trips(tmp_path: Path) -> None:
    cfg = Config().with_updates(solver={"seed": 7})
    path = write_config(cfg, tmp_path / "config.yaml")
    assert load_config(path) == cfg


def test_run_json_fields_and_from_run(tmp_path: Path) -> None:
    previous = tmp_path / "old"
    previous.mkdir()
    (previous / "run.json").write_text("{}")
    rec = RunRecord("run", ["run", "x"], TINY, None, previous / "assignments.csv")
    rec.status = "ok"
    assert rec.hard_violations is None
    rec.add_stage("A", "optimal", {"variables": 3}, errors=2, warnings=1)
    rec.add_stage("B", "infeasible", {}, solved=False)  # no solution: count unchanged
    out = tmp_path / "new"
    out.mkdir()
    data = json.loads(rec.write(out).read_text())
    assert data["from_run"] == "old" == from_run(previous / "assignments.csv")
    assert data["stages"]["A"] == {
        "status": "optimal",
        "variables": 3,
        "violations": {"error": 2, "warning": 1},
    }
    assert data["hard_violations"] == 2
    assert data["instance_sha256"] == instance_sha256(TINY)
    assert data["finished_at"] is not None and data["config"] is None
    assert from_run(tmp_path / "elsewhere.csv") is None
