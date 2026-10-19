# Changelog

All notable changes, by milestone (SPEC §13). Constraint IDs are cited where relevant.

## M0 — Scaffold
- `pyproject.toml` (uv, ruff, mypy strict, pytest with `slow` marker), GitHub Actions CI, package layout from SPEC §10.
- PuLP pinned to `<4`: PuLP 4 no longer bundles CBC, which is the default backend (SPEC §9).
- PuLP 4 with the `cbc` extra (bundled CBC via `cbcbox`); the solver adapter uses `COIN_CMD` / `HiGHS`.
- `ruff` ignores `docs/` so the formatter never rewrites SPEC.md.

## M1 — Domain + IO
- Frozen dataclasses for every entity (`scheduler.domain`); immutable `Instance` with cached lookups and a `memo` cache for config-dependent structures.
- Section labels: per (course, type) larger capacities get lower labels (`1L`, `2L`, ...).
- pydantic row schemas with row-level error messages; readers for a CSV folder or a single `.xlsx`; writers for assignments (CSV/xlsx), the JSON solution and whole instances.
- `Config` (pydantic, unknown keys / IDs are errors) and `configs/default.yaml`; YAML's bare `off` is read as mode `off`.
- Tiny example (`data/examples/tiny`): professors A–C, MATH 161 ×2, 351, 361.

## M2 — Time engine
- Day/time parsing (`MWF`, `TR`, `TTh`, `Mon;Wed`), half-open interval overlap with buffer, maximal overlap cliques, adjacency, consecutive chains, alpha_p via an independent-set MIP (cached).
- Property tests: every overlapping pair shares a clique; cliques are maximal; alpha matches brute force.

## M3 — Validator + diagnostics
- `scheduler.validation`: `Violation`, `@check(ID)` registry, `validate()`; checks for A1–A4, B1–B5; L4 pin check. No PuLP import (architecture test).
- Room capacity/type and pattern-type fit of a placement are checked under B1 (no separate ID in §4).
- `scheduler.diagnostics`: L1 pre-solve findings (load capacity, eligible capacity, rooms, alpha_p, conflict-group capacity, data integrity, pin conflicts, Stage B feasibility).

## M4 — Model framework
- `ModelContext` (the only PuLP user in model code), `@constraint(ID)` registry, solver backend (CBC/HiGHS, seeded, status mapping incl. time and gap limits), lexicographic solve with per-level tolerances.

## M5 — Stage A core
- Variables n/z with A3 filtering, A1–A4 builders, level-3 course satisfaction, label attachment (§5.4) with `pre`/`model` sources.
- Golden test (Stage A) and ablation pair tests for A1–A4.

## M6 — Stage B core
- Feasible set F, B1–B5 builders (clique formulation), level-3 time satisfaction.
- Regression tests: `test_room_cannot_be_double_booked`, `test_overlapping_patterns_with_different_labels_conflict`, `test_same_course_sections_may_overlap_in_conflict_group`; ablation pair tests for B1–B5.

## M7 — Pipeline + CLI + reporting
- `pipeline.run_stage_a` / `run_stage_b` (diagnostics → model → lexicographic solve → validation → slack explanations).
- CLI: `check`, `assign`, `timetable`, `validate`, `report`.
- L4 pins (Stage A: fixed counts; Stage B: F filtered by pattern/room).
- Excel workbook (timetables per professor/room/conflict group, assignments, satisfaction, violations, slacks, diagnostics, solver stats) and a static HTML weekly grid.
- SPEC §4: A1–A4 and B1–B5 marked `implemented`.

## M8 — Should-constraints
Each via the SPEC §11 workflow (validator check + unit tests → ablation pair test → builder → config → status):
- A5 multi-section preference (cap for mu = -1, bonus for mu = +1), A6 max preparations,
  A7 recitation staffing (`faculty`, `same_as_lecture` as an integer share band, `external` with `TBA-<course>`),
  A8 timetable capacity (alpha_p; the validator uses an exact pure-Python independent set), A9 course fairness.
- B6 spread sections, B7 recitation–lecture relation (incl. `recitation_after_first_lecture`), B8 max teaching days,
  B9 back-to-back (compact reward / spread penalty), B12 time fairness.
- A9 / B12 validator checks report the unfair extreme (a professor with satisfaction 0) as a warning, since a reward term cannot be violated.
- Golden test with the full default config: level 3 = 2.75 for both stages.
- SPEC §4: A5–A9, B6–B9, B12 marked `implemented`.

## M9 — Alternatives + repair
- L3 `solve/alternatives.py`: no-good cuts on z (Stage A) and on y~_{s,t} (Stage B, room changes ignored); level 3 kept within `alternatives.optimality_gap`; ranked list with a diff against the best. The lexicographic solve no longer locks its last level, so alternatives can relax it.
- L5 `solve/repair.py`: repair level inserted after coverage (Stage A: changes in z; Stage B: moved (s, t, r) decisions).
- CLI: `alternatives`, `repair`.

## M10 — Experiments
- L8 generator (`scheduler.generate`): seeded, with size, load/room tightness and preference-correlation knobs; standard MWF/TR pattern set.
- Property tests (hypothesis + generator): hard rules hold on generated instances, same seed → same solution, level-1 coverage matches the LP-relaxation bound when it is 0.
- `scheduler.experiment` (ablation, scaling, weight strategies, fairness) + `experiments/run_all.py` (CSV + PNG plots) + CLI `generate` / `experiment`; first quick results in `docs/report_notes.md`.
- matplotlib added as the optional `experiments` extra (and to the dev group).

## M11 — Could
- B10 max consecutive teaching (chains of adjacent patterns per day) and B11 room stability (rooms or buildings per professor, subtracted at level 3), each via the §11 workflow; SPEC §4 marked `implemented` (all 21 IDs now implemented).
- L7 integrated mode (`model/integrated.py`, `pipeline.run_integrated`), must-rules only, plus the `decomposition` experiment comparing it with the two-stage pipeline on a shared linear proxy objective.
- Fix: `Config.model_dump()` / `with_updates()` dropped constraint-specific settings (e.g. `max_consecutive`); constraints are now serialized with `SerializeAsAny`.
- Not done: the legacy converter (`scheduler convert-legacy`) — the legacy files are not available (SPEC D5), so its input format is unknown.

## Fall 2026 data (D5 settled, 2026-10-18)
Legacy files arrived (`refall2026mathcourselist/`, git-ignored: names, e-mails, IPs). Spec changes confirmed with the user, each via §11:
- **Room availability** (`room_availability` table, $A_r$): rooms listed there are usable only at their patterns. Always filtered out of $\mathcal{F}$ (also in the integrated model), checked under B4 (always an error). New L1 finding `room_slots`: sections needing ≥ c seats vs (room, pattern) slots with ≥ c seats.
- **B13 Day-family preference** (new, should, soft, weight 5): professors' `day_families` (e.g. `MWF`, `TR`) and `day_family_mixing` (`allow` / `avoid` / `forbid`). Off-family sections and extra families are level-2 slacks; hard mode filters off-family triples from $\mathcal{F}$; `forbid` is always hard. SPEC §4 marked `implemented`.
- **Course ranks per (course, type)**: `course_preferences.section_type` (blank = every type). A3 eligibility and $w^C_{p,c,k}$ (A9, Stage A objective, metrics, integrated model) are now per (c, k); A3 slacks/violations name the type.
- **`scheduler convert-legacy`** (SPEC §8.1): Qualtrics survey + wide Excel files → §8 CSVs plus `review.csv` (comments, name matches, duplicate/unmatched/missing responses). `--add-offering COURSE:TYPE:N:CAP` for sections missing from `courses.xlsx` (Fall 2026 recitations: MATH161 R 8×57, MATH162 R 15×57, MATH263 R 1×60, MATH273 R 2×90). Real output only under `data/private/`; `--anonymize` (hash-ordered `P01..`, no names, e-mails or comments) for `data/examples/`.
- `data/examples/medium`: the anonymized Fall 2026 instance (26 professors, 74 sections, 5 rooms, 15 patterns); fast read/diagnostics tests, slow full-pipeline test.
- Fix: blank cells in optional input columns now fall back to the column default (they used to fail validation, e.g. `schedule_style`).
- Duplicate-rank warnings are grouped into one finding per professor.

## Run folders (L9, 2026-10-19)
- SPEC L9 (new): every solve writes to its own `runs/<YYYY-MM-DD_HH-MM-SS>_<instance>/` folder (suffix `-2`, `-3`, ... on collisions) with `runs/latest` pointing at the newest; `--runs-dir` changes the parent, `--out` still writes to an exact folder.
- `scheduler run <instance>`: check → Stage A → Stage B in one step; `--assignments` skips Stage A and records which run the hand-off came from.
- Each folder gets `run.json` (command, times, status, instance hash, config, git commit/dirty, version, per-stage stats), `config.yaml` (resolved config), `log.txt` (console output) and, for `run`, `check.txt`.
- `assign`, `timetable`, `report`, `alternatives`, `repair` default to a new run folder instead of `out/`. `runs/` is git-ignored.

## Fixes (2026-10-19)
- Hand-off rows naming an unknown professor were accepted silently by `check`, `validate` and Stage B. Now an L1 `unknown_id` error and an A1 validator error (`TBA-*` placeholders still allowed).
- A2 validator summed the hand-off's own `units` column, so a hand-edited value could hide an overload; it now uses the offering units $u_{c,k}$ like the model. Hand-off rows whose capacity/units differ from the offerings get an L1 `assignment_mismatch` warning (the offerings are what Stage B uses).
- Malformed `solution.json` entries (bad `source`, `section_type`, missing keys, invalid JSON) crashed with a traceback; they are now row-level `InputError`s.
- CLI: missing files, bad YAML and invalid config give a one-line `Error: ...` and exit code 2 instead of a traceback.
- CLI no longer claims to have written `timetable.html` for a solution without placements.
