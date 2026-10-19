"""Stage A constraint builders; importing this package registers them."""

from scheduler.model.stage_a.constraints import (
    a01_coverage,
    a02_load,
    a03_eligibility,
    a04_pre_assignments,
    a05_multi_section,
    a06_max_preps,
    a07_recitation_staffing,
    a08_timetable_capacity,
    a09_course_fairness,
)

__all__ = [
    "a01_coverage",
    "a02_load",
    "a03_eligibility",
    "a04_pre_assignments",
    "a05_multi_section",
    "a06_max_preps",
    "a07_recitation_staffing",
    "a08_timetable_capacity",
    "a09_course_fairness",
]
