"""
Workload-related constraints for Phase 1.

Classes
-------
OneSectionPerSlotConstraint
    Each (course, section) slot may be taught by at most one professor.
ProfessorLoadConstraint
    Professor total section weight == load (with relaxation).
CourseSectionFillConstraint
    Each course must have all its sections assigned (with relaxation).
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from pulp import lpSum

from optimization.constraints.base import Constraint

if TYPE_CHECKING:
    pass


class OneSectionPerSlotConstraint(Constraint):
    """Each (course, section) slot is taught by at most 1 professor (skip pre-assigned)."""

    name = "one_section_per_slot"

    def apply(self, model, variables: dict, data: dict) -> None:
        x = variables["x"]
        assigned_slots = data["assigned_slots"]
        professors_list = data["professors_list"]
        course_list = data["course_list"]
        course_dict = data["course_dict"]

        for j in course_list:
            for k in range(course_dict[j]):
                if not any(
                    (prof, j, k) in assigned_slots for prof in professors_list
                ):
                    model += (
                        lpSum(
                            x.get((i, j, k), 0)
                            for i in professors_list
                            if (i, j, k) not in assigned_slots
                        )
                        <= 1,
                        f"one_section_{j}_{k}",
                    )


class ProfessorLoadConstraint(Constraint):
    """
    Professor total weighted section assignments + prof_relax == load.
    Uses w_by_course weights (L=1.0, R=0.5) so recitation sections count less.
    """

    name = "professor_load"

    def apply(self, model, variables: dict, data: dict) -> None:
        x = variables["x"]
        prof_relax = variables["prof_relax"]
        assigned_slots = data["assigned_slots"]
        professors_list = data["professors_list"]
        course_list = data["course_list"]
        course_dict = data["course_dict"]
        load_dict = data["load_dict"]
        w_by_course = data["w_by_course"]
        prof_preassigned_count = data["prof_preassigned_count"]

        for i in professors_list:
            pre = prof_preassigned_count[i]
            new_load = lpSum(
                w_by_course[j] * x[i, j, k]
                for j in course_list
                for k in range(course_dict[j])
                if (i, j, k) not in assigned_slots and (i, j, k) in x
            )
            model += (
                pre + new_load + prof_relax[i] == load_dict[i],
                f"prof_load_{i}",
            )


class CourseSectionFillConstraint(Constraint):
    """Each course must have all its sections assigned (with section_relax slack)."""

    name = "course_section_fill"

    def apply(self, model, variables: dict, data: dict) -> None:
        x = variables["x"]
        section_relax = variables["section_relax"]
        assigned_slots = data["assigned_slots"]
        professors_list = data["professors_list"]
        course_list = data["course_list"]
        course_dict = data["course_dict"]
        course_preassigned_count = data["course_preassigned_count"]

        for j in course_list:
            pre = course_preassigned_count[j]
            new_sections = lpSum(
                x.get((i, j, k), 0)
                for i in professors_list
                for k in range(course_dict[j])
                if (i, j, k) not in assigned_slots
            )
            model += (
                pre + new_sections + section_relax[j] == course_dict[j],
                f"course_fill_{j}",
            )
