"""ModelContext: the only object that touches PuLP inside model code (SPEC §10).

It owns the PuLP problem, registries of variables by family, the objective terms of
each lexicographic level, and a record of every slack variable so non-zero slacks can be
explained after solving (L1). Builders never read files or pandas objects.
"""

from __future__ import annotations

import re
from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import pulp

from scheduler.config import Config, Stage
from scheduler.domain import Instance

Sense = Literal["min", "max"]
VarCat = Literal["Continuous", "Integer", "Binary"]

LEVEL_COVERAGE = 1
LEVEL_SOFT = 2
LEVEL_SATISFACTION = 3
LEVEL_REPAIR = 10  # L5: inserted right after coverage

_UNSAFE = re.compile(r"[^A-Za-z0-9_.,\-\[\]#]")


@dataclass(frozen=True)
class ObjectiveLevel:
    """One lexicographic level: optimized in list order, then fixed within ``tolerance``."""

    key: int
    name: str
    sense: Sense
    tolerance: float = 0.0


@dataclass(frozen=True)
class SlackRecord:
    """A slack variable created by constraint ``cid`` for ``entities``."""

    cid: str
    var: Any
    entities: tuple[str, ...]
    description: str
    level: int
    weight: float


@dataclass
class ObjectiveTerm:
    level: int
    expr: Any
    label: str


@dataclass
class ModelContext:
    """Problem, variable registries and objective terms for one stage."""

    name: str
    instance: Instance
    config: Config
    stage: Stage
    levels: list[ObjectiveLevel]
    prob: Any = field(init=False)
    families: dict[str, dict[Hashable, Any]] = field(default_factory=dict)
    terms: list[ObjectiveTerm] = field(default_factory=list)
    slacks: list[SlackRecord] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    _names: set[str] = field(default_factory=set)
    _constraint_count: int = 0

    def __post_init__(self) -> None:
        self.prob = pulp.LpProblem(_safe(self.name), pulp.LpMinimize)

    # ----- variables --------------------------------------------------------------------

    def add_var(
        self,
        family: str,
        key: Hashable,
        parts: Sequence[object],
        low: float | None = 0,
        up: float | None = None,
        cat: VarCat = "Continuous",
    ) -> Any:
        """Create variable ``family[parts...]`` and register it under ``(family, key)``."""
        reg = self.families.setdefault(family, {})
        if key in reg:
            raise KeyError(f"variable {family}{key!r} already exists")
        name = self._unique(f"{family}[{','.join(str(p) for p in parts)}]")
        var = self.prob.add_variable(name, low, up, cat=cat)
        reg[key] = var
        return var

    def family(self, family: str) -> dict[Hashable, Any]:
        """All variables of a family (empty dict if none)."""
        return self.families.get(family, {})

    def get(self, family: str, key: Hashable) -> Any | None:
        return self.families.get(family, {}).get(key)

    # ----- constraints ------------------------------------------------------------------

    def add_constraint(self, constraint: Any, cid: str, parts: Sequence[object] = ()) -> None:
        """Add a constraint named ``cid[parts...]`` (unique)."""
        self._constraint_count += 1
        name = self._unique(f"{cid}[{','.join(str(p) for p in parts)}]")
        self.prob += (constraint, name)

    # ----- objective --------------------------------------------------------------------

    def level(self, key: int) -> ObjectiveLevel:
        for lv in self.levels:
            if lv.key == key:
                return lv
        raise KeyError(f"no objective level {key}")

    def add_objective_term(self, level: int, expr: Any, label: str) -> None:
        """Add ``expr`` to level ``level``, in that level's own sense (min or max)."""
        self.level(level)
        self.terms.append(ObjectiveTerm(level, expr, label))

    def level_expr(self, level: int) -> Any:
        return pulp.lpSum(t.expr for t in self.terms if t.level == level)

    def add_slack(
        self,
        cid: str,
        key: Hashable,
        entities: Sequence[str],
        description: str,
        weight: float = 1.0,
        level: int = LEVEL_SOFT,
        up: float | None = None,
        cat: VarCat = "Continuous",
    ) -> Any:
        """Create a non-negative slack and penalize ``weight * slack`` at ``level``.

        On a maximization level the penalty enters with a negative sign.
        """
        var = self.add_var(f"slack_{cid}", key, entities, 0, up, cat)
        sign = -1.0 if self.level(level).sense == "max" else 1.0
        if weight:
            self.add_objective_term(level, sign * weight * var, f"{cid} slack")
        self.slacks.append(SlackRecord(cid, var, tuple(entities), description, level, weight))
        return var

    # ----- helpers ----------------------------------------------------------------------

    @staticmethod
    def sum(items: Iterable[Any]) -> Any:
        return pulp.lpSum(items)

    @staticmethod
    def value(x: Any) -> float:
        v = pulp.value(x)
        return 0.0 if v is None else float(v)

    def fix(self, var: Any, value: float) -> None:
        """Fix a variable by tightening both bounds."""
        var.lowBound = value
        var.upBound = value

    @property
    def num_variables(self) -> int:
        return sum(len(f) for f in self.families.values())

    @property
    def num_constraints(self) -> int:
        return self._constraint_count

    def _unique(self, name: str) -> str:
        base = _safe(name)
        candidate, i = base, 1
        while candidate in self._names:
            i += 1
            candidate = f"{base}#{i}"
        self._names.add(candidate)
        return candidate


def _safe(name: str) -> str:
    return _UNSAFE.sub("_", name)
