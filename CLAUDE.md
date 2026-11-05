# CLAUDE.md

Class scheduling optimizer (MATH 499 capstone, Nazarbayev University).
Stage A assigns professors to course sections; Stage B assigns sections to time patterns and rooms. Both are MILPs built with PuLP.

## Source of truth

**`docs/SPEC.md` defines every rule, formula, data format and milestone.** Read the relevant sections before any change. If code and spec disagree, the spec wins. If the spec seems wrong or ambiguous, stop and ask; never silently diverge.

This is a from-scratch project. Do not port or imitate code from the previous capstone. Use it only as a source of requirements and known bugs (see the regression tests in SPEC §12).

## Commands

```bash
uv sync                          # install
uv run pytest                    # all fast tests
uv run pytest -m slow            # experiment-sized tests
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run scheduler --help          # CLI
```

## Stack

Python 3.12, uv, PuLP (CBC default, HiGHS optional), pydantic v2, pandas (io/reporting only), openpyxl, typer, pytest, hypothesis.

## Repository layout

SPEC §10 is the tree. Keep it; `tests/test_repo_layout.py` enforces the tracked part.
- Nothing new at the repository root. A new top-level entry needs a SPEC §10 change first.
- Real data (supervisor files, anything with names, past-capstone material) lives only in `data/private/`, never at the root or in `docs/`:
  - `data/private/<term>/raw/<YYYY-MM-DD>/` the supervisor's files as received, never edited; `fixes.yaml` next to `raw/`
  - `instance/` converter output; `runs/` results (always pass `--runs-dir data/private/<term>/runs`, never the root `runs/`)
  - `experiments/<name>/` what-if copies with their own fixes, instance and runs; never overwrite the term's `instance/` or `runs/` for an experiment
  - `deliveries/<YYYY-MM-DD>/` what was prepared for the supervisor; `verify/` and `VERIFICATION_<date>.md` for independent checks
  - `data/private/reference/` past-capstone material (requirements source only)
- When a file lands somewhere else (e.g. a supervisor folder dropped at the root), move it into this layout, delete duplicates only after a byte compare, and say what moved.
- The root `runs/` is for example data only. `experiments/results/` is generated output. Both are git-ignored, as are `*.xlsx`, `*.xls`, `*.zip`, `*.pdf` everywhere.

## Before anything goes to the supervisor (SPEC §8.1.3)

A result is not ready until it has been checked against the supervisor's Excel files by scripts that never import `scheduler`. Every time, in order:
1. Run on clean, committed `main` (`run.json` must show `git_dirty: false`), with `--runs-dir data/private/<term>/runs`.
2. If `time_room.xlsx` is missing, set `time_patterns_from_survey: true` so the day-family rule (A8) is checked; say in the e-mail that times come from the survey.
3. `uv run python -I data/private/<term>/verify/verify_all.py RAW INSTANCE RUN` must print `ALL CHECKS PASSED` (V1 conversion, V2 hard rules incl. A8, V3 report.xlsx, V4 provenance). If the survey layout changed, update the scripts first; never weaken a check to make it pass.
4. Read the run's final `Result:` line: every part listed as not checked goes into the e-mail as a caveat.
5. Write `VERIFICATION_<date>.md` (passed / not checked / open questions) and copy exactly what is sent into `deliveries/<date>/`.

Never send, and never call a result verified, if a step was skipped. Say which one.

## Rules

- **Constraint changes follow SPEC §11 exactly:** spec → validator check + tests → ablation pair test → builder → config → status/CHANGELOG.
- Every constraint has an ID (A1, B5, …). Use it in file names, registry keys, config keys, test names and commit messages.
- `scheduler.validation` must never import pulp. `scheduler.model` must never import pandas or read files.
- Impossible combinations are filtered out when variables are created. Don't use big-M to switch them off.
- Time conflicts always come from `scheduler.time` (meeting overlap and cliques), never from comparing slot labels.
- Objectives are lexicographic (`solve/lexicographic.py`). Never add ad-hoc large penalty constants.
- Deterministic everything: sorted iteration, a fixed solver seed, no reliance on dict or set ordering from inputs.
- Type hints everywhere; mypy strict must pass. Small functions; docstrings on public functions that state the math they implement (with the SPEC constraint ID).
- Tests use tiny instances built in code or from `data/examples/tiny`. Never commit anything from `data/private/`.
- Work milestone by milestone (SPEC §13). Finish a milestone with all tests green before starting the next. Update `docs/CHANGELOG.md`.

## When the user edits SPEC.md

Diff the spec against the implementation:
- For constraints marked `planned`, implement them following §11.
- For changed formulations of `implemented` constraints, update the check, the tests and the builder together.
- Report what changed and anything in the new text that is ambiguous.
