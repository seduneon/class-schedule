"""Run every experiment and write CSVs + plots to experiments/results/.

uv run python experiments/run_all.py [--quick]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from scheduler.config import load_config
from scheduler.experiment import EXPERIMENTS

sys.path.insert(0, str(Path(__file__).parent))
from plots import make_plots

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    quick = "--quick" in sys.argv
    seeds = [0, 1] if quick else [0, 1, 2, 3, 4]
    cfg = load_config(ROOT / "configs" / "default.yaml").with_updates(
        solver={"threads": 1, "time_limit_s": 120}
    )
    out = ROOT / "experiments" / "results"
    out.mkdir(parents=True, exist_ok=True)
    for name, run in EXPERIMENTS.items():
        rows = run(cfg, seeds)
        pd.DataFrame(rows).to_csv(out / f"{name}.csv", index=False)
        print(f"{name}: {len(rows)} rows -> {out / (name + '.csv')}")
    for path in make_plots(out):
        print(f"plot -> {path}")


if __name__ == "__main__":
    main()
