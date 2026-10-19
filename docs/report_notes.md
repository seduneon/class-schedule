# Experiment notes

Reproduce with `uv run python experiments/run_all.py` (5 seeds) or `--quick` (2 seeds).
Results land in `experiments/results/` (CSV + PNG; git-ignored). Instances come from the
seeded generator (`scheduler.generate`, L8); default config, 1 solver thread, CBC.

The numbers below are from a **quick run (seeds 0–1)** on 2026-10-14 and are only a
sanity check; rerun with all seeds before quoting them in the report.

## Scaling (`scaling.csv`)
Professors = courses = n; about 2 sections per course.

| n | sections | Stage A (s) | Stage B (s) |
|---|---|---|---|
| 5 | 9–10 | 0.1–0.2 | 0.7 |
| 10 | 17–18 | 0.1–10.3 | 1.2–1.8 |
| 15 | 31 | 0.4–0.5 | 3.3–5.6 |
| 20 | 41–42 | 0.5–1.0 | 3.6–8.0 |
| 30 | 58–60 | 0.8–1.7 | 6.9–9.6 |

All runs optimal at every level. Stage B dominates; one Stage A outlier (10 s, n = 10,
seed 0) comes from proving optimality of the fractional level-3 objective.

## Ablations (`ablation.csv`)
Each should-rule switched off; violations counted by the validator under the default config.
With the rule on, every run has 0 violations. Switching off B5, B7, B8 or B9 produced
1–2 violations on at least one seed; A5, A6, A8, A9, B6, B12 did not bind on these
small instances (they need tighter instances to show an effect).

## Weight strategies (`weights.csv`)
`top_1` maximizes first choices (33–38 %) but has the worst minimum satisfaction and
mean rank; `linear` gives the best mean rank / minimum satisfaction balance.
Exponential sits in between.

## Fairness trade-off (`fairness.csv`)
Raising lambda from 0 to 4 raised the minimum course satisfaction (0.13 -> 0.17 and
0.19 -> 0.30) at a small cost in total course satisfaction on seed 0 (2.68 -> 2.59);
on seed 1 the total even rose (3.38 -> 3.42): level 3 also contains the A5 multi-section
bonus, so at lambda = 0 the solver traded course satisfaction for that bonus.

## Decomposition gap (L7, `decomposition.csv`)
Must-rules only; both approaches scored with the integrated level-3 proxy
(course + time satisfaction, both normalized by L_max). Quick run, seeds 0–1:

| n | sections | gap (integrated − two-stage) / integrated | time integrated / two-stage (s) |
|---|---|---|---|
| 4 | 8–9 | 0 % | 1.0 / 0.4 |
| 6 | 10–12 | 0.2–1.0 % | 1.3–2.0 / 0.6–0.7 |
| 8 | 13–15 | 0.8–3.1 % | 2.1–3.3 / 0.5–0.6 |

Every section was covered and scheduled by both. The two-stage decomposition loses at
most about 3 % of the proxy objective here while solving 3–5× faster; the integrated
model grows quickly (one binary per professor × section × pattern × room).
