"""
Course-preference constraints for Phase 1.

Classes
-------
PreferredCoursesOnlyConstraint
    Professor cannot be assigned a course outside their preference list.
PreferredCoursesLoadConstraint
    Professor's preferred-course assignments == load (with preferred_relax slack).
MultiSectionConstraint
    For professors who prefer not to teach multiple sections of the same course,
    each (prof, course) pair is limited to <= 1 section (with multi_section_relax).
"""

from __future__ import annotations

from pulp import lpSum

from optimization.constraints.base import Constraint


class PreferredCoursesOnlyConstraint(Constraint):
    """Professor cannot be assigned non-preferred courses (sum of non-preferred == 0)."""

    name = "preferred_courses_only"

    def apply(self, model, variables: dict, data: dict) -> None:
        x = variables["x"]
        assigned_slots = data["assigned_slots"]
        professors_list = data["professors_list"]
        course_list = data["course_list"]
        course_dict = data["course_dict"]
        preferred_courses = data["preferred_courses"]

        for i in professors_list:
            non_pref = lpSum(
                x.get((i, j, k), 0)
                for j in course_list
                if j not in preferred_courses[i]
                for k in range(course_dict[j])
                if (i, j, k) not in assigned_slots
            )
            model += (non_pref == 0, f"pref_only_{i}")


class PreferredCoursesLoadConstraint(Constraint):
    """
    Sum of preferred-course section assignments (pre + new) + preferred_relax == load.
    """

    name = "preferred_courses_load"

    def apply(self, model, variables: dict, data: dict) -> None:
        x = variables["x"]
        preferred_relax = variables["preferred_relax"]
        assigned_slots = data["assigned_slots"]
        professors_list = data["professors_list"]
        course_list = data["course_list"]
        course_dict = data["course_dict"]
        load_dict = data["load_dict"]
        assigned_dict = data["assigned_dict"]
        preferred_courses = data["preferred_courses"]

        for i in professors_list:
            pre = sum(
                len(secs)
                for course, secs in assigned_dict.get(i, {}).items()
                if course in preferred_courses[i]
            )
            new_pref = lpSum(
                x.get((i, j, k), 0)
                for j in preferred_courses[i]
                for k in range(course_dict[j])
                if (i, j, k) not in assigned_slots
            )
            model += (
                pre + new_pref + preferred_relax[i] == load_dict[i],
                f"pref_load_{i}",
            )


class MultiSectionConstraint(Constraint):
    """
    For professors with multi_section_pref == -1: each (prof, course) pair is
    limited to at most 1 section across all sections of that course (plus relaxation).
    """

    name = "multi_section"

    def apply(self, model, variables: dict, data: dict) -> None:
        x = variables["x"]
        multi_section_relax = variables["multi_section_relax"]
        assigned_slots = data["assigned_slots"]
        professors_list = data["professors_list"]
        course_list = data["course_list"]
        course_dict = data["course_dict"]
        two_section_pref = data["two_section_pref"]

        for i in professors_list:
            if two_section_pref.get(i, 0) == -1:
                for j in course_list:
                    sections_sum = lpSum(
                        x.get((i, j, k), 0)
                        for k in range(course_dict[j])
                        if (i, j, k) not in assigned_slots
                    )
                    if (i, j) in multi_section_relax:
                        model += (
                            sections_sum + multi_section_relax[i, j] <= 1,
                            f"multi_section_{i}_{j}",
                        )
