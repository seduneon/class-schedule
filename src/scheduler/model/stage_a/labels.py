"""Label attachment: expand Stage A counts into labeled sections (SPEC §5.4)."""

from __future__ import annotations

from collections.abc import Mapping

from scheduler.config import Config
from scheduler.domain import (
    Assignment,
    Instance,
    OfferingKey,
    SectionType,
    Source,
    label_index,
    placeholder_for,
    section_label,
)

CountKey = tuple[str, str, SectionType]


def attach_labels(instance: Instance, counts: Mapping[CountKey, int]) -> tuple[Assignment, ...]:
    """Turn n_{p,c,k} into labeled assignments.

    Rule (deterministic, editable afterwards by the chair):
    1. Labels named in pre-assignments go to their professors first.
    2. Remaining labels, in label order (1L, 2L, ...; larger capacities have lower labels),
       go to professors in ID order, each taking its remaining count.
    3. A professor's first ``pre_{p,c,k}`` sections are marked ``pre``, the rest ``model``.
    If counts exceed the offered sections (only possible with A1 off), extra labels beyond
    N_{c,k} are created so the validator can report them.
    """
    out: list[Assignment] = []
    offering_keys: set[OfferingKey] = {(c, k) for (_p, c, k) in counts}
    for c, k in sorted(offering_keys, key=lambda ck: (ck[0], ck[1].value)):
        remaining = {p: n for (p, cc, kk), n in counts.items() if (cc, kk) == (c, k) and n > 0}
        sections = list(instance.sections_by_offering.get((c, k), ()))
        free = [s.label for s in sections]
        owner: dict[str, str] = {}
        for pa in sorted(instance.pre_assignments, key=lambda a: a.professor_id):
            if (pa.course_id, pa.section_type) != (c, k):
                continue
            for label in pa.section_labels:
                if label in free and remaining.get(pa.professor_id, 0) > 0:
                    owner[label] = pa.professor_id
                    free.remove(label)
                    remaining[pa.professor_id] -= 1
        next_extra = len(sections) + 1
        for p in sorted(remaining):
            for _ in range(remaining[p]):
                if free:
                    owner[free.pop(0)] = p
                else:
                    owner[section_label(next_extra, k)] = p
                    next_extra += 1
        by_label = {s.label: s for s in sections}
        info = instance.offering_info.get((c, k))
        pre_left = {p: instance.pre_assigned.get((p, c, k), 0) for p in set(owner.values())}
        labelled_pre = {
            label
            for pa in instance.pre_assignments
            if (pa.course_id, pa.section_type) == (c, k)
            for label in pa.section_labels
            if owner.get(label) == pa.professor_id
        }
        for label in sorted(owner, key=lambda lbl: (lbl not in labelled_pre, label_index(lbl))):
            p = owner[label]
            sec = by_label.get(label)
            source = Source.MODEL
            if pre_left.get(p, 0) > 0:
                source = Source.PRE
                pre_left[p] -= 1
            out.append(
                Assignment(
                    professor_id=p,
                    course_id=c,
                    section_type=k,
                    section_label=label,
                    capacity=sec.capacity if sec else (sections[-1].capacity if sections else 0),
                    units=sec.units if sec else (info.units if info else 0.0),
                    source=source,
                )
            )
    return tuple(
        sorted(
            out,
            key=lambda a: (
                a.professor_id,
                a.course_id,
                a.section_type.value,
                label_index(a.section_label),
            ),
        )
    )


def external_assignments(instance: Instance, config: Config) -> tuple[Assignment, ...]:
    """A7 ``external``: recitations go to Stage B with placeholder ``TBA-<course>``."""
    if not (config.enabled("A7") and config.recitations.staffing == "external"):
        return ()
    return tuple(
        Assignment(
            placeholder_for(s.course_id),
            s.course_id,
            s.section_type,
            s.label,
            s.capacity,
            s.units,
            Source.MODEL,
        )
        for s in instance.sections
        if s.section_type is SectionType.R
    )
