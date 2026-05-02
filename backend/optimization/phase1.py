"""
Phase 1: Assign professors to course sections.

solve_phase1(repo) -> Phase1Result

Bugs fixed vs. original:
  - Relaxation dicts renamed to prof_relax / section_relax / preferred_relax /
    multi_section_relax (no single-letter names that shadow loop variables).
  - `y` variable (declared but never used) removed entirely.
  - pre_assignments undefined reference removed (was dead code).
  - All constraint logic lives in constraint classes, not inline here.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import pulp
from pulp import LpMaximize, LpProblem, LpStatus, LpVariable, lpSum, value

from config import PENALTY_WEIGHT
from models.schedule import Phase1Assignment, Phase1Result
from optimization.constraints.preferences import (
    MultiSectionConstraint,
    PreferredCoursesLoadConstraint,
    PreferredCoursesOnlyConstraint,
)
from optimization.constraints.workload import (
    CourseSectionFillConstraint,
    OneSectionPerSlotConstraint,
    ProfessorLoadConstraint,
)

if TYPE_CHECKING:
    from data.loaders import SchedulingDataRepository


def solve_phase1(repo: "SchedulingDataRepository") -> Phase1Result:
    """Run the Phase 1 ILP and return a Phase1Result."""

    professors_list = [prof.last_name for prof in repo.professors]
    course_list = list(repo.course_dict.keys())
    course_dict = repo.course_dict
    load_dict = repo.load_dict
    w_by_course = repo.w_by_course
    assigned_dict = repo.assigned_dict
    preferred_courses = repo.preferred_courses
    modified_preferences = repo.modified_preferences
    two_section_pref = repo.two_section_pref

    # -------------------------------------------------------------------
    # Build pre-assignment tracking structures
    # -------------------------------------------------------------------
    assigned_slots: set = set()
    prof_preassigned_count: dict[str, int] = defaultdict(int)
    course_preassigned_count: dict[str, int] = defaultdict(int)

    for prof in assigned_dict:
        for course in assigned_dict[prof]:
            sections = assigned_dict[prof][course]
            prof_preassigned_count[prof] += len(sections)
            course_preassigned_count[course] += len(sections)
            for sec in sections:
                assigned_slots.add((prof, course, sec))

    # -------------------------------------------------------------------
    # Decision variables
    # -------------------------------------------------------------------
    # x[i, j, k] = 1 if professor i teaches section k of course j (new only)
    x = LpVariable.dicts(
        "assigned",
        (
            (i, j, k)
            for i in professors_list
            for j in course_list
            for k in range(course_dict[j])
            if (i, j, k) not in assigned_slots
        ),
        cat="Binary",
    )

    # Relaxation variables — named to avoid collision with loop variables
    prof_relax = LpVariable.dicts(
        "prof_relax", professors_list, lowBound=0
    )
    section_relax = LpVariable.dicts(
        "section_relax", course_list, lowBound=0
    )
    preferred_relax = LpVariable.dicts(
        "preferred_relax", professors_list, lowBound=0
    )
    multi_section_relax = LpVariable.dicts(
        "multi_section_relax",
        (
            (i, j)
            for i in professors_list
            for j in course_list
            if two_section_pref.get(i, 0) == -1
        ),
        lowBound=0,
    )

    # -------------------------------------------------------------------
    # Build model
    # -------------------------------------------------------------------
    prob = LpProblem("Professor_Course_Assignment", LpMaximize)

    # Objective: maximize weighted preferences, penalize all slack
    prob += (
        lpSum(
            modified_preferences.loc[i, j] * x[i, j, k]
            for i in professors_list
            for j in course_list
            for k in range(course_dict[j])
            if (i, j, k) not in assigned_slots and (i, j, k) in x
        )
        - PENALTY_WEIGHT * lpSum(prof_relax[i] for i in professors_list)
        - PENALTY_WEIGHT * lpSum(section_relax[j] for j in course_list)
        - PENALTY_WEIGHT * lpSum(preferred_relax[i] for i in professors_list)
        - PENALTY_WEIGHT
        * lpSum(
            multi_section_relax[i, j]
            for i in professors_list
            for j in course_list
            if two_section_pref.get(i, 0) == -1 and (i, j) in multi_section_relax
        )
    )

    # -------------------------------------------------------------------
    # Variables dict and data dict for constraints
    # -------------------------------------------------------------------
    variables = {
        "x": x,
        "prof_relax": prof_relax,
        "section_relax": section_relax,
        "preferred_relax": preferred_relax,
        "multi_section_relax": multi_section_relax,
    }
    data = {
        "professors_list": professors_list,
        "course_list": course_list,
        "course_dict": course_dict,
        "load_dict": load_dict,
        "w_by_course": w_by_course,
        "assigned_dict": assigned_dict,
        "assigned_slots": assigned_slots,
        "prof_preassigned_count": prof_preassigned_count,
        "course_preassigned_count": course_preassigned_count,
        "preferred_courses": preferred_courses,
        "two_section_pref": two_section_pref.to_dict(),
    }

    # -------------------------------------------------------------------
    # Apply all constraints via constraint classes
    # -------------------------------------------------------------------
    constraints = [
        OneSectionPerSlotConstraint(),
        ProfessorLoadConstraint(),
        CourseSectionFillConstraint(),
        PreferredCoursesOnlyConstraint(),
        PreferredCoursesLoadConstraint(),
        MultiSectionConstraint(),
    ]
    for constraint in constraints:
        constraint.apply(prob, variables, data)

    # -------------------------------------------------------------------
    # Solve
    # -------------------------------------------------------------------
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    # -------------------------------------------------------------------
    # Extract results
    # -------------------------------------------------------------------
    status_str = LpStatus[prob.status]
    obj_val = value(prob.objective)

    assignments: list[Phase1Assignment] = []

    # Pre-assigned entries
    for prof in assigned_dict:
        for course in assigned_dict[prof]:
            sections = assigned_dict[prof][course]
            assignments.append(
                Phase1Assignment(
                    professor=prof,
                    course=course,
                    sections=sections,
                    status="Pre-assigned",
                )
            )

    # New assignments from solver
    prof_total_sections: dict[str, int] = defaultdict(int)
    for prof in assigned_dict:
        prof_total_sections[prof] = sum(
            len(secs) for secs in assigned_dict[prof].values()
        )

    for i in professors_list:
        for j in course_list:
            new_sections = []
            for k in range(course_dict[j]):
                if (i, j, k) not in assigned_slots:
                    var = x.get((i, j, k))
                    if var is not None and value(var) == 1:
                        new_sections.append(k)
            if new_sections:
                prof_total_sections[i] += len(new_sections)
                assignments.append(
                    Phase1Assignment(
                        professor=i,
                        course=j,
                        sections=new_sections,
                        status="New",
                    )
                )

    unassigned_professors = [
        i for i in professors_list if value(prof_relax[i]) is not None and value(prof_relax[i]) > 0
    ]
    unfilled_courses = [
        j for j in course_list if value(section_relax[j]) is not None and value(section_relax[j]) > 0
    ]

    return Phase1Result(
        status=status_str,
        objective_value=obj_val,
        assignments=assignments,
        unassigned_professors=unassigned_professors,
        unfilled_courses=unfilled_courses,
        professor_loads=dict(prof_total_sections),
    )
