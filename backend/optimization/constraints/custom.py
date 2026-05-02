# New constraints added for capstone go here.

from optimization.constraints.base import Constraint


class SameCoursePreferenceConstraint(Constraint):
    """
    For professors with multi_section_pref == 1 (want to concentrate on one course):

    y[i,j] ∈ {0,1} — 1 iff professor i teaches >= 1 section of course j.

    Linking (one-sided suffices because objective penalizes sum y):
        y[i,j] >= x[i,j,k]   for all new sections k
        y[i,j] >= 1           for pre-assigned courses

    The objective term (-SAME_COURSE_BONUS_WEIGHT * sum y) is added in phase1.py.
    """

    name = "same_course_preference"

    def apply(self, model, variables: dict, data: dict) -> None:
        x = variables["x"]
        y = variables["y_distinct_courses"]
        assigned_slots = data["assigned_slots"]
        assigned_dict = data["assigned_dict"]
        professors_list = data["professors_list"]
        course_list = data["course_list"]
        course_dict = data["course_dict"]
        two_section_pref = data["two_section_pref"]

        for i in professors_list:
            if two_section_pref.get(i, 0) != 1:
                continue
            for j in course_list:
                if (i, j) not in y:
                    continue
                for k in range(course_dict[j]):
                    if (i, j, k) not in assigned_slots:
                        var = x.get((i, j, k))
                        if var is not None:
                            model += (
                                y[i, j] >= var,
                                f"same_course_link_{i}_{j}_{k}",
                            )
                if i in assigned_dict and j in assigned_dict[i]:
                    model += (y[i, j] >= 1, f"same_course_preassign_{i}_{j}")
