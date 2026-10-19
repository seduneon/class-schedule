"""M1: readers, schemas, writers (SPEC §8)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scheduler.domain import Assignment, Instance, Placement, SectionType, Solution, Source
from scheduler.io import (
    InputError,
    build_instance,
    read_assignments,
    read_instance,
    read_solution,
    write_assignments,
    write_instance,
    write_solution,
)
from tests.factory import TINY


def test_read_tiny(tiny: Instance) -> None:
    assert tiny.professor_ids == ("A", "B", "C")
    assert [s.id for s in tiny.sections] == [
        "MATH161-1L",
        "MATH161-2L",
        "MATH351-1L",
        "MATH361-1L",
    ]
    assert tiny.course_rank[("B", "MATH161")] == 3
    assert tiny.pattern_by_id["TR0900"].days == ("Tue", "Thu")
    assert tiny.blocked_slots[0].start == 12 * 60


def test_xlsx_and_csv_give_same_instance(tmp_path: Path, tiny: Instance) -> None:
    book = tmp_path / "tiny.xlsx"
    with pd.ExcelWriter(book) as writer:
        for csv in sorted(TINY.glob("*.csv")):
            pd.read_csv(csv, dtype=str).to_excel(writer, sheet_name=csv.stem, index=False)
    other = read_instance(book)
    assert other.professors == tiny.professors
    assert other.sections == tiny.sections
    assert other.patterns == tiny.patterns


def test_row_level_errors_are_reported() -> None:
    tables = {
        "professors": [
            {"professor_id": "A", "name": "a", "load_min": "3", "load_max": "1"},
            {"professor_id": "A", "name": "a2", "load_min": "0", "load_max": "1"},
        ],
        "offerings": [
            {
                "course_id": "M1",
                "title": "t",
                "level": "100",
                "section_type": "X",
                "num_sections": "1",
                "capacity": "10",
                "units": "",
                "room_type": "lecture",
            }
        ],
        "rooms": [],
        "course_preferences": [{"professor_id": "A", "course_id": "M1", "rank": "zero"}],
    }
    with pytest.raises(InputError) as exc:
        build_instance(tables)
    text = str(exc.value)
    assert "professors row 2" in text and "load_min" in text
    assert "professors row 3: duplicate key" in text
    assert "offerings row 2: section_type" in text
    assert "course_preferences row 2: rank" in text
    assert "time_patterns: required table is missing" in text


def test_units_default_by_section_type() -> None:
    tables = {
        "professors": [],
        "rooms": [],
        "time_patterns": [],
        "offerings": [
            {
                "course_id": "M1",
                "title": "t",
                "level": "100",
                "section_type": "R",
                "num_sections": "2",
                "capacity": "10",
                "units": "",
                "room_type": "lecture",
            }
        ],
    }
    inst = build_instance(tables)
    assert inst.offering_info[("M1", SectionType.R)].units == 0.5
    assert [s.label for s in inst.sections] == ["1R", "2R"]


def test_larger_capacity_gets_lower_labels() -> None:
    base = {"course_id": "M1", "title": "t", "level": "100", "section_type": "L", "room_type": "x"}
    tables = {
        "professors": [],
        "rooms": [],
        "time_patterns": [],
        "offerings": [
            {**base, "num_sections": "1", "capacity": "20", "units": "1"},
            {**base, "num_sections": "2", "capacity": "60", "units": "1"},
        ],
    }
    inst = build_instance(tables)
    assert [(s.label, s.capacity) for s in inst.sections] == [("1L", 60), ("2L", 60), ("3L", 20)]
    assert inst.offering_info[("M1", SectionType.L)].num_sections == 3


def test_pins_split_into_stage_a_and_b() -> None:
    tables = {
        "professors": [],
        "rooms": [],
        "time_patterns": [],
        "offerings": [],
        "pins": [
            {"professor_id": "A", "course_id": "M1", "section_type": "L", "count": "1"},
            {"course_id": "M1", "section_type": "L", "section_label": "1L", "room_id": "R1"},
        ],
    }
    inst = build_instance(tables)
    assert len(inst.stage_a_pins) == 1 and inst.stage_a_pins[0].count == 1
    assert inst.stage_b_pins[0].room_id == "R1" and inst.stage_b_pins[0].pattern_id is None


def test_instance_roundtrip(tmp_path: Path, tiny: Instance) -> None:
    write_instance(tiny, tmp_path / "copy")
    again = read_instance(tmp_path / "copy")
    assert again.professors == tiny.professors
    assert again.offerings == tiny.offerings
    assert again.patterns == tiny.patterns
    assert set(again.course_preferences) == set(tiny.course_preferences)
    assert again.blocked_slots == tiny.blocked_slots


def test_assignments_and_solution_roundtrip(tmp_path: Path) -> None:
    a = Assignment("A", "MATH161", SectionType.L, "1L", 40, 1.0, Source.PRE)
    p = Placement("MATH161", SectionType.L, "1L", "MWF0900", "7.101")
    for name in ("a.csv", "a.xlsx"):
        write_assignments((a,), tmp_path / name)
        assert read_assignments(tmp_path / name) == (a,)
    sol = Solution((a,), (p,), {"status": "optimal"})
    write_solution(sol, tmp_path / "s.json")
    again = read_solution(tmp_path / "s.json")
    assert again.assignments == (a,) and again.placements == (p,)
    assert again.meta == {"status": "optimal"}


def test_bad_solution_file_gives_entry_level_errors(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    path.write_text(
        '{"assignments": [{"professor_id": "A", "course_id": "M", "section_type": "Q",'
        ' "section_label": "1L", "capacity": 1, "units": 1, "source": "xx"}],'
        ' "placements": [{"course_id": "M"}]}'
    )
    with pytest.raises(InputError) as exc:
        read_solution(path)
    text = str(exc.value)
    assert "solution assignments row 1: section_type" in text
    assert "solution assignments row 1: source" in text
    assert "solution placements row 1: pattern_id: Field required" in text
    path.write_text("{not json")
    with pytest.raises(InputError, match="not valid JSON"):
        read_solution(path)
