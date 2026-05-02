"""
test_phase2.py — integration tests for solve_phase2.

Uses the session-scoped `phase2_result` fixture (depends on `phase1_result` and `repo`).
The fixture provides 10 room-timeslots for 6 course sections, so everything
should schedule without conflicts.
"""

import pytest
from collections import defaultdict


class TestPhase2Solves:
    def test_status_optimal(self, phase2_result):
        assert phase2_result.status == "Optimal"

    def test_result_has_assignments(self, phase2_result):
        assert len(phase2_result.assignments) > 0


class TestPhase2AllScheduled:
    def test_unscheduled_empty(self, phase2_result):
        """With 10 room-timeslots for 6 sections, nothing should be unscheduled."""
        assert phase2_result.unscheduled == []

    def test_assignment_count_matches_total_sections(self, phase2_result, repo):
        """Number of scheduled assignments should equal total section count (6)."""
        total_sections = sum(repo.course_dict.values())
        assert len(phase2_result.assignments) == total_sections


class TestPhase2NoRoomConflicts:
    def test_no_two_courses_in_same_room_at_same_time(self, phase2_result):
        """
        Each (room, timeslot) pair should appear at most once across all assignments.
        """
        seen: set = set()
        for a in phase2_result.assignments:
            key = (a.room, a.timeslot)
            assert key not in seen, (
                f"Room double-booking detected: room={a.room}, timeslot={a.timeslot}"
            )
            seen.add(key)


class TestPhase2NoProfConflicts:
    def test_no_prof_teaches_two_courses_at_same_time(self, phase2_result):
        """
        Each (professor, timeslot) pair should appear at most once.
        """
        seen: set = set()
        for a in phase2_result.assignments:
            key = (a.professor, a.timeslot)
            assert key not in seen, (
                f"Professor double-booking: prof={a.professor}, timeslot={a.timeslot}"
            )
            seen.add(key)


class TestPhase2AssignmentStructure:
    def test_all_assignments_have_nonempty_fields(self, phase2_result):
        for a in phase2_result.assignments:
            assert a.course, "assignment.course is empty"
            assert a.professor, "assignment.professor is empty"
            assert a.timeslot, "assignment.timeslot is empty"
            assert a.room, "assignment.room is empty"
            assert a.section >= 1, f"section {a.section} is invalid"

    def test_room_capacity_not_smaller_than_course_capacity(self, phase2_result):
        """
        Assignments should respect room capacity (room_capacity >= course_capacity)
        unless the Big-M slack was used.  With fixture rooms (cap=35) and max course
        cap=30, no violation is expected.
        """
        for a in phase2_result.assignments:
            assert a.room_capacity >= a.course_capacity, (
                f"{a.course}-{a.section}: room_cap={a.room_capacity} < "
                f"course_cap={a.course_capacity}"
            )

    def test_timeslots_are_in_time_list(self, phase2_result):
        """Every scheduled timeslot must be one of the canonical TIME_LIST entries."""
        import sys
        import os

        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
        from config import TIME_LIST

        for a in phase2_result.assignments:
            assert a.timeslot in TIME_LIST, (
                f"Unknown timeslot: {a.timeslot}"
            )


class TestPhase2RoomAssignmentValidity:
    def test_all_rooms_from_fixture(self, phase2_result, repo):
        """Assigned rooms must be ones that exist in the fixture room-timeslots."""
        valid_rooms = {rt.room for rt in repo.room_timeslots}
        for a in phase2_result.assignments:
            assert a.room in valid_rooms, f"Unknown room: {a.room}"

    def test_all_timeslots_from_fixture(self, phase2_result, repo):
        valid_ts = {rt.timeslot for rt in repo.room_timeslots}
        for a in phase2_result.assignments:
            assert a.timeslot in valid_ts, f"Unknown timeslot: {a.timeslot}"


class TestPhase2MWFTRPreference:
    def test_smith_assigned_mwf_slot(self, phase2_result):
        """
        Smith has MWForTR=1 (prefers MWF).  With sufficient MWF slots available,
        all her assignments should be in MWF timeslots.
        """
        for a in phase2_result.assignments:
            if a.professor == "Smith":
                assert a.timeslot.startswith("MWF"), (
                    f"Smith assigned to non-MWF slot: {a.timeslot}"
                )

    def test_jones_assigned_tr_slot(self, phase2_result):
        """
        Jones has MWForTR=0 (prefers TR).  All assignments should be TR slots.
        """
        for a in phase2_result.assignments:
            if a.professor == "Jones":
                assert a.timeslot.startswith("TR"), (
                    f"Jones assigned to non-TR slot: {a.timeslot}"
                )

    def test_brown_assigned_mwf_slot(self, phase2_result):
        """
        Brown has MWForTR=1 (prefers MWF).
        """
        for a in phase2_result.assignments:
            if a.professor == "Brown":
                assert a.timeslot.startswith("MWF"), (
                    f"Brown assigned to non-MWF slot: {a.timeslot}"
                )
