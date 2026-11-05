"""Config-dependent rules shared by the model, the validator and diagnostics.

One implementation per rule keeps the MILP and the independent validator honest: the
model *filters* with these predicates, the validator *checks* with them.
Plain Python only: no PuLP, no pandas.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from scheduler.config import A10Settings, Config, Mode
from scheduler.domain import (
    Assignment,
    FamilyMixing,
    Instance,
    OfferingKey,
    Room,
    Section,
    SectionKey,
    SectionType,
    TimePattern,
    is_placeholder,
    label_sort_key,
)
from scheduler.time import (
    blocked_pattern_ids,
    off_day_pattern_ids,
    professor_patterns,
    unavailable_pattern_ids,
    usable_patterns,
)

# ----- Stage A ------------------------------------------------------------------


def stage_a_offering_keys(instance: Instance, config: Config) -> tuple[OfferingKey, ...]:
    """(c, k) pairs staffed by Stage A; recitations are excluded under A7 ``external``."""
    external = config.enabled("A7") and config.recitations.staffing == "external"
    return tuple(
        key for key in instance.offering_keys if not (external and key[1] is SectionType.R)
    )


def is_overridden(
    instance: Instance, professor_id: str, course_id: str, section_type: SectionType
) -> bool:
    """A pre-assignment (A4) or a Stage A pin (L4) for (p, c, k) overrides eligibility."""
    key = (professor_id, course_id, section_type)
    return key in instance.pre_assigned or key in instance.stage_a_pin_counts


def ineligibility_reason(
    instance: Instance,
    config: Config,
    professor_id: str,
    course_id: str,
    section_type: SectionType,
) -> str | None:
    """Why (p, c, k) is ineligible under A3, or None if eligible.

    Ineligible if the rank of (p, c, k) (typed row, else course row; SPEC §3.4) is
    ``cannot``, or (p, c, k) is unranked and the policy is ``forbid``.
    """
    key = (professor_id, course_id, section_type)
    ranks = instance.course_type_rank
    if key in ranks and ranks[key] is None:
        return "marked cannot teach"
    if key not in ranks and config.preferences.unranked_policy == "forbid":
        return "unranked (unranked_policy = forbid)"
    return None


def is_eligible(
    instance: Instance,
    config: Config,
    professor_id: str,
    course_id: str,
    section_type: SectionType,
) -> bool:
    """A3 eligibility of (p, c, k), including the pre-assignment / pin override."""
    if not config.enabled("A3"):
        return True
    if is_overridden(instance, professor_id, course_id, section_type):
        return True
    return ineligibility_reason(instance, config, professor_id, course_id, section_type) is None


def outside_top_k(
    instance: Instance,
    config: Config,
    professor_id: str,
    course_id: str,
    section_type: SectionType,
) -> str | None:
    """Why (p, c, k) is outside the professor's top K under A10, or None if inside/exempt.

    Outside if the rank rho^C_{p,c,k} (SPEC §3.4) is > K = ``max_rank``, ``cannot``, or
    unranked. A pre-assignment or pin exempts (p, c, k), as for A3.
    """
    if is_overridden(instance, professor_id, course_id, section_type):
        return None
    k_max = config.typed_settings("A10", A10Settings).max_rank
    key = (professor_id, course_id, section_type)
    ranks = instance.course_type_rank
    if key not in ranks:
        return f"unranked, outside the top {k_max}"
    rank = ranks[key]
    if rank is None:
        return f"marked cannot teach, outside the top {k_max}"
    if rank > k_max:
        return f"rank {rank} is outside the top {k_max}"
    return None


# ----- conflict groups (B5) -------------------------------------------------------


@dataclass(frozen=True)
class ResolvedGroup:
    """A conflict group with its effective mode and weight."""

    id: str
    course_ids: frozenset[str]
    mode: Mode
    weight: float


def level_group_id(level: int) -> str | None:
    """Automatic level group of a course level (SPEC B5)."""
    if 300 <= level < 400:
        return "level_300"
    if 400 <= level < 500:
        return "level_400"
    if level >= 500:
        return "graduate"
    return None


def conflict_groups(instance: Instance, config: Config) -> tuple[ResolvedGroup, ...]:
    """Groups from the input file plus automatic level groups; empty if B5 is off.

    Groups with fewer than two courses are dropped (they cannot conflict).
    """
    settings = config.settings("B5")
    if settings.mode is Mode.OFF:
        return ()
    out: dict[str, ResolvedGroup] = {}
    if config.conflict_groups.auto_levels:
        by_level: dict[str, set[str]] = {}
        for course, level in instance.course_level.items():
            gid = level_group_id(level)
            if gid is not None:
                by_level.setdefault(gid, set()).add(course)
        for gid, courses in by_level.items():
            out[gid] = ResolvedGroup(gid, frozenset(courses), settings.mode, settings.weight)
    for g in instance.conflict_groups:
        mode = Mode(g.mode) if g.mode is not None else settings.mode
        weight = g.weight if g.weight is not None else settings.weight
        out[g.id] = ResolvedGroup(g.id, g.course_ids, mode, weight)
    return tuple(out[k] for k in sorted(out) if len(out[k].course_ids) >= 2)


# ----- Stage B sections and placement feasibility -------------------------------------


@dataclass(frozen=True)
class StageBSection:
    """A section to timetable together with its instructor (S_p)."""

    section: Section
    professor_id: str

    @property
    def key(self) -> SectionKey:
        return self.section.key

    @property
    def id(self) -> str:
        return self.section.id

    @property
    def placeholder(self) -> bool:
        return is_placeholder(self.professor_id)


def stage_b_sections(
    instance: Instance, assignments: Iterable[Assignment]
) -> tuple[StageBSection, ...]:
    """Sections from the hand-off file joined with the instance; unknown labels are skipped.

    If a label is listed twice, the first row (by professor ID) wins; the validator
    reports duplicates under A1.
    """
    seen: dict[SectionKey, StageBSection] = {}
    for a in sorted(assignments, key=lambda a: (a.professor_id, a.section_key[0], a.section_label)):
        sec = instance.section_by_key.get(a.section_key)
        if sec is not None and a.section_key not in seen:
            seen[a.section_key] = StageBSection(sec, a.professor_id)
    return tuple(
        seen[k] for k in sorted(seen, key=lambda k: (k[0], k[1].value, label_sort_key(k[2])))
    )


def room_problem(section: Section, room: Room) -> str | None:
    """Why ``room`` cannot host ``section`` (capacity, type), or None."""
    if room.capacity < section.capacity:
        return f"room {room.id} holds {room.capacity} < {section.capacity}"
    if room.room_type != section.room_type:
        return f"room {room.id} is {room.room_type!r}, section needs {section.room_type!r}"
    return None


def pattern_problem(
    instance: Instance, config: Config, section: Section, pattern: TimePattern
) -> str | None:
    """Why ``pattern`` can never host ``section`` (type not allowed, off-day), or None.

    Blocked slots and unavailability belong to B4 and are tested separately.
    """
    if not pattern.allows(section.section_type):
        return f"pattern {pattern.id} does not allow {section.section_type.value} sections"
    if pattern.id in off_day_pattern_ids(instance, config.time.days):
        return f"pattern {pattern.id} meets on a non-teaching day"
    return None


def pattern_blocked(instance: Instance, pattern_id: str) -> bool:
    """B4: some meeting of t intersects a blocked slot."""
    return pattern_id in blocked_pattern_ids(instance)


def professor_unavailable(instance: Instance, professor_id: str, pattern_id: str) -> bool:
    """B4: p is unavailable at some meeting of t (or ranked t ``cannot``)."""
    return pattern_id in unavailable_pattern_ids(instance, professor_id)


def room_unavailable(instance: Instance, room_id: str, pattern_id: str) -> bool:
    """Room availability: t not in A_r (always filtered from F; reported under B4)."""
    return not instance.room_available(room_id, pattern_id)


# ----- B13 day families -------------------------------------------------------------


def off_family(instance: Instance, professor_id: str, pattern_id: str) -> bool:
    """B13: p has preferred day families Phi_p and f(t) is not one of them."""
    prof = instance.professor_by_id.get(professor_id)
    if prof is None or not prof.day_families or is_placeholder(professor_id):
        return False
    return instance.pattern_by_id[pattern_id].family not in prof.day_families


def family_mixing(instance: Instance, config: Config, professor_id: str) -> FamilyMixing:
    """chi_p as enforced: ``avoid`` becomes ``forbid`` when B13 is hard; placeholders allow."""
    prof = instance.professor_by_id.get(professor_id)
    if prof is None or is_placeholder(professor_id):
        return FamilyMixing.ALLOW
    if prof.day_family_mixing is FamilyMixing.AVOID and config.mode("B13") is Mode.HARD:
        return FamilyMixing.FORBID
    return prof.day_family_mixing


# ----- missing data (SPEC §4 *Not checked*, D13) --------------------------------------

A8_PROFESSORS = "professors"
A8_ROOMS = "rooms"
A8_GROUPS = "groups"
A8_PART_INPUTS: dict[str, tuple[str, ...]] = {
    A8_PROFESSORS: ("time_patterns",),
    A8_ROOMS: ("time_patterns", "rooms"),
    A8_GROUPS: ("time_patterns",),
}
"""A8 parts (SPEC §5.2 *Missing data*) and the tables each one needs."""
A8_PART_NAMES = {
    A8_PROFESSORS: "per-professor capacity alpha_p",
    A8_ROOMS: "day-family room capacity kappa_f",
    A8_GROUPS: "day-family conflict-group capacity",
}


@dataclass(frozen=True)
class NotChecked:
    """A constraint part that is not built or validated because its inputs are absent."""

    cid: str
    part: str
    missing: tuple[str, ...]

    def __str__(self) -> str:
        tables = ", ".join(self.missing)
        return f"{self.cid} {self.part}: not checked (no {tables} table)"


def a8_part_active(instance: Instance, config: Config, part: str) -> bool:
    """Whether A8 part ``part`` is built and validated: A8 enabled, the part applies
    (rooms and groups only with B13 hard) and its input tables are present."""
    if not config.enabled("A8") or instance.missing(A8_PART_INPUTS[part]):
        return False
    return part == A8_PROFESSORS or config.mode("B13") is Mode.HARD


def stage_a_not_checked(instance: Instance, config: Config) -> tuple[NotChecked, ...]:
    """Stage A constraint parts that cannot be built for lack of data (never ``off`` ones)."""
    if not config.enabled("A8"):
        return ()
    parts = [A8_PROFESSORS]
    if config.mode("B13") is Mode.HARD:
        parts += [A8_ROOMS, A8_GROUPS]
    out = []
    for part in parts:
        if missing := instance.missing(A8_PART_INPUTS[part]):
            out.append(NotChecked("A8", A8_PART_NAMES[part], missing))
    return tuple(out)


# ----- A8 with day families (B13 hard) -------------------------------------------------


def professor_pattern_sets(
    instance: Instance, config: Config, professor_id: str
) -> tuple[tuple[TimePattern, ...], ...]:
    """A8: the pattern sets alpha_p is the maximum over.

    T_p (available patterns) as a single set; when B13 is hard, T_p keeps only f(t) in Phi_p
    and, unless chi_p is ``allow``, splits into one set T_p^f per family.
    """
    pats = professor_patterns(instance, professor_id, config.time.days)
    if config.mode("B13") is not Mode.HARD:
        return (pats,)
    pats = tuple(t for t in pats if not off_family(instance, professor_id, t.id))
    if family_mixing(instance, config, professor_id) is FamilyMixing.ALLOW:
        return (pats,)
    families = sorted({t.family for t in pats})
    return tuple(tuple(t for t in pats if t.family == f) for f in families) or ((),)


def pinned_family(instance: Instance, config: Config, professor_id: str) -> str | None:
    """A8: f if B13 is hard and Phi_p = {f} (p is in P_f); None otherwise."""
    if config.mode("B13") is not Mode.HARD or is_placeholder(professor_id):
        return None
    prof = instance.professor_by_id.get(professor_id)
    if prof is None or len(prof.day_families) != 1:
        return None
    return next(iter(prof.day_families))


def family_patterns(instance: Instance, config: Config, family: str) -> tuple[TimePattern, ...]:
    """A8: U^f, the usable patterns of family f."""
    return tuple(t for t in usable_patterns(instance, config.time.days) if t.family == family)


def offering_rooms(instance: Instance, offering: OfferingKey) -> frozenset[str]:
    """A8: R(c,k), the rooms large enough and of the right type for every section of (c, k)."""
    secs = instance.sections_by_offering.get(offering, ())
    return frozenset(r.id for r in instance.rooms if all(room_problem(s, r) is None for s in secs))


def family_room_pattern_sets(
    instance: Instance, config: Config, family: str, rooms: frozenset[str] | None = None
) -> tuple[tuple[TimePattern, ...], ...]:
    """A8: per room r in R* (default: all rooms), the usable patterns of family f in A_r;
    kappa_f(R*) sums their alphas."""
    pats = family_patterns(instance, config, family)
    return tuple(
        tuple(t for t in pats if instance.room_available(r.id, t.id))
        for r in sorted(instance.rooms, key=lambda r: r.id)
        if rooms is None or r.id in rooms
    )


def room_set_label(rooms: frozenset[str]) -> str:
    """Readable R* for messages."""
    return ", ".join(sorted(rooms))


def hard_group_families(
    instance: Instance, config: Config
) -> tuple[tuple[ResolvedGroup, str], ...]:
    """A8: (hard conflict group g, family f) pairs with P_f non-empty, sorted."""
    families = sorted(
        {f for p in instance.professor_ids if (f := pinned_family(instance, config, p))}
    )
    groups = [g for g in conflict_groups(instance, config) if g.mode is Mode.HARD]
    return tuple((g, f) for g in groups for f in families)


# ----- A7 same_as_lecture ------------------------------------------------------------


def recitation_band(lectures: int, total_lectures: int, total_recitations: int) -> tuple[int, int]:
    """A7 ``same_as_lecture``: recitations a professor with ``lectures`` of the
    ``total_lectures`` lecture sections takes, as the integer band around their share:

        floor(N_R * n_L / N_L) <= n_R <= ceil(N_R * n_L / N_L)

    Linear form (n integer): N_L n_R >= N_R n_L - (N_L - 1) and N_L n_R <= N_R n_L + (N_L - 1).
    Professors without lectures of the course take no recitations.
    """
    if total_lectures <= 0:
        return (0, total_recitations)
    lo = (total_recitations * lectures) // total_lectures
    hi = -(-(total_recitations * lectures) // total_lectures)
    return (lo, hi)


def courses_with_lectures_and_recitations(instance: Instance) -> tuple[str, ...]:
    """Courses offering both lecture and recitation sections."""
    info = instance.offering_info
    return tuple(
        c
        for c in instance.course_ids
        if info.get((c, SectionType.L)) is not None
        and info.get((c, SectionType.R)) is not None
        and info[(c, SectionType.L)].num_sections > 0
        and info[(c, SectionType.R)].num_sections > 0
    )


def linked_lectures(instance: Instance, recitation: Section) -> tuple[Section, ...]:
    """B7: the lecture linked to a recitation, or every lecture of its course if unlinked."""
    for link in instance.section_links:
        if link.course_id == recitation.course_id and link.recitation_label == recitation.label:
            lec = instance.section_by_key.get((link.course_id, SectionType.L, link.lecture_label))
            return (lec,) if lec else ()
    return instance.sections_by_offering.get((recitation.course_id, SectionType.L), ())
