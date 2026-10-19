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
