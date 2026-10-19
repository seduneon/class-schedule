"""Static HTML weekly grid for quick viewing (SPEC L6)."""

from __future__ import annotations

import html
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from scheduler.config import Config
from scheduler.derived import conflict_groups
from scheduler.domain import Instance, Solution
from scheduler.time import format_clock

_PALETTE = (
    "#4C78A8", "#F58518", "#54A24B", "#B279A2", "#E45756",
    "#72B7B2", "#9D755D", "#EECA3B", "#FF9DA6", "#79706E",
)  # fmt: skip

_CSS = """
:root { --bg:#ffffff; --fg:#1d1d1f; --muted:#6e6e73; --line:#e5e5ea; --panel:#f5f5f7; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#161618; --fg:#f2f2f7; --muted:#a1a1a6; --line:#2c2c2e; --panel:#1f1f22; }
}
body { font: 14px/1.4 -apple-system, system-ui, sans-serif; margin: 0 16px 48px; background: var(--bg); color: var(--fg); }
h1 { font-size: 22px; margin: 24px 0 4px; }
h2 { font-size: 17px; margin: 28px 0 8px; }
h3 { font-size: 14px; margin: 18px 0 6px; color: var(--muted); font-weight: 600; }
.meta { color: var(--muted); margin-bottom: 12px; }
nav a { margin-right: 14px; color: inherit; }
.week { display: grid; grid-template-columns: 52px repeat(var(--days), minmax(110px, 1fr)); border: 1px solid var(--line); border-radius: 8px; overflow-x: auto; background: var(--panel); }
.hdr { text-align: center; font-weight: 600; padding: 6px 0; border-bottom: 1px solid var(--line); }
.col { position: relative; border-left: 1px solid var(--line); height: var(--h); }
.axis { position: relative; height: var(--h); }
.tick { position: absolute; right: 6px; font-size: 11px; color: var(--muted); transform: translateY(-50%); }
.rule { position: absolute; left: 0; right: 0; border-top: 1px dashed var(--line); }
.ev { position: absolute; left: 3px; right: 3px; border-radius: 5px; padding: 2px 5px; font-size: 11px; color: #fff; overflow: hidden; }
.ev b { display: block; font-size: 12px; }
"""


@dataclass(frozen=True)
class _Event:
    label: str
    course: str
    prof: str
    room: str
    day: str
    start: int
    end: int


def _events(instance: Instance, solution: Solution) -> list[_Event]:
    owner = {a.section_key: a.professor_id for a in solution.assignments}
    out = []
    for p in solution.placements or ():
        pat = instance.pattern_by_id.get(p.pattern_id)
        for m in pat.meetings if pat else ():
            out.append(
                _Event(
                    f"{p.course_id}-{p.section_label}",
                    p.course_id,
                    owner.get(p.section_key, "?"),
                    p.room_id,
                    m.day,
                    m.start,
                    m.end,
                )
            )
    return out


def render_html(
    instance: Instance, solution: Solution, config: Config, title: str = "Timetable"
) -> str:
    """Self-contained HTML page with one weekly grid per professor, room and conflict group."""
    if solution.placements is None:
        raise ValueError("the solution has no placements (run Stage B first)")
    events = _events(instance, solution)
    days = list(config.time.days)
    lo = min((e.start for e in events), default=8 * 60) // 60 * 60
    hi = -(-max((e.end for e in events), default=18 * 60) // 60) * 60
    colors = {c: _PALETTE[i % len(_PALETTE)] for i, c in enumerate(instance.course_ids)}

    def grid(sub: list[_Event], detail: Callable[[_Event], str]) -> str:
        hours = range(lo, hi + 1, 60)
        parts = [f'<div class="week" style="--days:{len(days)};--h:{hi - lo}px">', "<div></div>"]
        parts += [f'<div class="hdr">{d}</div>' for d in days]
        ticks = "".join(
            f'<div class="tick" style="top:{t - lo}px">{format_clock(t)}</div>' for t in hours
        )
        parts.append(f'<div class="axis">{ticks}</div>')
        rules = "".join(f'<div class="rule" style="top:{t - lo}px"></div>' for t in hours)
        for d in days:
            evs = "".join(
                f'<div class="ev" style="top:{e.start - lo}px;height:{e.end - e.start}px;'
                f'background:{colors.get(e.course, "#888")}" '
                f'title="{html.escape(e.label)} {format_clock(e.start)}-{format_clock(e.end)}">'
                f"<b>{html.escape(e.label)}</b>{html.escape(detail(e))}</div>"
                for e in sub
                if e.day == d
            )
            parts.append(f'<div class="col">{rules}{evs}</div>')
        parts.append("</div>")
        return "".join(parts)

    def section(
        name: str, anchor: str, key: Callable[[_Event], str], detail: Callable[[_Event], str]
    ) -> str:
        groups: dict[str, list[_Event]] = defaultdict(list)
        for e in events:
            groups[key(e)].append(e)
        body = "".join(
            f"<h3>{html.escape(k)}</h3>{grid(groups[k], detail)}" for k in sorted(groups)
        )
        return f'<h2 id="{anchor}">{name}</h2>{body}'

    group_html = []
    for g in conflict_groups(instance, config):
        sub = [e for e in events if e.course in g.course_ids]
        if sub:
            group_html.append(f"<h3>{html.escape(g.id)}</h3>{grid(sub, lambda e: e.prof)}")
    status = solution.meta.get("status", "")
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{html.escape(title)}</title><style>{_CSS}</style></head><body>"
        f"<h1>{html.escape(title)}</h1><div class='meta'>{len(solution.placements)} sections scheduled"
        f"{' · ' + html.escape(str(status)) if status else ''}</div>"
        "<nav><a href='#prof'>Professors</a><a href='#room'>Rooms</a>"
        "<a href='#groups'>Conflict groups</a></nav>"
        + section("Professors", "prof", lambda e: e.prof, lambda e: f" {e.room}")
        + section("Rooms", "room", lambda e: e.room, lambda e: f" {e.prof}")
        + "<h2 id='groups'>Conflict groups</h2>"
        + ("".join(group_html) or "<p class='meta'>No conflict groups.</p>")
        + "</body></html>\n"
    )
