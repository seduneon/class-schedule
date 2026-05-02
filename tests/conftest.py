"""
conftest.py — shared pytest fixtures for the class-scheduling test suite.

The sys.path insert makes `from data.loaders import ...` etc. work without
installing the backend as a package.
"""

import os
import sys

import pytest

# Make backend importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(scope="session")
def fixture_paths():
    return {
        "professors": os.path.join(FIXTURES_DIR, "professors_test.xlsx"),
        "courses": os.path.join(FIXTURES_DIR, "courses_test.xlsx"),
        "preferences": os.path.join(FIXTURES_DIR, "preferences_test.xlsx"),
        "rooms": os.path.join(FIXTURES_DIR, "rooms_test.xlsx"),
    }


@pytest.fixture(scope="session")
def repo(fixture_paths):
    """Fully loaded SchedulingDataRepository for the 3-prof / 4-course fixture."""
    from data.loaders import SchedulingDataRepository

    r = SchedulingDataRepository(
        fixture_paths["professors"],
        fixture_paths["courses"],
        fixture_paths["preferences"],
        fixture_paths["rooms"],
    )
    r.load()
    return r


@pytest.fixture(scope="session")
def phase1_result(repo):
    """Phase 1 solution; computed once per session."""
    from optimization.phase1 import solve_phase1

    return solve_phase1(repo)


@pytest.fixture(scope="session")
def phase2_result(phase1_result, repo):
    """Phase 2 solution; depends on phase1_result."""
    from optimization.phase2 import solve_phase2

    return solve_phase2(phase1_result, repo)
