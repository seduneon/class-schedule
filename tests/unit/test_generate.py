"""L8 — generator."""

from __future__ import annotations

from scheduler.config import Config
from scheduler.diagnostics import presolve_checks
from scheduler.generate import GeneratorSpec, generate_instance


def test_generator_is_deterministic() -> None:
    a = generate_instance(GeneratorSpec(seed=7))
    b = generate_instance(GeneratorSpec(seed=7))
    assert a.professors == b.professors and a.offerings == b.offerings
    assert a.course_preferences == b.course_preferences
    assert generate_instance(GeneratorSpec(seed=8)).course_preferences != a.course_preferences


def test_every_course_has_someone_who_ranked_it() -> None:
    inst = generate_instance(GeneratorSpec(n_professors=3, n_courses=8, seed=3))
    ranked = {c.course_id for c in inst.course_preferences if c.rank is not None}
    assert ranked >= set(inst.course_ids)
    codes = {f.code for f in presolve_checks(inst, Config())}
    assert "no_eligible_professor" not in codes and "no_room" not in codes


def test_load_tightness_controls_capacity() -> None:
    loose = generate_instance(GeneratorSpec(load_tightness=0.5, seed=1))
    tight = generate_instance(GeneratorSpec(load_tightness=1.5, seed=1))
    assert sum(p.load_max for p in loose.professors) > sum(p.load_max for p in tight.professors)
