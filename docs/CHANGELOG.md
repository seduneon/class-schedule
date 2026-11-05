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

## No-recitation data + hard-violation count (2026-10-19)
- `data/examples/medium_no_recitations` (and the git-ignored `data/private/fall2026_no_recitations`): copies without the 26 recitation sections, to test whether the room shortage comes from recitations. Switch by passing the other folder; no new flag.
- L9: `run.json` records validator counts per stage (`violations: {error, warning}`) and `hard_violations` (errors of the last solved stage; `null` if none). `scheduler run` ends with a one-line `Result:` summary.
- Fall 2026 comparison: with recitations, 8 hard violations (3 sections without a professor, 5 MATH162 recitations without a room/time); without recitations, 0 hard violations and every lecture is covered, at the cost of more underloaded professors (A2 warnings).

## Fixes (2026-10-20)
- A pre-assignment above a professor's maximum load made Stage A infeasible while `check` reported "No data problems found". New L1 finding `pre_exceeds_caps` (SPEC §7 L1): pre-assignments vs hard caps A2 (max load), A8 ($\alpha_p$), A5 (one section per course, $\mu_p=-1$), A6 (max preps); error if A4 is hard, warning if soft.
- CLI printed "Validator: all checks passed" for a stage without a solution; it now says nothing was validated.

## Decisions from the previous-capstone comparison (2026-10-21, SPEC §14 D6–D10)
- **A10 — Top-k course preference** (new, SPEC §5.2, default `soft`, `max_rank: 5`, weight 1, level 2): each section taught with a course rank above $K$, `cannot` or unranked is a slack $e_{p,c,k} \ge n_{p,c,k}$; `hard` filters those variables out. Pre-assignments and pins are exempt. Replaces the old capstone's hard top-5 cutoff without giving up coverage. Validator check, ablation pair (soft and hard) and unit tests in `test_a10_top_k.py`; the A9 ablation test switches A10 off (its instance relies on unranked courses).
- Rank→weight strategy stays `linear` (D7); no truncated-linear strategy.
- Legacy converter: `MWForTR` is ignored (D9); survey Q3 alone sets `day_families` and `day_family_mixing`. `MWForTR = 1` without a Q3 answer adds a `mwfortr` review row. `data/examples/medium*` regenerated: 15 professors go from `forbid` to their Q3 answer.
- Priority stays a single $\pi_p$ for courses and times (D6).
- SPEC §12: the golden tiny example is *modeled on* the old report's example, not taken from it (D10); the thesis example contradicts itself.
- A10 soft penalty now scales with the distance past $K$: weight × $(\rho - K)/(m_p - K)$ per section, 1 for `cannot`/unranked (`preferences.top_k_distance`). On `medium` the count-only version gave one professor a course ranked 18th; at most 1 per section, so A2 underload (weight 10) still comes first.

## Day families are a rule (2026-10-31, SPEC D11)
Supervisor feedback on the Fall 2026 report: six professors who answered "Tuesdays and Thursday only" (survey Q3) were given one MWF section, because B13 was soft and Q3 answers 1-2 mapped to `allow` mixing.
- **B13** default `hard` (priority `must`). Survey Q3 answers 1-3 now map to `day_family_mixing = forbid`; only "I am OK teaching every day" (chosen by nobody) allows mixing. `data/examples/medium*` and the private instance regenerated (only `day_family_mixing` changes, 23 professors).
- **A8** extended for B13 hard, so Stage A only hands Stage B what fits: $\alpha_p$ uses only the professor's families (one family at a time unless mixing is allowed); per family $f$ and suitable-room set $R^*$, sections of professors pinned to $f$ ≤ (room, pattern) slots of $f$ in $R^*$; per hard conflict group, $\sum_c \max_p$ (sections of $c$ by a professor pinned to $f$) ≤ non-overlapping patterns of $f$. Validator checks, builder, ablation pairs and unit tests in `test_a08_timetable_capacity.py`.
- L1 `family_capacity` warning: minimum loads of professors pinned to a family vs that family's slots.
- Fall 2026 (no recitations): all 48 sections scheduled, no professor mixes MWF and TR or teaches off-family; Stage A soft cost unchanged (14.86). Trade-off: one `spread` professor now has a back-to-back pair (B9).
- Without the A8 extension, B13 hard left 6 sections unscheduled (28 TR-only sections for 26 TR slots; 3 need the 200-seat room, which has 2 TR slots; the 300-level TR courses needed 9 of 6 TR patterns).

## Spring 2027 data: fixes file, Stage A without Stage B data (2026-11-05, SPEC D12-D14)
The supervisor's Spring 2027 files differ from the Fall ones: `courses.xlsx` has one row per course (`Section_number` = number of sections), the survey export has its header one row higher and Q1 labels without tabs, MATH 818 sits in a survey column without a header, and there is no `time_room.xlsx`. The old converter silently produced 1 section per course and no preferences at all.
- **Converter (SPEC §8.1.1, D12):** raw files are never edited. A closed list of layout tolerances: header row found by an anchor in the first 5 rows (T1), columns by name (T2), whitespace normalized and Q1 labels split into code and title by tab or spaces (T3), blank rows skipped (T4). A column with data but no header is now an error (it used to be skipped: that is how MATH 818 got lost).
- **Fixes file (SPEC §8.1.2, `--fixes`):** `courses_format` (`per_section` / `per_course`), `course_aliases`, `survey_columns` (Excel column letter -> Q1 course), `time_patterns_from_survey`. Every applied fix is a `fix` review row; stale fixes are errors. A per-course file read per section, or a repeated row in a per-course file, is an error.
- Survey previews (`DistributionChannel = preview`) are skipped with a review row; Q1 courses that are not offered, and offered courses without a Q1 column, get `survey_course` review rows; a missing `time_room.xlsx` gets a `missing_table` review row.
- **D14:** `MATH 702/682` -> `MATH702`, title `Applied Functional Analysis (MATH 702/682)`. The Fall 2026 conversion is unchanged (byte-identical CSVs).
- `write_legacy` removes table CSVs left over from an earlier conversion into the same folder, so an absent table stays absent.
- **Required tables per stage (SPEC §8, D13):** Stage A needs `professors` and `offerings`; Stage B also `time_patterns` and `rooms`. `Instance.missing_tables` records absent tables (an empty table is present); `write_instance` keeps them absent.
- **Not checked (SPEC §4, D13):** constraint parts whose inputs are absent are not built or validated and are listed as L1 `not_checked` warnings, in `run.json` (`stages.A.not_checked`) and the report. **A8** is split into per-professor alpha_p (needs `time_patterns`), day-family rooms kappa_f (`time_patterns`, `rooms`) and day-family conflict groups (`time_patterns`); before, an absent `time_patterns` would have meant alpha_p = 0 and no sections for anyone. L1 checks needing absent tables are skipped and listed; references to absent tables (time preferences, room availability, Stage B pins) are not integrity errors.
- **`run` (L9):** without Stage B tables it stops after Stage A with status `ok`, writes `report.xlsx`, and records `stages.B = {status: skipped_no_data, missing_tables}`. `timetable` (and `run --assignments`) without Stage B tables is a user error (exit 2).
- Spring 2027 Stage A (default config): all 48 sections covered, no hard violations; 9 units of minimum load cannot be met (55 units of load for 46 offered), so 5 professors are underloaded (A2 soft); two sections outside the professor's top 5 (A10).
- L1 `duplicate_rank` for time preferences now counts per professor and day family (SPEC §7 L1): the survey ranks MWF and TR slots in separate lists, so every respondent used to get a false warning. Without `time_patterns` the check is reported as `not_checked`.

## Result line names parts not checked (2026-11-05, SPEC §4, L9)
The Spring 2027 Stage A run ended with "Result: no hard violations." while all three A8 parts were not checked; with survey time patterns (`time_patterns_from_survey: true`) the same assignment broke A8 day-family conflict-group capacity (7 level-400 courses on TR-only professors, 6 TR patterns).
- `run`'s final line now says the count covers only the checked rules and names every part not checked, e.g. `Result: no hard violations among checked rules; not checked: A8 day-family room capacity kappa_f (no rooms table).`, shown in yellow. With nothing unchecked it is unchanged.

## Repository layout (2026-11-06, SPEC §10)
- SPEC §10 tree updated to what is tracked (`.github/`, `data/examples/medium_no_recitations/`, `tests/test_architecture.py`) and now defines the git-ignored real-data layout: `data/private/<term>/{raw/<date>/, fixes.yaml, instance/, runs/, experiments/<name>/, deliveries/<date>/, verify/}` and `data/private/reference/`. Real-data runs use `--runs-dir data/private/<term>/runs`.
- New `tests/test_repo_layout.py`: tracked files stay inside the tree, only `data/examples/` is tracked under `data/`, and no `.xlsx`/`.xls`/`.zip`/`.pdf` is tracked. `.gitignore` ignores those types everywhere.
- `docs/PENDING_DECISIONS.md` removed: every item was resolved on 2026-10-21 and is recorded in SPEC §14 (D6–D10).
- README and CLAUDE.md describe the layout; README commands use the new paths.

## Delivery verification (2026-11-06, SPEC §8.1.3, D15)
- New SPEC §8.1.3 and D15: before anything goes to the supervisor, independent scripts (never importing `scheduler`, re-reading the raw Excel) run V1 conversion, V2 hard rules incl. A8 per professor and A8 conflict groups, V3 `report.xlsx` vs `assignments.csv`, V4 `run.json` provenance; the outcome goes to `VERIFICATION_<date>.md`, what is sent to `deliveries/<date>/`. Not-checked parts are never reported as passed.
- CLAUDE.md: the delivery checklist (clean main, survey time patterns when `time_room.xlsx` is missing, `verify_all.py`, read the `Result:` line, record and archive). README: the command.
- Why: the first Spring 2027 result broke A8 (7 level-400 courses on TR-only professors, 6 TR slots) and nobody noticed, because the time checks were skipped and the independent scripts covered A1–A4 only. The scripts themselves are term-specific and live in `data/private/<term>/verify/`.
