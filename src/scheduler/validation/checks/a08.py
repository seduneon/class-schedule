"""A8 — Timetable capacity pre-check."""

from __future__ import annotations

from collections import Counter, defaultdict

from scheduler.config import Config, ConstraintSettings
from scheduler.derived import (
    A8_GROUPS,
    A8_PROFESSORS,
    A8_ROOMS,
    a8_part_active,
    family_patterns,
    family_room_pattern_sets,
    hard_group_families,
    offering_rooms,
    pinned_family,
    professor_pattern_sets,
    room_set_label,
)
from scheduler.domain import Instance, Solution
from scheduler.time import max_independent_set_size
from scheduler.validation.core import Violation, check, severity_for


@check("A8")
def check_a8(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """sum_{c,k} n_{p,c,k} <= alpha_p, alpha_p = max number of pairwise non-overlapping patterns
    available to p (computed here without a solver). With B13 hard, alpha_p respects Phi_p and
    chi_p, and per family f and room set R*: sections of P_f that fit only in R* <= kappa_f(R*),
    and per hard group g: sum over its courses c of max_{p in P_f} (sections of c taught by p)
    <= alpha(U^f). Parts whose input tables are absent are not checked (SPEC D13)."""
    buf = config.time.buffer_minutes
    counts = Counter(a.professor_id for a in solution.assignments)
    out = []
    for pid, n in sorted(counts.items()) if a8_part_active(instance, config, A8_PROFESSORS) else ():
        if pid not in instance.professor_by_id:
            continue
        sets = professor_pattern_sets(instance, config, pid)
        alpha = max(max_independent_set_size(s, buf) for s in sets)
        if n > alpha:
            out.append(
                Violation(
                    "A8",
                    severity_for(settings),
                    f"{pid} has {n} sections but only {alpha} non-overlapping available time patterns",
                    (pid,),
                    size=n - alpha,
                )
            )
    pinned = {p: f for p in sorted(counts) if (f := pinned_family(instance, config, p))}
    demand: dict[str, Counter[frozenset[str]]] = defaultdict(Counter)
    own: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
    for a in solution.assignments:
        if a.professor_id in pinned:
            f = pinned[a.professor_id]
            demand[f][offering_rooms(instance, (a.course_id, a.section_type))] += 1
            own[f][(a.course_id, a.professor_id)] += 1
    for f in sorted(demand) if a8_part_active(instance, config, A8_ROOMS) else ():
        for rooms in sorted({r for r in demand[f] if r}, key=sorted):
            n = sum(m for r, m in demand[f].items() if r and r <= rooms)
            sets = family_room_pattern_sets(instance, config, f, rooms)
            kappa = sum(max_independent_set_size(s, buf) for s in sets)
            if n > kappa:
                out.append(
                    Violation(
                        "A8",
                        severity_for(settings),
                        f"professors who teach only {f} have {n} sections that fit only in "
                        f"rooms {room_set_label(rooms)}, which have {kappa} {f} "
                        "(room, time pattern) slots",
                        (f, *sorted(rooms)),
                        size=n - kappa,
                    )
                )
    groups = a8_part_active(instance, config, A8_GROUPS)
    for g, f in hard_group_families(instance, config) if groups else ():
        need: dict[str, int] = {}
        for (c, _p), n in own[f].items():
            if c in g.course_ids:
                need[c] = max(need.get(c, 0), n)
        slots = max_independent_set_size(family_patterns(instance, config, f), buf)
        if sum(need.values()) > slots:
            out.append(
                Violation(
                    "A8",
                    severity_for(settings),
                    f"conflict group {g.id} needs {sum(need.values())} non-overlapping {f} time "
                    f"patterns for professors who teach only {f} but only {slots} exist",
                    (g.id, f),
                    size=sum(need.values()) - slots,
                )
            )
    return out
