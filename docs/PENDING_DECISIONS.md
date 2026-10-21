# Pending decisions (from the comparison with the previous capstone, 2026-10-20)

**Resolved 2026-10-21** (SPEC §14 D6–D10): P1 → soft A10 (`max_rank: 5`), linear weights kept; P2 → `MWForTR` ignored, Q3 decides; P3 → single $\pi_p$; P4 → SPEC §12 reworded. README gaps fixed the same day.

Source: the 2025 capstone's `prof_course.py` and thesis draft (git-ignored, under
`refall2026mathcourselist/`). Each item needs a decision first. Then change SPEC → tests → code,
following SPEC §11, and record the decision in SPEC §14.

| # | Topic | Previous capstone | Ours now | Options | Changes if adopted |
|---|---|---|---|---|---|
| P1 | **Top-5 eligibility** (largest drift) | Course ranks > 5 get weight 0 and are then forbidden (hard). The survey tells professors "most assignments typically within your top 5". Weight $(6-r)/15$, which is steep. | Respondents rank all 33 items, so every ranked course is eligible and A3 forbids almost nothing. Linear weight $(34-r)/33$ is flat (rank 1 = 1.0, rank 5 = 0.88). Stage A on `medium`: 10 of 71 sections go to courses ranked 6–14. | (a) keep it (coverage first); (b) new option `preferences.max_rank: k` (ranks > k treated as unranked, so forbidden under `forbid`); (c) the same as a soft A3 penalty; plus a truncated-linear weight strategy $w=(k+1-\rho)/k$ for $\rho\le k$. | SPEC §3.4, A3 (§5.2), §9; `preferences`, A3 builder and check, config, tests; re-run `medium`. |
| P2 | **`MWForTR` meaning** | Set for every professor: 1 = MWF only, 0 = TR only (−100 per placement on the other days). | 1 = don't mix MWF and TR (`day_family_mixing = forbid`); 0 = no restriction (SPEC §8.1). | (a) keep it; (b) old meaning: 1 → `day_families = MWF`, 0 → `TR`; (c) ignore the column, since survey Q3 now asks professors directly. Ask the chair what the column means in the Fall 2026 file. | SPEC §8.1 table; `io/legacy.py` (~line 260); legacy tests; regenerate `data/examples/medium*`. |
| P3 | **Separate course and time priority** | `course_points` scales course weights and `time_points` scales time weights independently; the thesis example uses this (time points 130). | A single $\pi_p$ = `course_points/100`; a difference only adds a `review.csv` row (D6 = both). | (a) keep a single $\pi_p$; (b) split it into `priority_course` and `priority_time` (default: `priority`). | SPEC §3.3, §5.3, §6.3, §8, §8.1, D6; schemas, domain, both objectives, A9/B12, converter, tests. |
| P4 | **Golden tiny example** | Thesis §3.4: loads 1/1/2, A pre-assigned MATH161 1L, priorities 100/100/110 (time 100/130/100), multi-section −1/0/1, capacities 50/30/60/40, rooms 7.101 (45, MWF) and 7.102 (70, TR). | Same names and courses but different data. SPEC §12 claims it comes from the old report. | (a) rebuild `data/examples/tiny` from the thesis tables and recompute the golden values; (b) reword §12. | `data/examples/tiny`, `test_golden_tiny.py`, or one SPEC line. |

Not decisions, but README gaps found on the same day: the README does not mention the commands `report`, `generate`
or `experiment`, or the inputs `pins` and `section_links`, and marks `course_preferences` and `time_preferences`
as required although the reader does not require them.
