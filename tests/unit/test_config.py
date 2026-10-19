"""Config loading (SPEC §9)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from scheduler.config import (
    CONSTRAINT_IDS,
    A2Settings,
    Config,
    Mode,
    load_config,
)
from tests.factory import ROOT


def test_default_yaml_loads_and_covers_every_id() -> None:
    cfg = load_config(ROOT / "configs" / "default.yaml")
    assert set(cfg.constraints) == set(CONSTRAINT_IDS)
    assert cfg.typed_settings("A2", A2Settings).weight == 10
    assert cfg.mode("B10") is Mode.OFF


def test_missing_ids_use_spec_defaults() -> None:
    cfg = Config()
    assert cfg.mode("A1") is Mode.HARD
    assert cfg.mode("A7") is Mode.OFF
    assert cfg.mode("B6") is Mode.SOFT


def test_unknown_keys_are_errors(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("solver: {backend: cbc, nonsense: 1}\n")
    with pytest.raises(ValidationError):
        load_config(bad)
    with pytest.raises(ValidationError, match="unknown constraint IDs"):
        Config.model_validate({"constraints": {"Z9": {"mode": "hard"}}})
    with pytest.raises(ValidationError):
        Config.model_validate({"constraints": {"A2": {"mode": "soft", "bogus": True}}})
    with pytest.raises(ValidationError):
        Config.model_validate({"top": 1})


def test_with_mode_and_updates() -> None:
    cfg = Config().with_mode("B6", "off").with_updates(time={"buffer_minutes": 10})
    assert cfg.mode("B6") is Mode.OFF
    assert cfg.time.buffer_minutes == 10
    assert cfg.typed_settings("A2", A2Settings).allow_overload is False


def test_with_updates_keeps_constraint_specific_settings() -> None:
    """Regression: dumping the config must keep subclass fields such as max_consecutive."""
    cfg = Config.model_validate({"constraints": {"B10": {"mode": "hard", "max_consecutive": 2}}})
    again = cfg.with_updates(solver={"threads": 1})
    assert again.model_dump()["constraints"]["B10"]["max_consecutive"] == 2
    assert again.settings("B10") == cfg.settings("B10")
