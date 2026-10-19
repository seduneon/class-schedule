"""Config-dependent rules shared by the model, the validator and diagnostics.

One implementation per rule keeps the MILP and the independent validator honest: the
model *filters* with these predicates, the validator *checks* with them.
Plain Python only: no PuLP, no pandas.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from scheduler.config import Config, Mode
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
from scheduler.time import blocked_pattern_ids, off_day_pattern_ids, unavailable_pattern_ids

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
