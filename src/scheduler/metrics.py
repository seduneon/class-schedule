"""Solution metrics computed in plain Python (reports, experiments, alternatives).

sat^C_p = (1 / L_max_p) sum u_{c,k} w^C_{p,c,k}   over p's assignments (SPEC A9)
sat^T_p = (1 / |S_p|)   sum w^T_{p,t}           over p's placements  (SPEC B12)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from scheduler.config import Config
from scheduler.domain import Instance, Solution, is_placeholder
from scheduler.preferences import course_weights, time_weights


@dataclass(frozen=True)
class ProfessorMetrics:
    professor_id: str
    sections: int
    load: float
    load_min: float
    load_max: float
    course_ranks: tuple[int | None, ...]  # rank of each assigned course section (None = unranked)
    best_course_rank: int | None
    time_ranks: tuple[int | None, ...]
    best_time_rank: int | None
    sat_course: float | None
    sat_time: float | None


def professor_metrics(
    instance: Instance, solution: Solution, config: Config
) -> list[ProfessorMetrics]:
    """Per-professor load, ranks received vs best possible, and satisfaction."""
    wc = course_weights(instance, config.preferences)
    wt = time_weights(instance, config.preferences)
    by_prof = defaultdict(list)
    for a in solution.assignments:
        by_prof[a.professor_id].append(a)
    owner = {a.section_key: a.professor_id for a in solution.assignments}
    placed = defaultdict(list)
    for p in solution.placements or ():
        if p.section_key in owner:
            placed[owner[p.section_key]].append(p)
    out = []
    for prof in instance.professors:
        rows = by_prof.get(prof.id, [])
        load = sum(a.units for a in rows)
        cranks = tuple(
            instance.course_type_rank.get((prof.id, a.course_id, a.section_type)) for a in rows
        )
        tranks = tuple(
            instance.time_rank.get((prof.id, p.pattern_id)) for p in placed.get(prof.id, [])
        )
        own_c = [
            r
            for (p, _c, _k), r in instance.course_type_rank.items()
            if p == prof.id and r is not None
        ]
        own_t = [r for (p, _t), r in instance.time_rank.items() if p == prof.id and r is not None]
        sat_c = (
            sum(a.units * wc.get((prof.id, a.course_id, a.section_type), 0.0) for a in rows)
            / prof.load_max
            if prof.load_max > 0
            else None
        )
        sat_t = None
        if solution.placements is not None and rows:
            sat_t = sum(
                wt.get((prof.id, p.pattern_id), 0.0) for p in placed.get(prof.id, [])
            ) / len(rows)
        out.append(
            ProfessorMetrics(
                professor_id=prof.id,
                sections=len(rows),
                load=load,
                load_min=prof.load_min,
                load_max=prof.load_max,
                course_ranks=cranks,
                best_course_rank=min(own_c) if own_c else None,
                time_ranks=tranks,
                best_time_rank=min(own_t) if own_t else None,
                sat_course=sat_c,
                sat_time=sat_t,
            )
        )
    return out


@dataclass(frozen=True)
class SolutionSummary:
    sections_total: int
    sections_assigned: int
    sections_scheduled: int | None
    total_sat_course: float
    min_sat_course: float | None
    total_sat_time: float | None
    min_sat_time: float | None


def summarize(instance: Instance, solution: Solution, config: Config) -> SolutionSummary:
    """Totals used in reports and experiments (priorities applied to totals, D6)."""
    metrics = professor_metrics(instance, solution, config)
    prio = {p.id: p.priority for p in instance.professors}
    sat_c = [(m.professor_id, m.sat_course) for m in metrics if m.sat_course is not None]
    fair_c = [s for pid, s in sat_c if instance.professor_by_id[pid].load_min > 0]
    sat_t = [(m.professor_id, m.sat_time) for m in metrics if m.sat_time is not None]
    real = [a for a in solution.assignments if not is_placeholder(a.professor_id)]
    return SolutionSummary(
        sections_total=len(instance.sections),
        sections_assigned=len({a.section_key for a in solution.assignments}),
        sections_scheduled=None
        if solution.placements is None
        else len({p.section_key for p in solution.placements}),
        total_sat_course=sum(prio[p] * s for p, s in sat_c),
        min_sat_course=min(fair_c) if fair_c and real else None,
        total_sat_time=None if solution.placements is None else sum(prio[p] * s for p, s in sat_t),
        min_sat_time=min((s for _p, s in sat_t), default=None),
    )
