"""Validator core: Violation, registry and the ``validate`` entry point (SPEC L2).

Plain Python only. This package must never import PuLP (enforced by a test).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Literal

from scheduler.config import Config, ConstraintSettings, Mode, constraint_sort_key
from scheduler.domain import Instance, Solution

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Violation:
    """One rule violation. ``size`` is the amount (sections, units, pairs, ...)."""

    id: str
    severity: Severity
    message: str
    entities: tuple[str, ...] = ()
    size: float = 1.0

    def __str__(self) -> str:
        return f"[{self.id} {self.severity}] {self.message}"


CheckFn = Callable[[Instance, Solution, ConstraintSettings, Config], list[Violation]]
CHECKS: dict[str, CheckFn] = {}
STAGE_B_PREFIX = "B"


def check(cid: str) -> Callable[[CheckFn], CheckFn]:
    """Register a check function for constraint ``cid`` (one per ID)."""

    def register(fn: CheckFn) -> CheckFn:
        if cid in CHECKS:
            raise ValueError(f"check for {cid} registered twice")
        CHECKS[cid] = fn
        return fn

    return register


def severity_for(settings: ConstraintSettings | Mode) -> Severity:
    """Hard-mode violations are errors; soft-mode ones are warnings."""
    mode = settings if isinstance(settings, Mode) else settings.mode
    return "error" if mode is Mode.HARD else "warning"


def validate(
    instance: Instance,
    solution: Solution,
    config: Config,
    ids: Iterable[str] | None = None,
) -> list[Violation]:
    """Run every registered check whose constraint is not ``off``.

    Stage B checks are skipped when the solution has no placements.
    """
    wanted = set(ids) if ids is not None else set(CHECKS)
    out: list[Violation] = []
    for cid in sorted(CHECKS, key=constraint_sort_key):
        if cid not in wanted or not config.enabled(cid):
            continue
        if cid.startswith(STAGE_B_PREFIX) and solution.placements is None:
            continue
        out.extend(CHECKS[cid](instance, solution, config.settings(cid), config))
    return out


def errors(violations: Iterable[Violation]) -> list[Violation]:
    return [v for v in violations if v.severity == "error"]
