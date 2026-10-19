# class-scheduler

Two-stage MILP class scheduling optimizer (MATH 499 capstone, Nazarbayev University).

- **Stage A** assigns professors to course sections.
- **Stage B** assigns sections to time patterns and rooms.

The full specification lives in [`docs/SPEC.md`](docs/SPEC.md).

```bash
uv sync
uv run scheduler run data/examples/tiny          # check → Stage A → Stage B
# results: runs/<YYYY-MM-DD_HH-MM-SS>_tiny/ (runs/latest points to the newest)
# edit runs/latest/assignments.csv, then re-run Stage B into a new folder:
uv run scheduler run data/examples/tiny --assignments runs/latest/assignments.csv
uv run scheduler validate data/examples/tiny runs/latest/solution.json
```

Each run folder holds `assignments.csv`, `stage_a.json`, `solution.json`, `report.xlsx`,
`timetable.html`, plus `run.json` (inputs, config, git commit, objectives, timings),
`config.yaml`, `check.txt` and `log.txt` (SPEC L9). Old runs are never overwritten.
`run.json` also counts hard violations (`hard_violations`). `runs/` is git-ignored.

To compare inputs, just point at another data folder, e.g. `data/examples/medium_no_recitations` (the medium instance without recitation sections). The step-by-step commands (`check`, `assign`, `timetable`, `report`)
also write to a new run folder unless `--out` is given.

More commands: `alternatives` (L3), `repair` (L5), `generate` (L8), `experiment` (M10).
Experiments: `uv run python experiments/run_all.py [--quick]` → `experiments/results/` (notes in `docs/report_notes.md`).

Development: `uv run pytest` (fast), `uv run pytest -m slow`, `uv run ruff check .`, `uv run mypy src`.

## Converting the legacy survey files

```bash
uv run scheduler convert-legacy refall2026mathcourselist -o data/private/fall2026 \
  --add-offering MATH161:R:8:57 --add-offering MATH162:R:15:57 \
  --add-offering MATH263:R:1:60 --add-offering MATH273:R:2:90
# read data/private/fall2026/review.csv, then:
uv run scheduler check data/private/fall2026
```

Real data stays in `data/private/` (git-ignored). `--anonymize` produces a shareable copy; that is how `data/examples/medium` was made. Mapping: SPEC §8.1.
