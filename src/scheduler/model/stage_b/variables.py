"""Stage B variables (SPEC §6.1): y_{s,t,r} in {0,1} for (s, t, r) in F only.

F (SPEC §3.2): cap_r >= cap_s, room type matches, t in A_r, t allows k(s), t is not
blocked, t meets only on teaching days, the professor of s is available at every meeting
of t, and Stage B pins (L4) are respected. Impossible combinations are never created.
With B4 ``soft`` unavailable patterns are kept (and penalized by B4); with B4 ``off``
neither blocked slots nor unavailability filter F. Room availability always filters F.
With B13 ``hard``, patterns outside the professor's day families are filtered too.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any, cast

from scheduler.config import Config, Mode
from scheduler.derived import (
    StageBSection,
    off_family,
    pattern_blocked,
    pattern_problem,
    professor_unavailable,
    room_problem,
    room_unavailable,
)
from scheduler.domain import Instance, SectionKey
from scheduler.model.context import ModelContext
from scheduler.preferences import time_weights

YKey = tuple[SectionKey, str, str]  # (section key, pattern id, room id)


@dataclass(frozen=True)
class Triple:
    section: StageBSection
    pattern_id: str
    room_id: str
    unavailable: bool  # only possible when B4 is soft or off

    @property
    def key(self) -> YKey:
        return (self.section.key, self.pattern_id, self.room_id)


def feasible_triples(
    instance: Instance, config: Config, sections: Sequence[StageBSection]
) -> list[Triple]:
    """Enumerate F in deterministic order (section, pattern, room)."""
    b4 = config.mode("B4")
    b13_hard = config.mode("B13") is Mode.HARD
    out: list[Triple] = []
    for sb in sections:
        pin = instance.stage_b_pin_by_section.get(sb.key)
        rooms = [
            r
            for r in instance.rooms
            if room_problem(sb.section, r) is None and (pin is None or pin.room_id in (None, r.id))
        ]
        if not rooms:
            continue
        for pid in instance.pattern_ids:
            if pin is not None and pin.pattern_id not in (None, pid):
                continue
            pattern = instance.pattern_by_id[pid]
            if pattern_problem(instance, config, sb.section, pattern) is not None:
                continue
            if b4 is not Mode.OFF and pattern_blocked(instance, pid):
                continue
            unavailable = not sb.placeholder and professor_unavailable(
                instance, sb.professor_id, pid
            )
            if unavailable and b4 is Mode.HARD:
                continue
            if b13_hard and off_family(instance, sb.professor_id, pid):
                continue
            out.extend(
                Triple(sb, pid, r.id, unavailable)
                for r in rooms
                if not room_unavailable(instance, r.id, pid)
            )
    return out


def build_variables(ctx: ModelContext, sections: Sequence[StageBSection]) -> None:
    """Create y for every triple of F and index them for the builders."""
    triples = feasible_triples(ctx.instance, ctx.config, sections)
    for tr in triples:
        ctx.add_var("y", tr.key, [tr.section.id, tr.pattern_id, tr.room_id], 0, 1, "Binary")
    ctx.data["sections"] = tuple(sections)
    ctx.data["triples"] = tuple(triples)
    ctx.data["time_weights"] = time_weights(ctx.instance, ctx.config.preferences)
    yv = ctx.family("y")
    owners: dict[str, Callable[[Triple], object]] = {
        "prof": lambda tr: tr.section.professor_id,
        "room": lambda tr: tr.room_id,
        "section": lambda tr: tr.section.key,
        "course": lambda tr: tr.section.section.course_id,
    }
    for name, owner_of in owners.items():
        idx: dict[tuple[object, str], list[Any]] = {}
        for tr in triples:
            idx.setdefault((owner_of(tr), tr.pattern_id), []).append(yv[tr.key])
        ctx.data[f"idx_{name}_pattern"] = idx


def indexed(ctx: ModelContext, index: str, owner: Any, pattern_ids: Iterable[str]) -> list[Any]:
    """y variables of ``owner`` (professor, room, section key or course) in ``pattern_ids``.

    ``index`` is one of ``prof``, ``room``, ``section``, ``course``.
    """
    idx: dict[Any, list[Any]] = ctx.data[f"idx_{index}_pattern"]
    return [v for t in sorted(pattern_ids) for v in idx.get((owner, t), ())]


def sections(ctx: ModelContext) -> tuple[StageBSection, ...]:
    return cast(tuple[StageBSection, ...], ctx.data["sections"])


def triples(ctx: ModelContext) -> tuple[Triple, ...]:
    return cast(tuple[Triple, ...], ctx.data["triples"])


def y(ctx: ModelContext, tr: Triple) -> Any:
    return ctx.family("y")[tr.key]


def by_section(ctx: ModelContext) -> dict[SectionKey, list[Triple]]:
    """Triples grouped by section."""
    out: dict[SectionKey, list[Triple]] = {s.key: [] for s in sections(ctx)}
    for tr in triples(ctx):
        out[tr.section.key].append(tr)
    return out


def professors(ctx: ModelContext) -> list[str]:
    """Real (non-placeholder) professors that teach Stage B sections, sorted."""
    return sorted({s.professor_id for s in sections(ctx) if not s.placeholder})


def busy(ctx: ModelContext, professor_id: str, pattern_ids: Iterable[str]) -> Any:
    """sum_{t in pattern_ids} busy_{p,t}, with busy_{p,t} = sum_{s in S_p} sum_r y_{s,t,r}."""
    return ctx.sum(indexed(ctx, "prof", professor_id, pattern_ids))


def time_satisfaction(ctx: ModelContext, professor_id: str) -> Any | None:
    """sat^T_p = (1 / |S_p|) sum_{s in S_p} sum_{t,r} w^T_{p,t} y_{s,t,r}; None if S_p is empty."""
    own = [s for s in sections(ctx) if s.professor_id == professor_id]
    if not own:
        return None
    w: dict[tuple[str, str], float] = ctx.data["time_weights"]
    return ctx.sum(
        (w.get((professor_id, tr.pattern_id), 0.0) / len(own)) * y(ctx, tr)
        for tr in triples(ctx)
        if tr.section.professor_id == professor_id
    )
