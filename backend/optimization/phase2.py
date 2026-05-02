"""
Phase 2: Schedule course sections into rooms and time slots.

solve_phase2(phase1_result, repo) -> Phase2Result

Bugs fixed vs. original:
  - Big-M re-enabled in room capacity constraint (RoomCapacityConstraint).
  - No-room-double-booking now groups by (room, timeslot_label) pair, not raw index.
  - `y` variable removed.
  - All constraint logic delegated to constraint classes.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING

import pandas as pd
import pulp
from pulp import LpMaximize, LpProblem, LpStatus, LpVariable, lpSum, value

from config import BIG_M, SLACK_PENALTY
from models.schedule import Phase2Assignment, Phase2Result
from optimization.constraints.scheduling import (
    CourseLevelConflictConstraint,
    NoProfDoubleBookingConstraint,
    NoRoomDoubleBookingConstraint,
    RoomCapacityConstraint,
)

if TYPE_CHECKING:
    from data.loaders import SchedulingDataRepository
    from models.schedule import Phase1Result


def _get_course_level(course_name: str):
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


def solve_phase2(
    phase1_result: "Phase1Result", repo: "SchedulingDataRepository"
) -> Phase2Result:
    """Run Phase 2 ILP and return a Phase2Result."""

    # -------------------------------------------------------------------
    # Build professor_course_df from Phase 1 assignments
    # -------------------------------------------------------------------
    rows = []
    capacity_map: dict[tuple, int] = {}
    for cs in repo.course_sections:
        capacity_map[(cs.code, cs.section_number)] = cs.capacity

    for assignment in phase1_result.assignments:
        for sec_0based in assignment.sections:
            sec_1based = sec_0based + 1
            cap = capacity_map.get((assignment.course, sec_1based), 0)
            rows.append(
                {
                    "professor": assignment.professor,
                    "course": assignment.course,
                    "section": sec_1based,
                    "capacity": cap,
                }
            )

    professor_course_df = pd.DataFrame(rows).reset_index(drop=True)
    professor_course_df = professor_course_df.reset_index()
    professor_course_df.set_index("index", inplace=True)

    # -------------------------------------------------------------------
    # Time preferences
    # -------------------------------------------------------------------
    time_preference_df = repo.get_time_preferences(repo.professors)

    # -------------------------------------------------------------------
    # Room timeslots
    # -------------------------------------------------------------------
    room_timeslots = repo.room_timeslots

    # Build time_groups: timeslot_label -> [rt.index, ...]
    time_groups: dict[str, list[int]] = defaultdict(list)
    for rt in room_timeslots:
        time_groups[rt.timeslot].append(rt.index)

    # -------------------------------------------------------------------
    # Course levels
    # -------------------------------------------------------------------
    courses = professor_course_df.index.tolist()
    course_levels = {
        c: _get_course_level(professor_course_df.loc[c, "course"]) for c in courses
    }

    timeslots = [rt.index for rt in room_timeslots]

    # -------------------------------------------------------------------
    # Decision variables
    # -------------------------------------------------------------------
    x = LpVariable.dicts(
        "schedule",
        ((c, t) for c in courses for t in timeslots),
        cat="Binary",
    )
    slack = LpVariable.dicts(
        "slack",
        (c for c in courses),
        lowBound=0,
        cat="Binary",
    )

    # -------------------------------------------------------------------
    # Build model
    # -------------------------------------------------------------------
    prob = LpProblem("Course_Scheduling", LpMaximize)

    # Objective: time preferences + count of scheduled courses - slack penalty
    rts_by_index = {rt.index: rt for rt in room_timeslots}
    objective = 0
    for c in courses:
        prof = professor_course_df.loc[c, "professor"]
        for t in timeslots:
            timeslot_label = rts_by_index[t].timeslot
            pref_weight = time_preference_df.loc[prof, timeslot_label]
            objective += pref_weight * x[c, t]

    objective += (
        lpSum(x[c, t] for c in courses for t in timeslots)
        - SLACK_PENALTY * lpSum(slack[c] for c in courses)
    )
    prob += objective

    # Each course section scheduled exactly once (or uses slack)
    for c in courses:
        prob += (
            lpSum(x[c, t] for t in timeslots) + slack[c] == 1,
            f"schedule_once_{c}",
        )

    # -------------------------------------------------------------------
    # Variables dict and data dict for constraints
    # -------------------------------------------------------------------
    variables = {
        "x": x,
        "slack": slack,
    }
    data = {
        "prof_courses_df": professor_course_df,
        "room_timeslots": room_timeslots,
        "time_groups": dict(time_groups),
        "course_levels": course_levels,
        "BIG_M": BIG_M,
    }

    # -------------------------------------------------------------------
    # Apply all constraints via constraint classes
    # -------------------------------------------------------------------
    constraints = [
        RoomCapacityConstraint(),
        NoRoomDoubleBookingConstraint(),
        NoProfDoubleBookingConstraint(),
        CourseLevelConflictConstraint(),
    ]
    for constraint in constraints:
        constraint.apply(prob, variables, data)

    # -------------------------------------------------------------------
    # Solve
    # -------------------------------------------------------------------
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    status_str = LpStatus[prob.status]

    # -------------------------------------------------------------------
    # Extract results
    # -------------------------------------------------------------------
    assignments: list[Phase2Assignment] = []
    unscheduled: list[str] = []

    base_courses = {c: professor_course_df.loc[c, "course"] for c in courses}
    course_sections_map = {c: professor_course_df.loc[c, "section"] for c in courses}
    full_ids = {c: f"{base_courses[c]}-{course_sections_map[c]}" for c in courses}

    for c in courses:
        slack_val = value(slack[c])
        if slack_val is not None and slack_val > 0.5:
            unscheduled.append(full_ids[c])
            continue
        for t in timeslots:
            if value(x[c, t]) is not None and value(x[c, t]) > 0.5:
                rt = rts_by_index[t]
                prof = professor_course_df.loc[c, "professor"]
                pref = time_preference_df.loc[prof, rt.timeslot]
                assignments.append(
                    Phase2Assignment(
                        course=base_courses[c],
                        section=int(course_sections_map[c]),
                        professor=prof,
                        timeslot=rt.timeslot,
                        room=rt.room,
                        course_capacity=int(professor_course_df.loc[c, "capacity"]),
                        room_capacity=rt.room_capacity,
                        professor_preference=float(pref),
                    )
                )
                break

    return Phase2Result(
        status=status_str,
        assignments=assignments,
        unscheduled=unscheduled,
    )
