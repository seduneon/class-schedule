"""Constraint builder registry: ``@constraint("A1")`` and lookup by ID / stage (SPEC §10)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar, Protocol

from scheduler.config import CONSTRAINT_BY_ID, ConstraintSettings, Stage, constraint_sort_key

if TYPE_CHECKING:
    from scheduler.model.context import ModelContext


class ConstraintBuilder(Protocol):
    """Adds the constraints, slacks and objective terms of one constraint ID."""

    id: ClassVar[str]
    stage: ClassVar[Stage]

    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None: ...


BUILDERS: dict[str, type[ConstraintBuilder]] = {}


def constraint(cid: str) -> Callable[[type], type]:
    """Class decorator registering a builder for constraint ``cid``."""
    if cid not in CONSTRAINT_BY_ID:
        raise ValueError(f"{cid} is not in the SPEC §4 constraint index")

    def register(cls: type) -> type:
        if cid in BUILDERS:
            raise ValueError(f"builder for {cid} registered twice")
        cls.id = cid  # type: ignore[attr-defined]
        cls.stage = CONSTRAINT_BY_ID[cid].stage  # type: ignore[attr-defined]
        BUILDERS[cid] = cls
        return cls

    return register


def builders_for(stage: Stage) -> list[type[ConstraintBuilder]]:
    """Registered builders of a stage, in ID order."""
    return [
        BUILDERS[cid]
        for cid in sorted(BUILDERS, key=constraint_sort_key)
        if BUILDERS[cid].stage is stage
    ]
