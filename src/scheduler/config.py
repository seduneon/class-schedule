"""Configuration (SPEC §9). Unknown keys and unknown constraint IDs are errors."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, TypeVar

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializeAsAny,
    field_validator,
    model_validator,
)

from scheduler.domain import DAYS


class Mode(StrEnum):
    """Constraint mode (SPEC §4)."""

    HARD = "hard"
    SOFT = "soft"
    OFF = "off"


class Stage(StrEnum):
    A = "A"
    B = "B"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConstraintSettings(_Strict):
    """Settings common to every constraint.

    ``weight`` multiplies the constraint's slack in the objective; ``level`` is the
    lexicographic level the slack is minimized at (soft mode).
    """

    mode: Mode
    weight: float = Field(default=1.0, ge=0)
    level: int = Field(default=2, ge=1, le=3)

    @field_validator("mode", mode="before")
    @classmethod
    def _yaml_off(cls, v: object) -> object:
        """YAML 1.1 reads a bare ``off`` as ``False``."""
        return "off" if v is False else v


class A2Settings(ConstraintSettings):
    allow_overload: bool = False


class A5Settings(ConstraintSettings):
    bonus_per_extra: float = Field(default=0.1, ge=0)


class B7Settings(ConstraintSettings):
    recitation_after_first_lecture: bool = False


class B9Settings(ConstraintSettings):
    reward: float = Field(default=0.05, ge=0)


class B10Settings(ConstraintSettings):
    max_consecutive: int = Field(default=3, ge=1)


class B11Settings(ConstraintSettings):
    scope: Literal["room", "building"] = "room"


class ConstraintSpec(_Strict):
    """One row of the SPEC §4 constraint index."""

    id: str
    name: str
    stage: Stage
    priority: Literal["must", "should", "could"]
    default_mode: Mode


CONSTRAINT_INDEX: tuple[ConstraintSpec, ...] = tuple(
    ConstraintSpec(id=i, name=n, stage=Stage(i[0]), priority=pr, default_mode=Mode(m))
    for i, n, pr, m in (
        ("A1", "Section coverage", "must", "hard"),
        ("A2", "Teaching load range", "must", "soft"),
        ("A3", "Eligibility", "must", "hard"),
        ("A4", "Pre-assignments", "must", "hard"),
        ("A5", "Multi-section preference", "should", "soft"),
        ("A6", "Max distinct preparations", "should", "soft"),
        ("A7", "Lecture–recitation staffing", "should", "off"),
        ("A8", "Timetable capacity pre-check", "should", "hard"),
        ("A9", "Course satisfaction fairness", "should", "soft"),
        ("B1", "Section scheduled once", "must", "hard"),
        ("B2", "No room overlap", "must", "hard"),
        ("B3", "No professor overlap", "must", "hard"),
        ("B4", "Unavailability and blocked slots", "must", "hard"),
        ("B5", "Conflict groups", "must", "hard"),
        ("B6", "Spread sections of a course", "should", "soft"),
        ("B7", "Recitation–lecture relation", "should", "soft"),
        ("B8", "Max teaching days", "should", "soft"),
        ("B9", "Back-to-back preference", "should", "soft"),
        ("B10", "Max consecutive teaching", "could", "off"),
        ("B11", "Room stability", "could", "off"),
        ("B12", "Time satisfaction fairness", "should", "soft"),
        ("B13", "Day-family preference", "should", "soft"),
    )
)
CONSTRAINT_IDS: tuple[str, ...] = tuple(c.id for c in CONSTRAINT_INDEX)
CONSTRAINT_BY_ID: dict[str, ConstraintSpec] = {c.id: c for c in CONSTRAINT_INDEX}

SETTINGS_CLASS: dict[str, type[ConstraintSettings]] = {
    "A2": A2Settings,
    "A5": A5Settings,
    "B7": B7Settings,
    "B9": B9Settings,
    "B10": B10Settings,
    "B11": B11Settings,
}


def constraint_sort_key(cid: str) -> tuple[str, int]:
    """Order IDs as A1, A2, ..., A9, B1, ..., B12."""
    return (cid[0], int(cid[1:]))


class SolverConfig(_Strict):
    backend: Literal["cbc", "highs"] = "cbc"
    time_limit_s: float = Field(default=300, gt=0)
    threads: int = Field(default=4, ge=1)
    seed: int = 42
    mip_gap: float = Field(default=0.0, ge=0)


class PreferencesConfig(_Strict):
    strategy: Literal["linear", "exponential", "top_k"] = "linear"
    beta: float = Field(default=0.7, gt=0, lt=1)
    top_k: int = Field(default=5, ge=1)
    unranked_policy: Literal["forbid", "allow_low"] = "forbid"
    unranked_weight: float = Field(default=0.0, ge=0, le=1)


class TimeConfig(_Strict):
    buffer_minutes: int = Field(default=0, ge=0)
    adjacency_gap_minutes: int = Field(default=15, ge=0)
    days: tuple[str, ...] = ("Mon", "Tue", "Wed", "Thu", "Fri")

    @field_validator("days")
    @classmethod
    def _known_days(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        bad = [d for d in v if d not in DAYS]
        if bad:
            raise ValueError(f"unknown days {bad}; use {list(DAYS)}")
        return v


class RecitationsConfig(_Strict):
    staffing: Literal["faculty", "same_as_lecture", "external"] = "faculty"


class ConflictGroupsConfig(_Strict):
    auto_levels: bool = True


class Tolerances(_Strict):
    level1: float = Field(default=0.0, ge=0)
    level2: float = Field(default=0.0, ge=0)


class ObjectiveConfig(_Strict):
    lambda_course_fairness: float = Field(default=0.5, ge=0)
    lambda_time_fairness: float = Field(default=0.5, ge=0)
    tolerances: Tolerances = Tolerances()


class AlternativesConfig(_Strict):
    count: int = Field(default=0, ge=0)
    min_difference: int = Field(default=3, ge=1)
    optimality_gap: float = Field(default=0.02, ge=0)


S = TypeVar("S", bound=ConstraintSettings)


class Config(_Strict):
    """Root configuration object (SPEC §9)."""

    solver: SolverConfig = SolverConfig()
    preferences: PreferencesConfig = PreferencesConfig()
    time: TimeConfig = TimeConfig()
    recitations: RecitationsConfig = RecitationsConfig()
    conflict_groups: ConflictGroupsConfig = ConflictGroupsConfig()
    objective: ObjectiveConfig = ObjectiveConfig()
    alternatives: AlternativesConfig = AlternativesConfig()
    constraints: dict[str, SerializeAsAny[ConstraintSettings]] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _fill_constraints(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        given = data.get("constraints") or {}
        if not isinstance(given, dict):
            raise ValueError("constraints must be a mapping of constraint ID to settings")
        unknown = sorted(set(given) - set(CONSTRAINT_IDS))
        if unknown:
            raise ValueError(f"unknown constraint IDs: {unknown}")
        filled: dict[str, ConstraintSettings] = {}
        for spec in CONSTRAINT_INDEX:
            raw = given.get(spec.id) or {}
            if isinstance(raw, ConstraintSettings):
                filled[spec.id] = raw
                continue
            raw = {"mode": spec.default_mode.value, **raw}
            filled[spec.id] = SETTINGS_CLASS.get(spec.id, ConstraintSettings).model_validate(raw)
        return {**data, "constraints": filled}

    def settings(self, cid: str) -> ConstraintSettings:
        """Settings for constraint ``cid``."""
        return self.constraints[cid]

    def typed_settings(self, cid: str, cls: type[S]) -> S:
        """Settings for ``cid``, checked to be of the specific settings class."""
        s = self.constraints[cid]
        if not isinstance(s, cls):
            raise TypeError(f"{cid} settings are {type(s).__name__}, expected {cls.__name__}")
        return s

    def mode(self, cid: str) -> Mode:
        return self.constraints[cid].mode

    def enabled(self, cid: str) -> bool:
        return self.constraints[cid].mode is not Mode.OFF

    def with_mode(self, cid: str, mode: Mode | str) -> Config:
        """Copy of this config with constraint ``cid`` switched to ``mode`` (ablations)."""
        new = self.constraints[cid].model_copy(update={"mode": Mode(mode)})
        return self.model_copy(update={"constraints": {**self.constraints, cid: new}})

    def with_updates(self, **sections: Any) -> Config:
        """Copy with top-level sections replaced, e.g. ``with_updates(time={...})``."""
        data = self.model_dump()
        for key, value in sections.items():
            if isinstance(value, dict) and isinstance(data.get(key), dict):
                data[key] = {**data[key], **value}
            else:
                data[key] = value
        return Config.model_validate(data)


def load_config(path: Path | str | None = None) -> Config:
    """Load a YAML config; ``None`` returns the built-in defaults."""
    if path is None:
        return Config()
    with Path(path).open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a mapping")
    return Config.model_validate(data)
