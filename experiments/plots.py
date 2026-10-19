"""Static figures for the report: one measure per axis, fixed categorical order, thin marks."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Categorical slots 1..6, always assigned in this order (dataviz reference palette, light).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
INK, MUTED, GRID = "#1d1d1f", "#6e6e73", "#e5e5ea"


def _axes(title: str, xlabel: str, ylabel: str):  # type: ignore[no-untyped-def]
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.4, 3.8), dpi=150)
    ax.set_title(title, loc="left", color=INK, fontsize=11)
    ax.set_xlabel(xlabel, color=MUTED)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED)
    return fig, ax


def _lines(
    frame: pd.DataFrame, x: str, ys: list[tuple[str, str]], title: str, ylabel: str, out: Path
) -> None:
    fig, ax = _axes(title, x, ylabel)
    means = frame.groupby(x)[[c for c, _ in ys]].mean()
    for i, (col, label) in enumerate(ys):
        ax.plot(
            means.index,
            means[col],
            color=SERIES[i],
            linewidth=2,
            marker="o",
            markersize=5,
            label=label,
        )
    if len(ys) > 1:
        ax.legend(frameon=False, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(out)


def make_plots(results: Path) -> list[Path]:
    """Render the figures for whichever CSVs exist; returns the files written."""
    try:
        import matplotlib

        matplotlib.use("Agg")
    except ImportError:  # plots are optional
        return []
    written: list[Path] = []
    if (results / "scaling.csv").exists():
        f = pd.read_csv(results / "scaling.csv")
        out = results / "scaling.png"
        _lines(
            f,
            "size",
            [("A_wall_s", "Stage A"), ("B_wall_s", "Stage B")],
            "Solve time vs instance size (professors = courses)",
            "seconds (mean over seeds)",
            out,
        )
        written.append(out)
    if (results / "fairness.csv").exists():
        f = pd.read_csv(results / "fairness.csv")
        for col, title in (
            ("total_sat_course", "Total course satisfaction"),
            ("min_sat_course", "Minimum course satisfaction"),
        ):
            out = results / f"fairness_{col}.png"
            _lines(
                f, "lambda", [(col, title)], f"{title} vs fairness weight λ", "mean over seeds", out
            )
            written.append(out)
    if (results / "weights.csv").exists():
        f = pd.read_csv(results / "weights.csv")
        means = f.groupby("strategy", sort=False)["share_first_choice"].mean()
        fig, ax = _axes("Share of sections given as a first choice", "strategy", "share")
        ax.bar(range(len(means)), means.values, color=SERIES[0], width=0.6)
        ax.set_xticks(range(len(means)), means.index)
        fig.tight_layout()
        out = results / "weights.png"
        fig.savefig(out)
        written.append(out)
    return written
