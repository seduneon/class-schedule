"""B7 — Recitation–lecture relation."""

from __future__ import annotations

from scheduler.config import B7Settings, Config, ConstraintSettings
from scheduler.derived import linked_lectures
from scheduler.domain import Instance, SectionType, Solution
from scheduler.time import earliest_meeting, patterns_overlap
from scheduler.validation.core import Violation, check, severity_for
from scheduler.validation.view import placed_sections


@check("B7")
def check_b7(
    instance: Instance, solution: Solution, settings: ConstraintSettings, config: Config
) -> list[Violation]:
    """A recitation must not overlap its linked lecture (every lecture of the course if
    unlinked). With ``recitation_after_first_lecture`` it must not start before the
    earliest weekly meeting of that lecture."""
    after = isinstance(settings, B7Settings) and settings.recitation_after_first_lecture
    placed = {x.placement.section_key: x for x in placed_sections(instance, solution)}
    sev = severity_for(settings)
    out = []
    for key, rec in sorted(placed.items(), key=lambda kv: kv[1].label):
        if key[1] is not SectionType.R:
            continue
        for lec_section in linked_lectures(instance, rec.section.section):
            lec = placed.get(lec_section.key)
            if lec is None:
                continue
            if patterns_overlap(rec.pattern, lec.pattern, config.time.buffer_minutes):
                out.append(
                    Violation(
                        "B7",
                        sev,
                        f"recitation {rec.label} overlaps lecture {lec.label}",
                        (rec.label, lec.label),
                    )
                )
            if after and earliest_meeting(rec.pattern) < earliest_meeting(lec.pattern):
                out.append(
                    Violation(
                        "B7",
                        sev,
                        f"recitation {rec.label} ({rec.pattern.id}) starts the week before "
                        f"lecture {lec.label} ({lec.pattern.id})",
                        (rec.label, lec.label),
                    )
                )
    return out
