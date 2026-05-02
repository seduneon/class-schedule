"""
test_phase1.py — integration tests for solve_phase1.

Uses the session-scoped `phase1_result` fixture (depends on `repo`).
The fixture data is a balanced 3-professor / 4-course / 6-section problem
that should solve to Optimal with every section filled and every professor
at load.
"""

import pytest


class TestPhase1Solves:
    def test_status_optimal(self, phase1_result):
        assert phase1_result.status == "Optimal"

    def test_objective_value_is_positive(self, phase1_result):
        assert phase1_result.objective_value is not None
        assert phase1_result.objective_value > 0


class TestPhase1LoadsSatisfied:
    def test_no_unassigned_professors(self, phase1_result):
        """With balanced fixture data all professors should be fully assigned."""
        assert phase1_result.unassigned_professors == []

    def test_all_prof_loads_met(self, phase1_result, repo):
        """Every professor's assigned section count should equal their load."""
        for prof_name, sections_assigned in phase1_result.professor_loads.items():
            expected_load = repo.load_dict[prof_name]
            assert sections_assigned == expected_load, (
                f"{prof_name}: expected load={expected_load}, "
                f"got sections_assigned={sections_assigned}"
            )

    def test_total_sections_assigned_equals_total_sections(self, phase1_result, repo):
        total_assigned = sum(phase1_result.professor_loads.values())
        total_sections = sum(repo.course_dict.values())
        assert total_assigned == total_sections


class TestPhase1AllSectionsFilled:
    def test_no_unfilled_courses(self, phase1_result):
        """With balanced fixture data all sections should be filled."""
        assert phase1_result.unfilled_courses == []

    def test_assignments_cover_all_sections(self, phase1_result, repo):
        """
        Build a dict of course → {sections assigned} from phase1 assignments.
        Every course must have all section indices present.
        """
        from collections import defaultdict

        assigned_sections: dict = defaultdict(set)
        for a in phase1_result.assignments:
            for sec in a.sections:
                assigned_sections[a.course].add(sec)

        for course, total_secs in repo.course_dict.items():
            expected_indices = set(range(total_secs))
            assert assigned_sections[course] == expected_indices, (
                f"Course {course}: expected sections {expected_indices}, "
                f"got {assigned_sections[course]}"
            )


class TestPhase1NoPreferredViolations:
    def test_no_assignment_to_non_preferred_course(self, phase1_result, repo):
        """
        No professor should be assigned a course outside their preference list
        (unless prof_relax fired — check unassigned_professors is empty first).
        """
        # Only meaningful if no relaxation fired
        if phase1_result.unassigned_professors:
            pytest.skip("Relaxation fired; preferred-only check not applicable")

        for assignment in phase1_result.assignments:
            if assignment.status == "Pre-assigned":
                continue
            prof = assignment.professor
            course = assignment.course
            preferred = repo.preferred_courses.get(prof, [])
            assert course in preferred, (
                f"{prof} assigned to non-preferred course {course}"
            )


class TestPhase1AssignmentStructure:
    def test_every_assignment_has_nonempty_sections(self, phase1_result):
        for a in phase1_result.assignments:
            assert len(a.sections) > 0, f"Assignment for {a.professor}/{a.course} has no sections"

    def test_assignment_status_values(self, phase1_result):
        valid_statuses = {"Pre-assigned", "New"}
        for a in phase1_result.assignments:
            assert a.status in valid_statuses

    def test_all_profs_appear_in_assignments(self, phase1_result, repo):
        assigned_profs = {a.professor for a in phase1_result.assignments}
        for prof_name in repo.load_dict:
            assert prof_name in assigned_profs, f"{prof_name} has no assignments"

    def test_no_duplicate_section_assignments(self, phase1_result, repo):
        """
        Each (course, section_index) pair should appear in at most one assignment.
        """
        seen: set = set()
        for a in phase1_result.assignments:
            for sec in a.sections:
                key = (a.course, sec)
                assert key not in seen, f"Duplicate assignment: {key}"
                seen.add(key)


class TestPhase1BrownMultiSection:
    def test_brown_assigned_at_most_one_section_per_course(self, phase1_result):
        """
        Brown has multi_section_pref=-1.  Without relaxation, she should be
        assigned at most 1 section per course.
        """
        if "Brown" in (phase1_result.unassigned_professors or []):
            pytest.skip("Brown's load relaxation fired; multi-section check not applicable")

        for a in phase1_result.assignments:
            if a.professor == "Brown" and a.status == "New":
                assert len(a.sections) <= 1, (
                    f"Brown assigned {len(a.sections)} sections of {a.course}"
                )
