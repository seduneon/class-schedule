"""
test_loaders.py — tests for SchedulingDataRepository.

All tests use the session-scoped `repo` fixture from conftest.py which is
backed by the synthetic 3-professor / 4-course fixture files.
"""

import pytest


class TestLoadProfessors:
    def test_count(self, repo):
        """Three professors should be loaded."""
        assert len(repo.professors) == 3

    def test_last_names_present(self, repo):
        last_names = {p.last_name for p in repo.professors}
        assert last_names == {"Smith", "Jones", "Brown"}

    def test_loads_are_positive(self, repo):
        for p in repo.professors:
            assert p.load > 0, f"{p.last_name} has non-positive load"

    def test_mwf_flag_values(self, repo):
        """MWForTR must be 0 or 1 for every professor."""
        for p in repo.professors:
            assert p.mwf_or_tr in (0, 1), f"{p.last_name} mwf_or_tr={p.mwf_or_tr}"

    def test_smith_is_mwf(self, repo):
        smith = next(p for p in repo.professors if p.last_name == "Smith")
        assert smith.mwf_or_tr == 1

    def test_jones_is_tr(self, repo):
        jones = next(p for p in repo.professors if p.last_name == "Jones")
        assert jones.mwf_or_tr == 0

    def test_brown_is_mwf(self, repo):
        brown = next(p for p in repo.professors if p.last_name == "Brown")
        assert brown.mwf_or_tr == 1


class TestLoadCourseDict:
    def test_four_courses(self, repo):
        assert len(repo.course_dict) == 4

    def test_math301_two_sections(self, repo):
        assert repo.course_dict["MATH301"] == 2

    def test_math302_one_section(self, repo):
        assert repo.course_dict["MATH302"] == 1

    def test_math401_two_sections(self, repo):
        assert repo.course_dict["MATH401"] == 2

    def test_math402_one_section(self, repo):
        assert repo.course_dict["MATH402"] == 1


class TestLoadDict:
    def test_three_professors_in_load_dict(self, repo):
        assert len(repo.load_dict) == 3

    def test_total_load_equals_total_sections(self, repo):
        """Sum of all professor loads must equal total sections (6)."""
        total_load = sum(repo.load_dict.values())
        total_sections = sum(repo.course_dict.values())
        assert total_load == total_sections

    def test_each_prof_load_is_two(self, repo):
        for prof, load in repo.load_dict.items():
            assert load == 2, f"{prof} expected load=2, got {load}"


class TestWByCourse:
    def test_all_lecture_weight_one(self, repo):
        """All fixture courses are type L → weight 1.0."""
        for course, weight in repo.w_by_course.items():
            assert weight == 1.0, f"{course} weight={weight}, expected 1.0"

    def test_four_entries(self, repo):
        assert len(repo.w_by_course) == 4


class TestAssignedDict:
    def test_empty_no_preassignments(self, repo):
        """Fixture has no pre-assignments."""
        assert repo.assigned_dict == {}


class TestCoursePreferences:
    def test_shape(self, repo):
        """DataFrame must be 3 professors × 4 courses."""
        cp = repo.course_preferences
        assert cp.shape == (3, 4)

    def test_index_is_last_names(self, repo):
        cp = repo.course_preferences
        assert set(cp.index.tolist()) == {"Smith", "Jones", "Brown"}

    def test_columns_are_course_codes(self, repo):
        cp = repo.course_preferences
        assert set(cp.columns.tolist()) == {"MATH301", "MATH302", "MATH401", "MATH402"}

    def test_values_are_normalized_non_negative(self, repo):
        cp = repo.course_preferences
        assert (cp.values >= 0).all()

    def test_smith_ranks_math301_highest(self, repo):
        """Smith gave MATH301 rank 1 → highest normalized weight among her preferences."""
        cp = repo.course_preferences
        row = cp.loc["Smith"]
        # MATH301 should have the highest weight (rank 1 → highest score)
        assert row["MATH301"] == row[row > 0].max()

    def test_jones_ranks_math302_highest(self, repo):
        cp = repo.course_preferences
        row = cp.loc["Jones"]
        assert row["MATH302"] == row[row > 0].max()

    def test_brown_ranks_math401_highest(self, repo):
        cp = repo.course_preferences
        row = cp.loc["Brown"]
        assert row["MATH401"] == row[row > 0].max()


class TestPreferredCourses:
    def test_smith_preferred_courses(self, repo):
        """Smith ranked MATH301, MATH302, MATH401 (MATH402=0 → not preferred)."""
        prefs = set(repo.preferred_courses["Smith"])
        assert "MATH301" in prefs
        assert "MATH302" in prefs
        assert "MATH401" in prefs
        assert "MATH402" not in prefs

    def test_jones_preferred_courses(self, repo):
        """Jones ranked MATH302, MATH401, MATH402 (MATH301=0)."""
        prefs = set(repo.preferred_courses["Jones"])
        assert "MATH302" in prefs
        assert "MATH401" in prefs
        assert "MATH402" in prefs
        assert "MATH301" not in prefs

    def test_brown_preferred_courses(self, repo):
        """Brown ranked MATH401, MATH301, MATH302 (MATH402=0)."""
        prefs = set(repo.preferred_courses["Brown"])
        assert "MATH401" in prefs
        assert "MATH301" in prefs
        assert "MATH302" in prefs
        assert "MATH402" not in prefs

    def test_every_prof_has_at_least_one_preferred_course(self, repo):
        for prof, prefs in repo.preferred_courses.items():
            assert len(prefs) > 0, f"{prof} has no preferred courses"


class TestTwoSectionPref:
    def test_brown_negative(self, repo):
        """Brown gave Q4=2 which maps to -1."""
        assert repo.two_section_pref["Brown"] == -1

    def test_smith_neutral(self, repo):
        """Smith gave Q4=3 which maps to 0."""
        assert repo.two_section_pref["Smith"] == 0

    def test_jones_neutral(self, repo):
        """Jones gave Q4=3 which maps to 0."""
        assert repo.two_section_pref["Jones"] == 0

    def test_brown_multi_section_pref_on_professor(self, repo):
        """The multi_section_pref attribute on the Professor dataclass must also be -1."""
        brown = next(p for p in repo.professors if p.last_name == "Brown")
        assert brown.multi_section_pref == -1


class TestRoomTimeslots:
    def test_room_timeslots_loaded(self, repo):
        assert len(repo.room_timeslots) > 0

    def test_correct_count(self, repo):
        """Fixture: 3 MWF × 2 rooms + 2 TR × 2 rooms = 10 room-timeslots."""
        assert len(repo.room_timeslots) == 10

    def test_all_have_positive_capacity(self, repo):
        for rt in repo.room_timeslots:
            assert rt.room_capacity > 0

    def test_rooms_present(self, repo):
        rooms = {rt.room for rt in repo.room_timeslots}
        assert "RoomA" in rooms
        assert "RoomB" in rooms

    def test_mwf_and_tr_timeslots_present(self, repo):
        timeslots = {rt.timeslot for rt in repo.room_timeslots}
        mwf = any(ts.startswith("MWF") for ts in timeslots)
        tr = any(ts.startswith("TR") for ts in timeslots)
        assert mwf
        assert tr
