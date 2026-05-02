"""
test_constraints.py — unit tests for each constraint class.

Each test builds its own minimal PuLP model, applies only the constraint(s)
under test, solves, and asserts the expected variable values.  The `repo`
fixture from conftest.py is NOT used here — isolation is the goal.
"""

import pytest
from pulp import (
    LpMaximize,
    LpMinimize,
    LpProblem,
    LpStatus,
    LpVariable,
    lpSum,
    value,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _solve(prob):
    import pulp

    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    return LpStatus[prob.status]


# ---------------------------------------------------------------------------
# OneSectionPerSlotConstraint
# ---------------------------------------------------------------------------


class TestOneSectionPerSlotConstraint:
    def test_at_most_one_prof_per_slot(self):
        """
        2 professors, 1 course, 1 section.
        Both could teach it, but constraint limits to <= 1.
        Maximising the sum should give exactly 1 assignment.
        """
        from optimization.constraints.workload import OneSectionPerSlotConstraint

        profs = ["P1", "P2"]
        courses = ["MATH301"]
        course_dict = {"MATH301": 1}

        x = LpVariable.dicts(
            "x",
            [(i, j, k) for i in profs for j in courses for k in range(course_dict[j])],
            cat="Binary",
        )
        prob = LpProblem("test", LpMaximize)
        prob += lpSum(x.values())

        constraint = OneSectionPerSlotConstraint()
        constraint.apply(
            prob,
            variables={"x": x},
            data={
                "assigned_slots": set(),
                "professors_list": profs,
                "course_list": courses,
                "course_dict": course_dict,
            },
        )

        status = _solve(prob)
        assert status == "Optimal"
        total = sum(value(v) for v in x.values())
        assert total == pytest.approx(1.0)

    def test_skips_preassigned_slots(self):
        """
        When a slot is pre-assigned it is excluded from the constraint;
        the constraint should still be added for remaining free slots.
        """
        from optimization.constraints.workload import OneSectionPerSlotConstraint

        profs = ["P1", "P2"]
        courses = ["MATH301"]
        course_dict = {"MATH301": 2}  # 2 sections
        # section 0 pre-assigned to P1
        assigned_slots = {("P1", "MATH301", 0)}

        x = LpVariable.dicts(
            "x",
            [
                (i, j, k)
                for i in profs
                for j in courses
                for k in range(course_dict[j])
                if (i, j, k) not in assigned_slots
            ],
            cat="Binary",
        )
        prob = LpProblem("test", LpMaximize)
        prob += lpSum(x.values())

        constraint = OneSectionPerSlotConstraint()
        constraint.apply(
            prob,
            variables={"x": x},
            data={
                "assigned_slots": assigned_slots,
                "professors_list": profs,
                "course_list": courses,
                "course_dict": course_dict,
            },
        )

        status = _solve(prob)
        assert status == "Optimal"
        # Free section 1 can be taught by at most 1 of {P1, P2}
        free_total = sum(
            value(x.get((i, "MATH301", 1), 0)) for i in profs
        )
        assert free_total <= 1.0 + 1e-6


# ---------------------------------------------------------------------------
# ProfessorLoadConstraint
# ---------------------------------------------------------------------------


class TestProfessorLoadConstraint:
    def test_prof_assigned_exactly_to_load(self):
        """
        1 professor with load=2, 3 available sections.
        The constraint forces total assigned sections + relax == 2.
        Maximizing assignments should result in exactly 2 assigned (relax=0).
        """
        from optimization.constraints.workload import ProfessorLoadConstraint

        profs = ["Smith"]
        courses = ["MATH301", "MATH302", "MATH401"]
        course_dict = {"MATH301": 1, "MATH302": 1, "MATH401": 1}
        load_dict = {"Smith": 2}
        w_by_course = {"MATH301": 1.0, "MATH302": 1.0, "MATH401": 1.0}

        x = LpVariable.dicts(
            "x",
            [(i, j, k) for i in profs for j in courses for k in range(course_dict[j])],
            cat="Binary",
        )
        prof_relax = LpVariable.dicts("prof_relax", profs, lowBound=0)

        prob = LpProblem("test", LpMaximize)
        prob += lpSum(x.values()) - 100 * lpSum(prof_relax.values())

        constraint = ProfessorLoadConstraint()
        constraint.apply(
            prob,
            variables={"x": x, "prof_relax": prof_relax},
            data={
                "assigned_slots": set(),
                "professors_list": profs,
                "course_list": courses,
                "course_dict": course_dict,
                "load_dict": load_dict,
                "w_by_course": w_by_course,
                "prof_preassigned_count": {"Smith": 0},
            },
        )

        status = _solve(prob)
        assert status == "Optimal"
        assigned_total = sum(value(v) for v in x.values())
        assert assigned_total == pytest.approx(2.0)
        assert value(prof_relax["Smith"]) == pytest.approx(0.0)

    def test_relax_fires_when_insufficient_sections(self):
        """
        1 professor with load=3 but only 2 available sections.
        relax must absorb the shortfall (relax=1).
        """
        from optimization.constraints.workload import ProfessorLoadConstraint

        profs = ["Jones"]
        courses = ["MATH301", "MATH302"]
        course_dict = {"MATH301": 1, "MATH302": 1}
        load_dict = {"Jones": 3}
        w_by_course = {"MATH301": 1.0, "MATH302": 1.0}

        x = LpVariable.dicts(
            "x",
            [(i, j, k) for i in profs for j in courses for k in range(course_dict[j])],
            cat="Binary",
        )
        prof_relax = LpVariable.dicts("prof_relax", profs, lowBound=0)

        prob = LpProblem("test", LpMinimize)
        prob += lpSum(prof_relax.values())

        constraint = ProfessorLoadConstraint()
        constraint.apply(
            prob,
            variables={"x": x, "prof_relax": prof_relax},
            data={
                "assigned_slots": set(),
                "professors_list": profs,
                "course_list": courses,
                "course_dict": course_dict,
                "load_dict": load_dict,
                "w_by_course": w_by_course,
                "prof_preassigned_count": {"Jones": 0},
            },
        )

        status = _solve(prob)
        assert status == "Optimal"
        assert value(prof_relax["Jones"]) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# CourseSectionFillConstraint
# ---------------------------------------------------------------------------


class TestCourseSectionFillConstraint:
    def test_all_sections_filled(self):
        """
        1 course with 2 sections, 2 professors.
        Constraint forces both sections to be filled.
        """
        from optimization.constraints.workload import CourseSectionFillConstraint

        profs = ["P1", "P2"]
        courses = ["MATH301"]
        course_dict = {"MATH301": 2}

        x = LpVariable.dicts(
            "x",
            [(i, j, k) for i in profs for j in courses for k in range(course_dict[j])],
            cat="Binary",
        )
        section_relax = LpVariable.dicts("section_relax", courses, lowBound=0)

        prob = LpProblem("test", LpMaximize)
        prob += lpSum(x.values()) - 1000 * lpSum(section_relax.values())

        constraint = CourseSectionFillConstraint()
        constraint.apply(
            prob,
            variables={"x": x, "section_relax": section_relax},
            data={
                "assigned_slots": set(),
                "professors_list": profs,
                "course_list": courses,
                "course_dict": course_dict,
                "course_preassigned_count": {"MATH301": 0},
            },
        )

        status = _solve(prob)
        assert status == "Optimal"
        # Both sections should be assigned (relax = 0)
        assert value(section_relax["MATH301"]) == pytest.approx(0.0)
        total = sum(value(v) for v in x.values())
        assert total == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# PreferredCoursesOnlyConstraint
# ---------------------------------------------------------------------------


class TestPreferredCoursesOnlyConstraint:
    def test_non_preferred_cannot_be_assigned(self):
        """
        Professor P1 only prefers MATH301; MATH302 must be assigned = 0.
        """
        from optimization.constraints.preferences import PreferredCoursesOnlyConstraint

        profs = ["P1"]
        courses = ["MATH301", "MATH302"]
        course_dict = {"MATH301": 1, "MATH302": 1}
        preferred_courses = {"P1": ["MATH301"]}

        x = LpVariable.dicts(
            "x",
            [(i, j, k) for i in profs for j in courses for k in range(course_dict[j])],
            cat="Binary",
        )

        prob = LpProblem("test", LpMaximize)
        # Try to maximise ALL assignments (including non-preferred)
        prob += lpSum(x.values())

        constraint = PreferredCoursesOnlyConstraint()
        constraint.apply(
            prob,
            variables={"x": x},
            data={
                "assigned_slots": set(),
                "professors_list": profs,
                "course_list": courses,
                "course_dict": course_dict,
                "preferred_courses": preferred_courses,
            },
        )

        status = _solve(prob)
        assert status == "Optimal"
        # Non-preferred course must be 0
        assert value(x["P1", "MATH302", 0]) == pytest.approx(0.0)
        # Preferred course can be 1
        assert value(x["P1", "MATH301", 0]) == pytest.approx(1.0)

    def test_prof_with_no_preferred_assigns_nothing(self):
        """If preferred_courses is empty for a prof, they get nothing."""
        from optimization.constraints.preferences import PreferredCoursesOnlyConstraint

        profs = ["P1"]
        courses = ["MATH301"]
        course_dict = {"MATH301": 1}
        preferred_courses = {"P1": []}

        x = LpVariable.dicts(
            "x",
            [(i, j, k) for i in profs for j in courses for k in range(course_dict[j])],
            cat="Binary",
        )

        prob = LpProblem("test", LpMaximize)
        prob += lpSum(x.values())

        constraint = PreferredCoursesOnlyConstraint()
        constraint.apply(
            prob,
            variables={"x": x},
            data={
                "assigned_slots": set(),
                "professors_list": profs,
                "course_list": courses,
                "course_dict": course_dict,
                "preferred_courses": preferred_courses,
            },
        )

        status = _solve(prob)
        assert status == "Optimal"
        assert value(x["P1", "MATH301", 0]) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# MultiSectionConstraint
# ---------------------------------------------------------------------------


class TestMultiSectionConstraint:
    def test_multi_section_limits_to_one_section_per_course(self):
        """
        Professor with multi_section_pref=-1 should be limited to at most
        1 section per course (without slack firing, penalty is very high).
        """
        from optimization.constraints.preferences import MultiSectionConstraint

        profs = ["Brown"]
        courses = ["MATH301"]
        course_dict = {"MATH301": 2}  # 2 sections available
        two_section_pref = {"Brown": -1}

        x = LpVariable.dicts(
            "x",
            [(i, j, k) for i in profs for j in courses for k in range(course_dict[j])],
            cat="Binary",
        )
        multi_section_relax = LpVariable.dicts(
            "multi_section_relax",
            [(i, j) for i in profs for j in courses if two_section_pref.get(i, 0) == -1],
            lowBound=0,
        )

        prob = LpProblem("test", LpMaximize)
        # High penalty on relax to prevent it firing
        prob += lpSum(x.values()) - 1000 * lpSum(multi_section_relax.values())

        constraint = MultiSectionConstraint()
        constraint.apply(
            prob,
            variables={"x": x, "multi_section_relax": multi_section_relax},
            data={
                "assigned_slots": set(),
                "professors_list": profs,
                "course_list": courses,
                "course_dict": course_dict,
                "two_section_pref": two_section_pref,
            },
        )

        status = _solve(prob)
        assert status == "Optimal"
        # At most 1 section of MATH301 may be assigned
        total_math301 = sum(
            value(x["Brown", "MATH301", k]) for k in range(course_dict["MATH301"])
        )
        assert total_math301 <= 1.0 + 1e-6

    def test_neutral_prof_not_restricted(self):
        """
        Professor with multi_section_pref=0 is not restricted by this constraint;
        they can be assigned both sections.
        """
        from optimization.constraints.preferences import MultiSectionConstraint

        profs = ["Smith"]
        courses = ["MATH301"]
        course_dict = {"MATH301": 2}
        two_section_pref = {"Smith": 0}

        x = LpVariable.dicts(
            "x",
            [(i, j, k) for i in profs for j in courses for k in range(course_dict[j])],
            cat="Binary",
        )
        multi_section_relax = LpVariable.dicts(
            "multi_section_relax",
            [(i, j) for i in profs for j in courses if two_section_pref.get(i, 0) == -1],
            lowBound=0,
        )

        prob = LpProblem("test", LpMaximize)
        prob += lpSum(x.values())

        constraint = MultiSectionConstraint()
        constraint.apply(
            prob,
            variables={"x": x, "multi_section_relax": multi_section_relax},
            data={
                "assigned_slots": set(),
                "professors_list": profs,
                "course_list": courses,
                "course_dict": course_dict,
                "two_section_pref": two_section_pref,
            },
        )

        status = _solve(prob)
        assert status == "Optimal"
        total = sum(
            value(x["Smith", "MATH301", k]) for k in range(course_dict["MATH301"])
        )
        assert total == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# RoomCapacityConstraint
# ---------------------------------------------------------------------------


class TestRoomCapacityConstraint:
    def _make_prof_courses_df(self, courses_data):
        """Helper: build a minimal prof_courses_df DataFrame."""
        import pandas as pd

        rows = []
        for idx, (course, cap, prof) in enumerate(courses_data):
            rows.append({"professor": prof, "course": course, "section": 1, "capacity": cap})
        df = pd.DataFrame(rows)
        df.index.name = "index"
        return df

    def _make_rts(self, entries):
        """Helper: build RoomTimeSlot objects."""
        from models.entities import RoomTimeSlot

        result = []
        for idx, (timeslot, room, cap) in enumerate(entries):
            result.append(
                RoomTimeSlot(index=idx, timeslot=timeslot, room=room, room_capacity=cap)
            )
        return result

    def test_large_course_blocked_in_small_room_when_big_m_zero(self):
        """
        Course capacity=40, room capacity=20, BIG_M=0.
        With slack=0 forced (minimise slack with very high cost),
        the solver cannot schedule the course in that room.
        """
        from optimization.constraints.scheduling import RoomCapacityConstraint

        prof_courses_df = self._make_prof_courses_df([("MATH301", 40, "Smith")])
        room_timeslots = self._make_rts([("MWF 09:00 AM-09:50 AM", "SmallRoom", 20)])

        courses = prof_courses_df.index.tolist()
        timeslots = [rt.index for rt in room_timeslots]

        x = LpVariable.dicts("x", [(c, t) for c in courses for t in timeslots], cat="Binary")
        slack = LpVariable.dicts("slack", courses, lowBound=0, cat="Binary")

        prob = LpProblem("test", LpMaximize)
        # Force slack = 0 by not penalising x but heavily penalising slack
        prob += lpSum(x.values()) - 10000 * lpSum(slack.values())

        constraint = RoomCapacityConstraint()
        constraint.apply(
            prob,
            variables={"x": x, "slack": slack},
            data={
                "prof_courses_df": prof_courses_df,
                "room_timeslots": room_timeslots,
                "BIG_M": 0,
            },
        )

        _solve(prob)
        # With BIG_M=0 and cap=40 > room=20, x[0,0] must be 0
        assert value(x[0, 0]) == pytest.approx(0.0, abs=1e-4)

    def test_small_course_fits_in_room(self):
        """
        Course capacity=15, room capacity=35.  BIG_M=10000.
        Course should be schedulable (x = 1).
        """
        from optimization.constraints.scheduling import RoomCapacityConstraint

        prof_courses_df = self._make_prof_courses_df([("MATH402", 15, "Jones")])
        room_timeslots = self._make_rts([("TR 09:00 AM-10:15 AM", "RoomA", 35)])

        courses = prof_courses_df.index.tolist()
        timeslots = [rt.index for rt in room_timeslots]

        x = LpVariable.dicts("x", [(c, t) for c in courses for t in timeslots], cat="Binary")
        slack = LpVariable.dicts("slack", courses, lowBound=0, cat="Binary")

        prob = LpProblem("test", LpMaximize)
        prob += lpSum(x.values()) - 1000 * lpSum(slack.values())

        constraint = RoomCapacityConstraint()
        constraint.apply(
            prob,
            variables={"x": x, "slack": slack},
            data={
                "prof_courses_df": prof_courses_df,
                "room_timeslots": room_timeslots,
                "BIG_M": 10000,
            },
        )

        status = _solve(prob)
        assert status == "Optimal"
        assert value(x[0, 0]) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# NoRoomDoubleBookingConstraint
# ---------------------------------------------------------------------------


class TestNoRoomDoubleBookingConstraint:
    def _make_rts(self, entries):
        from models.entities import RoomTimeSlot

        return [
            RoomTimeSlot(index=i, timeslot=ts, room=room, room_capacity=cap)
            for i, (ts, room, cap) in enumerate(entries)
        ]

    def test_two_courses_cannot_share_room_timeslot(self):
        """
        2 courses, 1 room, 1 timeslot → at most 1 can be scheduled there.
        """
        import pandas as pd

        from optimization.constraints.scheduling import NoRoomDoubleBookingConstraint

        rows = [
            {"professor": "Smith", "course": "MATH301", "section": 1, "capacity": 30},
            {"professor": "Jones", "course": "MATH302", "section": 1, "capacity": 25},
        ]
        prof_courses_df = pd.DataFrame(rows)

        room_timeslots = self._make_rts(
            [("MWF 09:00 AM-09:50 AM", "RoomA", 35)]
        )

        courses = prof_courses_df.index.tolist()
        timeslots = [rt.index for rt in room_timeslots]

        x = LpVariable.dicts("x", [(c, t) for c in courses for t in timeslots], cat="Binary")

        prob = LpProblem("test", LpMaximize)
        prob += lpSum(x.values())

        constraint = NoRoomDoubleBookingConstraint()
        constraint.apply(
            prob,
            variables={"x": x},
            data={
                "prof_courses_df": prof_courses_df,
                "room_timeslots": room_timeslots,
            },
        )

        status = _solve(prob)
        assert status == "Optimal"
        total = sum(value(x[c, 0]) for c in courses)
        assert total <= 1.0 + 1e-6

    def test_different_rooms_same_timeslot_allowed(self):
        """
        2 courses, 2 different rooms, same timeslot → both can be scheduled.
        """
        import pandas as pd

        from optimization.constraints.scheduling import NoRoomDoubleBookingConstraint

        rows = [
            {"professor": "Smith", "course": "MATH301", "section": 1, "capacity": 30},
            {"professor": "Jones", "course": "MATH302", "section": 1, "capacity": 25},
        ]
        prof_courses_df = pd.DataFrame(rows)

        # Two different rooms at the same timeslot label
        room_timeslots = self._make_rts(
            [
                ("MWF 09:00 AM-09:50 AM", "RoomA", 35),
                ("MWF 09:00 AM-09:50 AM", "RoomB", 35),
            ]
        )

        courses = prof_courses_df.index.tolist()
        timeslots = [rt.index for rt in room_timeslots]

        x = LpVariable.dicts("x", [(c, t) for c in courses for t in timeslots], cat="Binary")
        # Each course scheduled exactly once
        prob = LpProblem("test", LpMaximize)
        prob += lpSum(x.values())
        for c in courses:
            prob += lpSum(x[c, t] for t in timeslots) == 1

        constraint = NoRoomDoubleBookingConstraint()
        constraint.apply(
            prob,
            variables={"x": x},
            data={
                "prof_courses_df": prof_courses_df,
                "room_timeslots": room_timeslots,
            },
        )

        status = _solve(prob)
        assert status == "Optimal"
        # Both courses should be scheduled (different rooms)
        total = sum(value(x[c, t]) for c in courses for t in timeslots)
        assert total == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# NoProfDoubleBookingConstraint
# ---------------------------------------------------------------------------


class TestNoProfDoubleBookingConstraint:
    def _make_rts(self, entries):
        from models.entities import RoomTimeSlot

        return [
            RoomTimeSlot(index=i, timeslot=ts, room=room, room_capacity=cap)
            for i, (ts, room, cap) in enumerate(entries)
        ]

    def test_prof_cannot_teach_two_courses_at_same_timeslot(self):
        """
        1 professor, 2 courses, 1 timeslot (2 rooms available).
        Professor can only be in one room at a time → at most 1 assignment
        at any given timeslot.
        """
        import pandas as pd
        from collections import defaultdict

        from optimization.constraints.scheduling import NoProfDoubleBookingConstraint

        rows = [
            {"professor": "Smith", "course": "MATH301", "section": 1, "capacity": 30},
            {"professor": "Smith", "course": "MATH401", "section": 1, "capacity": 20},
        ]
        prof_courses_df = pd.DataFrame(rows)

        # Same timeslot, two rooms
        room_timeslots = self._make_rts(
            [
                ("MWF 09:00 AM-09:50 AM", "RoomA", 35),
                ("MWF 09:00 AM-09:50 AM", "RoomB", 35),
            ]
        )

        time_groups = defaultdict(list)
        for rt in room_timeslots:
            time_groups[rt.timeslot].append(rt.index)

        courses = prof_courses_df.index.tolist()
        timeslots = [rt.index for rt in room_timeslots]

        x = LpVariable.dicts("x", [(c, t) for c in courses for t in timeslots], cat="Binary")
        prob = LpProblem("test", LpMaximize)
        prob += lpSum(x.values())

        constraint = NoProfDoubleBookingConstraint()
        constraint.apply(
            prob,
            variables={"x": x},
            data={
                "prof_courses_df": prof_courses_df,
                "room_timeslots": room_timeslots,
                "time_groups": dict(time_groups),
            },
        )

        status = _solve(prob)
        assert status == "Optimal"

        ts_label = "MWF 09:00 AM-09:50 AM"
        t_indices = time_groups[ts_label]
        total_at_ts = sum(value(x[c, t]) for c in courses for t in t_indices)
        assert total_at_ts <= 1.0 + 1e-6

    def test_different_profs_same_timeslot_allowed(self):
        """
        2 different professors, 1 timeslot, 2 rooms → both can teach simultaneously.
        """
        import pandas as pd
        from collections import defaultdict

        from optimization.constraints.scheduling import NoProfDoubleBookingConstraint

        rows = [
            {"professor": "Smith", "course": "MATH301", "section": 1, "capacity": 30},
            {"professor": "Jones", "course": "MATH302", "section": 1, "capacity": 25},
        ]
        prof_courses_df = pd.DataFrame(rows)

        room_timeslots = self._make_rts(
            [
                ("MWF 09:00 AM-09:50 AM", "RoomA", 35),
                ("MWF 09:00 AM-09:50 AM", "RoomB", 35),
            ]
        )

        time_groups = defaultdict(list)
        for rt in room_timeslots:
            time_groups[rt.timeslot].append(rt.index)

        courses = prof_courses_df.index.tolist()
        timeslots = [rt.index for rt in room_timeslots]

        x = LpVariable.dicts("x", [(c, t) for c in courses for t in timeslots], cat="Binary")
        prob = LpProblem("test", LpMaximize)
        prob += lpSum(x.values())
        for c in courses:
            prob += lpSum(x[c, t] for t in timeslots) == 1

        constraint = NoProfDoubleBookingConstraint()
        constraint.apply(
            prob,
            variables={"x": x},
            data={
                "prof_courses_df": prof_courses_df,
                "room_timeslots": room_timeslots,
                "time_groups": dict(time_groups),
            },
        )

        status = _solve(prob)
        assert status == "Optimal"
        total = sum(value(x[c, t]) for c in courses for t in timeslots)
        assert total == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# SameCoursePreferenceConstraint
# ---------------------------------------------------------------------------


class TestSameCoursePreferenceConstraint:
    """
    Professor with pref==1 should be nudged toward teaching multiple sections
    of the same course rather than one section of each of several courses.
    """

    def test_y_forced_to_one_when_section_assigned(self):
        """
        y[i,j] >= x[i,j,k]: if x=1 then y must be 1.
        """
        from optimization.constraints.custom import SameCoursePreferenceConstraint

        profs = ["Smith"]
        courses = ["MATH301"]
        course_dict = {"MATH301": 1}
        two_section_pref = {"Smith": 1}

        x = LpVariable.dicts(
            "x",
            [("Smith", "MATH301", 0)],
            cat="Binary",
        )
        y = LpVariable.dicts(
            "y_distinct",
            [("Smith", "MATH301")],
            cat="Binary",
        )

        prob = LpProblem("test", LpMaximize)
        prob += x["Smith", "MATH301", 0]
        prob += x["Smith", "MATH301", 0] == 1  # force assignment

        constraint = SameCoursePreferenceConstraint()
        constraint.apply(
            prob,
            variables={"x": x, "y_distinct_courses": y},
            data={
                "assigned_slots": set(),
                "assigned_dict": {},
                "professors_list": profs,
                "course_list": courses,
                "course_dict": course_dict,
                "two_section_pref": two_section_pref,
            },
        )

        _solve(prob)
        assert value(y["Smith", "MATH301"]) == pytest.approx(1.0)

    def test_y_zero_when_no_section_assigned(self):
        """
        When x=0 (no section assigned), objective drives y to 0.
        """
        from optimization.constraints.custom import SameCoursePreferenceConstraint

        profs = ["Smith"]
        courses = ["MATH301"]
        course_dict = {"MATH301": 1}
        two_section_pref = {"Smith": 1}

        x = LpVariable.dicts(
            "x",
            [("Smith", "MATH301", 0)],
            cat="Binary",
        )
        y = LpVariable.dicts(
            "y_distinct",
            [("Smith", "MATH301")],
            cat="Binary",
        )

        prob = LpProblem("test", LpMaximize)
        # Penalize y — solver will set y=0 unless forced
        prob += -10 * y["Smith", "MATH301"]
        prob += x["Smith", "MATH301", 0] == 0  # no assignment

        constraint = SameCoursePreferenceConstraint()
        constraint.apply(
            prob,
            variables={"x": x, "y_distinct_courses": y},
            data={
                "assigned_slots": set(),
                "assigned_dict": {},
                "professors_list": profs,
                "course_list": courses,
                "course_dict": course_dict,
                "two_section_pref": two_section_pref,
            },
        )

        _solve(prob)
        assert value(y["Smith", "MATH301"]) == pytest.approx(0.0)

    def test_same_course_preferred_over_distinct(self):
        """
        Prof with pref==1, load=2, two courses each with 2 sections.
        Objective penalizes distinct-course count heavily.
        Solver should assign both sections to one course (y sum = 1, not 2).
        """
        from optimization.constraints.custom import SameCoursePreferenceConstraint

        profs = ["Smith"]
        courses = ["MATH301", "MATH302"]
        course_dict = {"MATH301": 2, "MATH302": 2}
        two_section_pref = {"Smith": 1}
        W = 10.0  # large weight to guarantee same-course choice

        x = LpVariable.dicts(
            "x",
            [(i, j, k) for i in profs for j in courses for k in range(course_dict[j])],
            cat="Binary",
        )
        y = LpVariable.dicts(
            "y_distinct",
            [(i, j) for i in profs for j in courses],
            cat="Binary",
        )

        prob = LpProblem("test", LpMaximize)
        # Maximize assignments, heavily penalize distinct courses
        prob += lpSum(x.values()) - W * lpSum(y.values())

        # Load = 2
        prob += lpSum(x.values()) == 2

        # One professor per section
        for j in courses:
            for k in range(course_dict[j]):
                prob += lpSum(x[i, j, k] for i in profs) <= 1

        constraint = SameCoursePreferenceConstraint()
        constraint.apply(
            prob,
            variables={"x": x, "y_distinct_courses": y},
            data={
                "assigned_slots": set(),
                "assigned_dict": {},
                "professors_list": profs,
                "course_list": courses,
                "course_dict": course_dict,
                "two_section_pref": two_section_pref,
            },
        )

        status = _solve(prob)
        assert status == "Optimal"
        # Should teach both sections of one course: distinct count = 1
        y_sum = sum(value(y[i, j]) for i in profs for j in courses)
        assert y_sum == pytest.approx(1.0)

    def test_neutral_prof_not_constrained(self):
        """
        Prof with pref==0 is unaffected — no y variables created for them.
        """
        from optimization.constraints.custom import SameCoursePreferenceConstraint

        profs = ["Jones"]
        courses = ["MATH301", "MATH302"]
        course_dict = {"MATH301": 1, "MATH302": 1}
        two_section_pref = {"Jones": 0}

        x = LpVariable.dicts(
            "x",
            [(i, j, k) for i in profs for j in courses for k in range(course_dict[j])],
            cat="Binary",
        )
        # No y vars for neutral prof
        y = {}

        prob = LpProblem("test", LpMaximize)
        prob += lpSum(x.values())

        constraint = SameCoursePreferenceConstraint()
        # Should add zero constraints and not crash
        constraint.apply(
            prob,
            variables={"x": x, "y_distinct_courses": y},
            data={
                "assigned_slots": set(),
                "assigned_dict": {},
                "professors_list": profs,
                "course_list": courses,
                "course_dict": course_dict,
                "two_section_pref": two_section_pref,
            },
        )

        status = _solve(prob)
        assert status == "Optimal"

    def test_preassigned_course_forces_y_one(self):
        """
        When a professor is pre-assigned to a course, y[i,j] must be 1
        even if no new x variable is created for that course.
        """
        from optimization.constraints.custom import SameCoursePreferenceConstraint

        profs = ["Smith"]
        courses = ["MATH301"]
        course_dict = {"MATH301": 1}
        two_section_pref = {"Smith": 1}
        assigned_dict = {"Smith": {"MATH301": [0]}}
        assigned_slots = {("Smith", "MATH301", 0)}

        x = {}  # no new x vars — section already pre-assigned
        y = LpVariable.dicts(
            "y_distinct",
            [("Smith", "MATH301")],
            cat="Binary",
        )

        prob = LpProblem("test", LpMaximize)
        prob += -10 * y["Smith", "MATH301"]  # penalize y — constraint must override

        constraint = SameCoursePreferenceConstraint()
        constraint.apply(
            prob,
            variables={"x": x, "y_distinct_courses": y},
            data={
                "assigned_slots": assigned_slots,
                "assigned_dict": assigned_dict,
                "professors_list": profs,
                "course_list": courses,
                "course_dict": course_dict,
                "two_section_pref": two_section_pref,
            },
        )

        _solve(prob)
        assert value(y["Smith", "MATH301"]) == pytest.approx(1.0)
