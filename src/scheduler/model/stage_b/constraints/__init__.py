"""Stage B constraint builders; importing this package registers them."""

from scheduler.model.stage_b.constraints import (
    b01_once,
    b02_room_overlap,
    b03_professor_overlap,
    b04_unavailability,
    b05_conflict_groups,
    b06_spread_sections,
    b07_recitation_lecture,
    b08_max_days,
    b09_back_to_back,
    b10_max_consecutive,
    b11_room_stability,
    b12_time_fairness,
    b13_day_family,
)

__all__ = [
    "b01_once",
    "b02_room_overlap",
    "b03_professor_overlap",
    "b04_unavailability",
    "b05_conflict_groups",
    "b06_spread_sections",
    "b07_recitation_lecture",
    "b08_max_days",
    "b09_back_to_back",
    "b10_max_consecutive",
    "b11_room_stability",
    "b12_time_fairness",
    "b13_day_family",
]
