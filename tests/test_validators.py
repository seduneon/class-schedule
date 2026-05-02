"""
test_validators.py — tests for data/validators.py.
"""

import pytest


class TestValidateLoads:
    def test_validate_loads_ok(self, repo):
        """Fixture has no pre-assignments → validate_loads should not raise."""
        from data.validators import validate_loads

        validate_loads(repo)  # must not raise

    def test_validate_loads_fails_when_over_assigned(self):
        """
        Build a minimal repository-like object where one professor has more
        pre-assigned sections than their load, and assert ValueError is raised.
        """
        from data.validators import validate_loads

        class FakeRepo:
            assigned_dict = {"Smith": {"MATH301": [0, 1, 2]}}  # 3 sections
            load_dict = {"Smith": 2}  # load = 2  → violation

        with pytest.raises(ValueError, match="Smith"):
            validate_loads(FakeRepo())

    def test_validate_loads_ok_when_exactly_at_limit(self):
        """Pre-assignments exactly equal to load must not raise."""
        from data.validators import validate_loads

        class FakeRepo:
            assigned_dict = {"Jones": {"MATH302": [0], "MATH401": [0]}}  # 2 sections
            load_dict = {"Jones": 2}

        validate_loads(FakeRepo())  # must not raise

    def test_validate_loads_ignores_profs_without_preassignments(self):
        """Professors absent from assigned_dict are not checked."""
        from data.validators import validate_loads

        class FakeRepo:
            assigned_dict = {}  # nobody pre-assigned
            load_dict = {"Smith": 2, "Jones": 2}

        validate_loads(FakeRepo())  # must not raise

    def test_validate_loads_multiple_courses_summed(self):
        """Sections across multiple courses are summed per professor."""
        from data.validators import validate_loads

        class FakeRepo:
            # 2 sections of MATH301 + 1 section of MATH302 = 3 total > load 2
            assigned_dict = {
                "Brown": {"MATH301": [0, 1], "MATH302": [0]}
            }
            load_dict = {"Brown": 2}

        with pytest.raises(ValueError, match="Brown"):
            validate_loads(FakeRepo())


class TestNormalizeWeights:
    def test_normalize_weights_passthrough(self, repo):
        """normalize_weights is a pass-through; it must return a copy of the input."""
        import pandas as pd
        from data.validators import normalize_weights

        cp = repo.course_preferences.copy()
        result = normalize_weights(cp)

        # Should be a copy, not the same object
        assert result is not cp
        # Values must be unchanged
        assert result.equals(cp)
