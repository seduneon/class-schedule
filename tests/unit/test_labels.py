"""Label attachment (SPEC §5.4)."""

from __future__ import annotations

from scheduler.domain import PreAssignment, SectionType, Source
from scheduler.model.stage_a.labels import attach_labels
from tests.factory import instance, offering

L = SectionType.L


def test_labels_in_professor_order_with_larger_caps_first() -> None:
    inst = instance(offerings=[offering("M1", n=1, cap=20), offering("M1", n=2, cap=60)])
    out = attach_labels(inst, {("Q", "M1", L): 1, ("P", "M1", L): 2})
    assert [(a.professor_id, a.section_label, a.capacity) for a in out] == [
        ("P", "1L", 60),
        ("P", "2L", 60),
        ("Q", "3L", 20),
    ]
    assert all(a.source is Source.MODEL for a in out)


def test_pre_assigned_labels_go_first() -> None:
    inst = instance(
        offerings=[offering("M1", n=3)],
        pre_assignments=[
            PreAssignment("Q", "M1", L, 1, ("1L",)),
            PreAssignment("P", "M1", L, 1),
        ],
    )
    out = attach_labels(inst, {("P", "M1", L): 2, ("Q", "M1", L): 1})
    got = {(a.professor_id, a.section_label, a.source.value) for a in out}
    assert got == {("Q", "1L", "pre"), ("P", "2L", "pre"), ("P", "3L", "model")}


def test_counts_beyond_offered_get_extra_labels() -> None:
    inst = instance(offerings=[offering("M1", n=1)])
    out = attach_labels(inst, {("P", "M1", L): 1, ("Q", "M1", L): 1})
    assert [a.section_label for a in out] == ["1L", "2L"]
