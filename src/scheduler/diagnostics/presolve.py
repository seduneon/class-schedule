"""L1 — pre-solve diagnostics: find unsatisfiable data before building a model.

Every finding is plain-language and names the entities involved.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from scheduler.config import Config
from scheduler.derived import (
    StageBSection,
    conflict_groups,
    ineligibility_reason,
    is_eligible,
    pattern_blocked,
    pattern_problem,
    professor_unavailable,
    room_problem,
    stage_a_offering_keys,
    stage_b_sections,
)
from scheduler.domain import Assignment, Instance, OfferingKey, is_placeholder
from scheduler.time import usable_patterns
from scheduler.time.independent_set import alpha, max_independent_patterns

Level = Literal["error", "warning", "info"]


@dataclass(frozen=True)
class Finding:
    severity: Level
    code: str
    message: str
    entities: tuple[str, ...] = ()

    def __str__(self) -> str:
        return f"{self.severity.upper():7} {self.code}: {self.message}"


def presolve_checks(
    instance: Instance, config: Config, assignments: Sequence[Assignment] | None = None
) -> list[Finding]:
    """Run every L1 check. With ``assignments`` (Stage B input), also check those sections."""
    out: list[Finding] = []
    out += data_integrity(instance, config)
    out += load_capacity(instance, config)
    out += offering_staffing(instance, config)
    out += section_rooms(instance, config)
    out += room_slot_capacity(instance, config)
    out += professor_alpha(instance, config, assignments)
    out += group_capacity(instance, config)
    out += pin_conflicts(instance, config)
    out += unavailability_off_days(instance, config)
    if assignments is not None:
        out += stage_b_inputs(instance, config, assignments)
    return out


def has_errors(findings: Iterable[Finding]) -> bool:
    return any(f.severity == "error" for f in findings)


# ----- data integrity ----------------------------------------------------------------


def data_integrity(instance: Instance, config: Config) -> list[Finding]:
    """Unknown IDs, duplicate ranks, pre-assignments of non-offered courses, overlapping blocks."""
    out: list[Finding] = []
    profs, courses, pats = (
        set(instance.professor_ids),
        set(instance.course_ids),
        set(instance.pattern_ids),
    )

    def unknown(kind: str, value: str, where: str) -> None:
        out.append(
            Finding("error", "unknown_id", f"{where} refers to unknown {kind} {value!r}", (value,))
        )

    for cp in instance.course_preferences:
        if cp.professor_id not in profs:
            unknown("professor", cp.professor_id, "course_preferences")
        if cp.course_id not in courses:
            out.append(
                Finding(
                    "warning",
                    "unknown_id",
                    f"course_preferences: {cp.professor_id} ranks {cp.course_id!r}, which is not offered",
                    (cp.professor_id, cp.course_id),
                )
            )
    for tp in instance.time_preferences:
        if tp.professor_id not in profs:
            unknown("professor", tp.professor_id, "time_preferences")
        if tp.pattern_id not in pats:
            unknown("time pattern", tp.pattern_id, "time_preferences")
    for u in instance.unavailability:
        if u.professor_id not in profs:
            unknown("professor", u.professor_id, "unavailability")
    for ra in instance.room_availability:
        if ra.room_id not in instance.room_by_id:
            unknown("room", ra.room_id, "room_availability")
        if ra.pattern_id not in pats:
            unknown("time pattern", ra.pattern_id, "room_availability")
    for g in instance.conflict_groups:
        for c in sorted(g.course_ids - courses):
            out.append(
                Finding(
                    "warning",
                    "unknown_id",
                    f"conflict group {g.id} lists {c!r}, which is not offered",
                    (g.id, c),
                )
            )
    for link in instance.section_links:
        for label in (link.recitation_label, link.lecture_label):
            if not any(
                s.course_id == link.course_id and s.label == label for s in instance.sections
            ):
                unknown("section", f"{link.course_id}-{label}", "section_links")

    out += _duplicate_ranks(
        "course",
        [(c.professor_id, c.rank) for c in instance.course_preferences if c.rank is not None],
    )
    out += _duplicate_ranks(
        "time", [(t.professor_id, t.rank) for t in instance.time_preferences if t.rank is not None]
    )

    for pa in instance.pre_assignments:
        key = (pa.course_id, pa.section_type)
        if pa.professor_id not in profs:
            unknown("professor", pa.professor_id, "pre_assignments")
        if key not in instance.offering_info:
            out.append(
                Finding(
                    "error",
                    "pre_not_offered",
                    f"pre-assignment of {pa.professor_id} to {pa.course_id} {pa.section_type.value}, "
                    "which is not offered",
                    (pa.professor_id, pa.course_id),
                )
            )
            continue
        for label in pa.section_labels:
            if (pa.course_id, pa.section_type, label) not in instance.section_by_key:
                unknown("section", f"{pa.course_id}-{label}", "pre_assignments")
        reason = ineligibility_reason(
            instance, config, pa.professor_id, pa.course_id, pa.section_type
        )
        if reason is not None and config.enabled("A3"):
            out.append(
                Finding(
                    "warning",
                    "pre_overrides_eligibility",
                    f"{pa.professor_id} is pre-assigned {pa.course_id} although {reason}; "
                    "the pre-assignment wins (A4)",
                    (pa.professor_id, pa.course_id),
                )
            )
    pre_by_offering: dict[OfferingKey, int] = {}
    for (_p, c, k), n in instance.pre_assigned.items():
        pre_by_offering[(c, k)] = pre_by_offering.get((c, k), 0) + n
    for (c, k), n in sorted(pre_by_offering.items(), key=lambda kv: (kv[0][0], kv[0][1].value)):
        info = instance.offering_info.get((c, k))
        if info is not None and n > info.num_sections:
            out.append(
                Finding(
                    "error",
                    "pre_exceeds_sections",
                    f"{c} {k.value}: {n} sections pre-assigned but only {info.num_sections} offered",
                    (c, k.value),
                )
            )

    blocks = sorted(instance.blocked_slots, key=lambda b: (b.day, b.start, b.end))
    for i, a in enumerate(blocks):
        for b in blocks[i + 1 :]:
            if a.day == b.day and a.start < b.end and b.start < a.end:
                out.append(
                    Finding(
                        "warning",
                        "overlapping_blocked_slots",
                        f"blocked slots overlap on {a.day}: {a.reason or 'unnamed'} and {b.reason or 'unnamed'}",
                        (a.day,),
                    )
                )
    return out


def _duplicate_ranks(kind: str, rows: list[tuple[str, int | None]]) -> list[Finding]:
    """One warning per professor listing every rank given to more than one item."""
    counts = Counter(rows)
    tied: dict[str, list[str]] = {}
    for (pid, rank), n in sorted(counts.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0)):
        if n > 1:
            tied.setdefault(pid, []).append(f"{rank} (x{n})")
    return [
        Finding(
            "warning",
            "duplicate_rank",
            f"{pid} gives several {kind} preferences the same rank: {', '.join(ranks)}",
            (pid,),
        )
        for pid, ranks in tied.items()
    ]


# ----- capacity checks ---------------------------------------------------------------------


def _units_needed(instance: Instance, config: Config) -> float:
    return sum(
        instance.offering_info[k].num_sections * instance.offering_info[k].units
        for k in stage_a_offering_keys(instance, config)
    )


def load_capacity(instance: Instance, config: Config) -> list[Finding]:
    """Total load capacity vs total section units."""
    needed = _units_needed(instance, config)
    cap_max = sum(p.load_max for p in instance.professors)
    cap_min = sum(p.load_min for p in instance.professors)
    out: list[Finding] = []
    if cap_max < needed:
        out.append(
            Finding(
                "error",
                "load_capacity",
                f"sections need {needed:g} units but professors can teach at most {cap_max:g}; "
                f"at least {needed - cap_max:g} units will stay uncovered",
            )
        )
    if cap_min > needed:
        out.append(
            Finding(
                "warning",
                "load_minimum",
                f"professors' minimum loads add up to {cap_min:g} units but only {needed:g} are offered; "
                "some professors will be underloaded",
            )
        )
    return out


def offering_staffing(instance: Instance, config: Config) -> list[Finding]:
    """Per (c, k): eligible professors and their combined capacity vs N_{c,k}."""
    out: list[Finding] = []
    for c, k in stage_a_offering_keys(instance, config):
        info = instance.offering_info[(c, k)]
        if info.num_sections == 0:
            continue
        eligible = [p for p in instance.professors if is_eligible(instance, config, p.id, c, k)]
        if not eligible:
            out.append(
                Finding(
                    "error",
                    "no_eligible_professor",
                    f"{c} {k.value}: nobody is eligible to teach it ({info.num_sections} section(s) "
                    "will stay uncovered)",
                    (c, k.value),
                )
            )
            continue
        per_section = info.units if info.units > 0 else 1.0
        capacity = sum(math.floor(p.load_max / per_section + 1e-9) for p in eligible)
        if capacity < info.num_sections:
            names = ", ".join(p.id for p in eligible)
            out.append(
                Finding(
                    "warning",
                    "eligible_capacity",
                    f"{c} {k.value}: {info.num_sections} section(s) but the eligible professors "
                    f"({names}) can take at most {capacity} even with no other teaching",
                    (c, k.value),
                )
            )
    return out


def room_slot_capacity(instance: Instance, config: Config) -> list[Finding]:
    """Per distinct section capacity c: sections needing a room of >= c seats vs the
    (room, pattern) slots offering that many seats (room availability A_r applied).

    Slots of one room at overlapping patterns are counted separately, so this is an
    upper bound: a shortfall is certain, enough slots is not a guarantee.
    """
    pats = usable_patterns(instance, config.time.days)
    out: list[Finding] = []
    for cap in sorted({s.capacity for s in instance.sections}, reverse=True):
        need = [s for s in instance.sections if s.capacity >= cap]
        rooms = [r for r in instance.rooms if r.capacity >= cap]
        slots = sum(1 for r in rooms for t in pats if instance.room_available(r.id, t.id))
        if len(need) > slots:
            out.append(
                Finding(
                    "error",
                    "room_slots",
                    f"{len(need)} section(s) need a room with >= {cap} seats, but only {slots} "
                    "(room, time pattern) slot(s) offer that many",
                    (str(cap),),
                )
            )
    return out


def section_rooms(instance: Instance, config: Config) -> list[Finding]:
    """Per section: some room is large enough and of the right type; some pattern allows it."""
    out: list[Finding] = []
    usable = usable_patterns(instance, config.time.days)
    checked: set[tuple[str, object, int, str]] = set()
    for s in instance.sections:
        sig = (s.course_id, s.section_type, s.capacity, s.room_type)
        if sig in checked:
            continue
        checked.add(sig)
        if not any(room_problem(s, r) is None for r in instance.rooms):
            out.append(
                Finding(
                    "error",
                    "no_room",
                    f"{s.course_id} {s.section_type.value} (capacity {s.capacity}, type {s.room_type!r}): "
                    "no room is large enough and of the right type",
                    (s.course_id,),
                )
            )
        if not any(pattern_problem(instance, config, s, t) is None for t in usable):
            out.append(
                Finding(
                    "error",
                    "no_pattern",
                    f"{s.course_id} {s.section_type.value}: no usable time pattern allows this section type",
                    (s.course_id,),
                )
            )
    return out


def professor_alpha(
    instance: Instance, config: Config, assignments: Sequence[Assignment] | None
) -> list[Finding]:
    """alpha_p (A8) vs the sections assigned to p, or vs the minimum load."""
    out: list[Finding] = []
    days, buf = config.time.days, config.time.buffer_minutes
    assigned = Counter(a.professor_id for a in assignments or ())
    max_units = max((i.units for i in instance.offering_info.values()), default=1.0) or 1.0
    for p in instance.professors:
        a = alpha(instance, p.id, days, buf)
        if assignments is not None:
            need = assigned.get(p.id, 0)
            what = f"is assigned {need} section(s)"
        else:
            need = math.ceil(p.load_min / max_units - 1e-9)
            what = f"needs at least {need} section(s) to reach the minimum load {p.load_min:g}"
        if a < need:
            out.append(
                Finding(
                    "error" if assignments is not None else "warning",
                    "alpha",
                    f"{p.id} {what} but has only {a} non-overlapping available time pattern(s)",
                    (p.id,),
                )
            )
    return out


def group_capacity(instance: Instance, config: Config) -> list[Finding]:
    """Per conflict group: number of courses vs the number of disjoint usable time slots."""
    out: list[Finding] = []
    usable = usable_patterns(instance, config.time.days)
    slots = max_independent_patterns(usable, config.time.buffer_minutes)
    for g in conflict_groups(instance, config):
        offered = sorted(c for c in g.course_ids if c in instance.course_level)
        if len(offered) > slots:
            out.append(
                Finding(
                    "error" if g.mode.value == "hard" else "warning",
                    "group_capacity",
                    f"conflict group {g.id} has {len(offered)} courses but only {slots} "
                    "pairwise non-overlapping time patterns exist",
                    (g.id,),
                )
            )
    return out


def pin_conflicts(instance: Instance, config: Config) -> list[Finding]:
    """L4: pins that contradict the data."""
    out: list[Finding] = []
    for pin in instance.stage_a_pins:
        info = instance.offering_info.get((pin.course_id, pin.section_type))
        tag = f"pin {pin.professor_id}/{pin.course_id} {pin.section_type.value}"
        if pin.professor_id not in instance.professor_by_id:
            out.append(
                Finding("error", "pin_unknown", f"{tag}: unknown professor", (pin.professor_id,))
            )
        if info is None:
            out.append(
                Finding("error", "pin_unknown", f"{tag}: course/type not offered", (pin.course_id,))
            )
        elif pin.count > info.num_sections:
            out.append(
                Finding(
                    "error",
                    "pin_count",
                    f"{tag}: count {pin.count} > {info.num_sections} offered",
                    (pin.course_id,),
                )
            )
        reason = ineligibility_reason(
            instance, config, pin.professor_id, pin.course_id, pin.section_type
        )
        if reason is not None and config.enabled("A3"):
            out.append(
                Finding(
                    "warning",
                    "pin_overrides_eligibility",
                    f"{tag}: professor {reason}; the pin wins",
                    (pin.professor_id,),
                )
            )
        pre = instance.pre_assigned.get((pin.professor_id, pin.course_id, pin.section_type), 0)
        if pre > pin.count:
            out.append(
                Finding(
                    "error",
                    "pin_vs_pre",
                    f"{tag}: pinned to {pin.count} but pre-assigned {pre}",
                    (pin.professor_id,),
                )
            )
    for bpin in instance.stage_b_pins:
        key = (bpin.course_id, bpin.section_type, bpin.section_label)
        sid = f"{bpin.course_id}-{bpin.section_label}"
        sec = instance.section_by_key.get(key)
        if sec is None:
            out.append(Finding("error", "pin_unknown", f"pin {sid}: no such section", (sid,)))
            continue
        if bpin.pattern_id is not None:
            pat = instance.pattern_by_id.get(bpin.pattern_id)
            if pat is None:
                out.append(
                    Finding(
                        "error",
                        "pin_unknown",
                        f"pin {sid}: unknown pattern {bpin.pattern_id}",
                        (sid,),
                    )
                )
            else:
                problem = pattern_problem(instance, config, sec, pat)
                if problem is None and pattern_blocked(instance, pat.id):
                    problem = f"pattern {pat.id} intersects a blocked slot"
                if problem:
                    out.append(Finding("error", "pin_infeasible", f"pin {sid}: {problem}", (sid,)))
        if bpin.room_id is not None:
            room = instance.room_by_id.get(bpin.room_id)
            if room is None:
                out.append(
                    Finding(
                        "error", "pin_unknown", f"pin {sid}: unknown room {bpin.room_id}", (sid,)
                    )
                )
            elif (problem := room_problem(sec, room)) is not None:
                out.append(Finding("error", "pin_infeasible", f"pin {sid}: {problem}", (sid,)))
    return out


def stage_b_inputs(
    instance: Instance, config: Config, assignments: Sequence[Assignment]
) -> list[Finding]:
    """Stage B: every assigned section has at least one feasible (pattern, room)."""
    out: list[Finding] = []
    for a in assignments:
        if a.section_key not in instance.section_by_key:
            out.append(
                Finding(
                    "error",
                    "unknown_section",
                    f"assignments: {a.course_id}-{a.section_label} is not an offered section",
                    (a.course_id,),
                )
            )
    for sb in stage_b_sections(instance, assignments):
        if not _has_feasible_slot(instance, config, sb):
            out.append(
                Finding(
                    "error",
                    "no_feasible_slot",
                    f"{sb.id} ({sb.professor_id}): no time pattern and room combination is feasible "
                    "(check room sizes, allowed section types, blocked slots and unavailability)",
                    (sb.id, sb.professor_id),
                )
            )
    return out


def _has_feasible_slot(instance: Instance, config: Config, sb: StageBSection) -> bool:
    rooms_ok = [r for r in instance.rooms if room_problem(sb.section, r) is None]
    if not rooms_ok:
        return False
    for t in usable_patterns(instance, config.time.days):
        if pattern_problem(instance, config, sb.section, t) is not None:
            continue
        if all(not instance.room_available(r.id, t.id) for r in rooms_ok):
            continue
        if not is_placeholder(sb.professor_id) and professor_unavailable(
            instance, sb.professor_id, t.id
        ):
            continue
        return True
    return False


def unavailability_off_days(instance: Instance, config: Config) -> list[Finding]:
    """Info: unavailability on days that are not teaching days has no effect."""
    return [
        Finding(
            "info",
            "unavailability_off_day",
            f"{u.professor_id} is unavailable on {u.day}, not a teaching day",
        )
        for u in instance.unavailability
        if u.day not in config.time.days
    ]
