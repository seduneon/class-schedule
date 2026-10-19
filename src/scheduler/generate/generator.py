"""Synthetic instances with controllable size, tightness and preference correlation (L8).

Deterministic: everything is drawn from ``random.Random(spec.seed)`` in a fixed order.

- ``load_tightness`` = total section units / total maximum load (1.0 = exactly enough).
- ``room_tightness`` = sections per (room x non-overlapping slot); higher = scarcer rooms.
- ``preference_correlation`` in [0, 1]: 0 = independent random rankings, 1 = everybody
  ranks courses and times in the same global order.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from scheduler.domain import (
    ConflictGroup,
    CoursePreference,
    Instance,
    Meeting,
    Offering,
    Professor,
    Room,
    ScheduleStyle,
    SectionType,
    TimePattern,
    TimePreference,
    Unavailability,
)

L, R = SectionType.L, SectionType.R


def standard_patterns() -> tuple[TimePattern, ...]:
    """MWF 50-minute slots on the hour (08:00-16:00) and TR 75-minute slots."""
    out = []
    for h in range(8, 17):
        out.append(
            TimePattern(
                f"MWF{h:02d}00",
                tuple(Meeting(d, h * 60, h * 60 + 50) for d in ("Mon", "Wed", "Fri")),
                frozenset({L, R}),
            )
        )
    for start in (9 * 60, 10 * 60 + 30, 12 * 60, 13 * 60 + 30, 15 * 60, 16 * 60 + 30):
        out.append(
            TimePattern(
                f"TR{start // 60:02d}{start % 60:02d}",
                tuple(Meeting(d, start, start + 75) for d in ("Tue", "Thu")),
                frozenset({L}),
            )
        )
    return tuple(sorted(out, key=lambda t: t.id))


@dataclass(frozen=True)
class GeneratorSpec:
    n_professors: int = 6
    n_courses: int = 6
    max_lecture_sections: int = 2
    recitation_share: float = 0.25
    n_rooms: int = 3
    load_tightness: float = 0.8
    room_tightness: float = 0.5
    preference_correlation: float = 0.5
    courses_ranked: tuple[int, int] = (3, 5)
    times_ranked: tuple[int, int] = (3, 6)
    unavailability_rate: float = 0.1
    cannot_rate: float = 0.05
    seed: int = 0
    patterns: tuple[TimePattern, ...] = field(default_factory=standard_patterns)


def _ranking(
    rng: random.Random, items: list[str], base: dict[str, float], corr: float
) -> list[str]:
    noisy = {i: corr * base[i] + (1 - corr) * rng.random() for i in items}
    return sorted(items, key=lambda i: (-noisy[i], i))


def generate_instance(spec: GeneratorSpec) -> Instance:
    """Build a random instance from ``spec`` (same spec -> identical instance)."""
    rng = random.Random(spec.seed)
    levels = [100, 200, 300, 300, 400, 400, 500]
    offerings: list[Offering] = []
    for i in range(spec.n_courses):
        level = levels[i % len(levels)] + 10 * (i // len(levels)) + 1 + i % 9
        cid = f"MATH{level}"
        n_l = rng.randint(1, spec.max_lecture_sections)
        cap = rng.choice([25, 30, 40, 60]) if level < 500 else 20
        offerings.append(Offering(cid, f"Course {cid}", level, L, n_l, cap, 1.0, "lecture"))
        if rng.random() < spec.recitation_share:
            offerings.append(
                Offering(cid, f"Course {cid}", level, R, n_l, min(cap, 30), 0.5, "lecture")
            )
    course_ids = sorted({o.course_id for o in offerings})
    units = sum(o.units * o.num_sections for o in offerings)
    n_sections = sum(o.num_sections for o in offerings)

    total_load = units / max(spec.load_tightness, 1e-6)
    shares = [rng.uniform(0.7, 1.3) for _ in range(spec.n_professors)]
    norm = sum(shares)
    professors = []
    for j in range(spec.n_professors):
        hi = max(1.0, round(total_load * shares[j] / norm * 2) / 2)
        lo = max(0.0, hi - 1.0)
        professors.append(
            Professor(
                id=f"P{j + 1:02d}",
                name=f"Professor {j + 1}",
                load_min=lo,
                load_max=hi,
                priority=1.0,
                max_preps=rng.choice([None, None, 2, 3]),
                max_days=rng.choice([None, None, None, 4]),
                multi_section_pref=rng.choice([-1, 0, 0, 1]),
                schedule_style=rng.choice(list(ScheduleStyle)),
            )
        )

    max_cap = max((o.capacity for o in offerings), default=30)
    slots = 9  # roughly the number of pairwise disjoint slots in standard_patterns per day-group
    n_rooms = max(spec.n_rooms, math.ceil(n_sections / (slots / max(spec.room_tightness, 1e-6))))
    rooms = [
        Room(
            f"R{k + 1:02d}",
            "Main",
            max_cap if k == 0 else rng.choice([30, 40, 60, max_cap]),
            "lecture",
        )
        for k in range(n_rooms)
    ]

    course_base = {c: rng.random() for c in course_ids}
    pattern_ids = [t.id for t in spec.patterns]
    time_base = {t: rng.random() for t in pattern_ids}
    cprefs: list[CoursePreference] = []
    tprefs: list[TimePreference] = []
    unav: list[Unavailability] = []
    for prof in professors:
        k = rng.randint(*spec.courses_ranked)
        ranked = _ranking(rng, course_ids, course_base, spec.preference_correlation)[:k]
        cprefs += [CoursePreference(prof.id, c, r + 1) for r, c in enumerate(ranked)]
        for c in course_ids:
            if c not in ranked and rng.random() < spec.cannot_rate:
                cprefs.append(CoursePreference(prof.id, c, None))
        k = rng.randint(*spec.times_ranked)
        ranked_t = _ranking(rng, pattern_ids, time_base, spec.preference_correlation)[:k]
        tprefs += [TimePreference(prof.id, t, r + 1) for r, t in enumerate(ranked_t)]
        if rng.random() < spec.unavailability_rate:
            day = rng.choice(["Mon", "Tue", "Wed", "Thu", "Fri"])
            start = rng.choice([8, 12, 14]) * 60
            unav.append(Unavailability(prof.id, day, start, start + 120, "generated"))

    # Every course must be coverable: give it to the professor ranking it best, else to the
    # least-loaded professor, so generated instances are interesting but not hopeless.
    ranked_by = {
        c: [p.professor_id for p in cprefs if p.course_id == c and p.rank is not None]
        for c in course_ids
    }
    for idx, c in enumerate(course_ids):
        if not ranked_by[c]:
            prof = professors[idx % len(professors)]
            cprefs = [p for p in cprefs if not (p.professor_id == prof.id and p.course_id == c)]
            worst = max((p.rank or 0 for p in cprefs if p.professor_id == prof.id), default=0)
            cprefs.append(CoursePreference(prof.id, c, worst + 1))

    groups = []
    first_year = [c for c in course_ids if c.startswith("MATH1")]
    if len(first_year) >= 2:
        groups.append(ConflictGroup("first_year", frozenset(first_year[:2]), None, None))
    return Instance(
        professors=tuple(professors),
        offerings=tuple(offerings),
        rooms=tuple(rooms),
        patterns=tuple(spec.patterns),
        course_preferences=tuple(cprefs),
        time_preferences=tuple(tprefs),
        unavailability=tuple(unav),
        conflict_groups=tuple(groups),
    )
