"""
Room/time-scheduling constraints for Phase 2.

Classes
-------
RoomCapacityConstraint
    Course capacity must fit in the assigned room (with Big-M slack).
NoRoomDoubleBookingConstraint
    At most one course per (room, timeslot) pair.
NoProfDoubleBookingConstraint
    A professor cannot teach two courses in the same timeslot.
CourseLevelConflictConstraint
    At most one course per level (300/400/500) in any given timeslot.
"""

from __future__ import annotations

import re
from collections import defaultdict

from pulp import lpSum

from optimization.constraints.base import Constraint


def _get_course_level(course_name: str):
    """Extract 300/400/500 level from course name, or None."""
    match = re.search(r"(\d{3})", course_name)
    if match:
        level = int(match.group(1))
        if 300 <= level < 400:
            return 300
        elif 400 <= level < 500:
            return 400
        elif level >= 500:
            return 500
    return None


class RoomCapacityConstraint(Constraint):
    """
    course_capacity * x[c, t] <= room_capacity + BIG_M * slack[c]

    Fixes original bug 3: the Big-M was commented out, making the problem
    unnecessarily infeasible when a course does not fit in any room.
    """

    name = "room_capacity"

    def apply(self, model, variables: dict, data: dict) -> None:
        x = variables["x"]
        slack = variables["slack"]
        prof_courses_df = data["prof_courses_df"]
        room_timeslots = data["room_timeslots"]
        big_m = data["BIG_M"]

        courses = prof_courses_df.index.tolist()
        timeslots = [rt.index for rt in room_timeslots]
        rts_by_index = {rt.index: rt for rt in room_timeslots}

        for c in courses:
            course_capacity = int(prof_courses_df.loc[c, "capacity"])
            for t in timeslots:
                rt = rts_by_index[t]
                room_capacity = rt.room_capacity
                model += (
                    course_capacity * x[c, t]
                    <= room_capacity + big_m * slack[c],
                    f"room_cap_{c}_{t}",
                )


class NoRoomDoubleBookingConstraint(Constraint):
    """
    At most one course per (room, timeslot_label) pair.

    Fixes original bug 5: the original checked per raw timeslot index (one row),
    which allowed multiple courses in different rows that share the same room+timeslot.
    We now group room-timeslots by (room, timeslot_label) and enforce sum <= 1 per pair.
    """

    name = "no_room_double_booking"

    def apply(self, model, variables: dict, data: dict) -> None:
        x = variables["x"]
        prof_courses_df = data["prof_courses_df"]
        room_timeslots = data["room_timeslots"]

        courses = prof_courses_df.index.tolist()

        # Group room-timeslot indices by (room, timeslot_label)
        room_time_groups: dict[tuple, list[int]] = defaultdict(list)
        for rt in room_timeslots:
            room_time_groups[(rt.room, rt.timeslot)].append(rt.index)

        for (room, timeslot_label), t_indices in room_time_groups.items():
            model += (
                lpSum(x[c, t] for c in courses for t in t_indices) <= 1,
                f"no_room_double_{room}_{timeslot_label}".replace(" ", "_"),
            )


class NoProfDoubleBookingConstraint(Constraint):
    """A professor cannot teach two courses in the same timeslot."""

    name = "no_prof_double_booking"

    def apply(self, model, variables: dict, data: dict) -> None:
        x = variables["x"]
        prof_courses_df = data["prof_courses_df"]
        room_timeslots = data["room_timeslots"]
        time_groups = data["time_groups"]  # timeslot_label -> [rt_index, ...]

        professors = prof_courses_df["professor"].unique().tolist()

        for prof in professors:
            prof_courses = prof_courses_df[
                prof_courses_df["professor"] == prof
            ].index.tolist()
            for time_label, t_indices in time_groups.items():
                model += (
                    lpSum(x[c, t] for c in prof_courses for t in t_indices) <= 1,
                    f"no_prof_double_{prof}_{time_label}".replace(" ", "_"),
                )


class CourseLevelConflictConstraint(Constraint):
    """
    At most one course of each level (300, 400, 500) per timeslot.
    Prevents two 300-level courses (for example) from being scheduled simultaneously.
    """

    name = "course_level_conflict"

    def apply(self, model, variables: dict, data: dict) -> None:
        x = variables["x"]
        prof_courses_df = data["prof_courses_df"]
        time_groups = data["time_groups"]
        course_levels = data["course_levels"]

        courses = prof_courses_df.index.tolist()

        courses_300 = [c for c in courses if course_levels.get(c) == 300]
        courses_400 = [c for c in courses if course_levels.get(c) == 400]
        courses_500 = [c for c in courses if course_levels.get(c) == 500]

        for time_label, t_indices in time_groups.items():
            label_safe = str(time_label).replace(" ", "_")
            if courses_300:
                model += (
                    lpSum(x[c, t] for c in courses_300 for t in t_indices) <= 1,
                    f"level_300_{label_safe}",
                )
            if courses_400:
                model += (
                    lpSum(x[c, t] for c in courses_400 for t in t_indices) <= 1,
                    f"level_400_{label_safe}",
                )
            if courses_500:
                model += (
                    lpSum(x[c, t] for c in courses_500 for t in t_indices) <= 1,
                    f"level_500_{label_safe}",
                )
