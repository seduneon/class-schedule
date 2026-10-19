# class-scheduler

Two-stage MILP class scheduling optimizer (MATH 499 capstone, Nazarbayev University).

- **Stage A** assigns professors to course sections.
- **Stage B** assigns sections to time patterns and rooms.

The full specification lives in [`docs/SPEC.md`](docs/SPEC.md).

```bash
uv sync
uv run scheduler check data/examples/tiny
uv run scheduler assign data/examples/tiny --out out/tiny
uv run scheduler timetable data/examples/tiny --assignments out/tiny/assignments.csv --out out/tiny
uv run scheduler validate data/examples/tiny out/tiny/solution.json
```

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
