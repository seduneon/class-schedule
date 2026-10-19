from __future__ import annotations

import pytest

from scheduler.config import Config, load_config
from scheduler.domain import Instance
from scheduler.io import read_instance
from tests.factory import ROOT, TINY


@pytest.fixture
def tiny() -> Instance:
    return read_instance(TINY)


@pytest.fixture
def default_config() -> Config:
    return load_config(ROOT / "configs" / "default.yaml")
