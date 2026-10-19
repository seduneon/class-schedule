# Class Scheduling Optimizer — Specification

> **This is the source of truth for the project.** Code, tests and config follow this document.
> When a rule changes, change it here first, then implement (see §11 *Change workflow*).

Capstone project: *Class Scheduling Automation Using Integer Programming: Aligning Professors, Courses, and Time Slots* — Department of Mathematics, Nazarbayev University.

---

## 1. Goals and non-goals

### Goals
1. Assign professors to course sections (Stage A), then sections to time patterns and rooms (Stage B), using mixed-integer linear programming.
2. Every rule is an explicit, ID'd constraint that can be switched `hard` / `soft` / `off` from config without code changes.
3. Correctness is verifiable: an independent validator (no solver involved) checks every solution, including human-edited ones.
4. Coverage always beats preferences: lexicographic objectives, no hand-tuned "−100" penalties.
5. Clear diagnostics when the data cannot be satisfied, in words a department chair understands.
6. Human-in-the-loop: the chair can edit Stage A output and pin any decision before Stage B.
7. Reproducible experiments for the capstone report (ablations, scaling, decomposition gap).

### Non-goals (for now)
- Student-level enrollment optimization (we use conflict groups as a proxy).
- A web UI (CLI + Excel/HTML reports only; keep the core library UI-agnostic).
- Multi-department or campus-wide room allocation.

---

## 2. Design principles

- **Build the problem from first principles.** The earlier capstone is a source of requirements and pitfalls only; do not port its code.
- **Filter, don't penalize.** If a (section, time, room) combination is impossible (room too small, wrong room type, professor unavailable, blocked slot), never create the variable. No big-M for these.
- **Exact time logic.** Time conflicts come from actual overlap of meetings (day + interval), never from matching slot labels.
- **No-overlap via cliques.** All "at most one at a time" rules are written per maximal clique of overlapping time patterns.
- **Aggregate before you enumerate.** Stage A decides *how many* sections of each course a professor teaches (integer counts); section labels are attached afterwards. This removes symmetry between identical sections.
- **Spec ↔ code ↔ test sync.** Every constraint ID in §5–§6 has exactly one model builder, one validator check and at least one test.

---

## 3. Data model

### 3.1 Sets

| Symbol | Meaning |
|---|---|
| $P$ | professors |
| $C$ | courses (e.g. MATH 161) |
| $K$ | section types: `L` (lecture), `R` (recitation), `LAB` |
| $S$ | sections; each $s$ has course $c(s)$, type $k(s)$, enrollment cap $\text{cap}_s$, units $u_s$, required room type, optional parent lecture |
| $S_p$ | sections assigned to professor $p$ (Stage B input) |
| $R$ | rooms, with $\text{cap}_r$, building, room type |
| $A_r \subseteq T$ | patterns at which room $r$ may be used: the patterns listed for $r$ in `room_availability`, or all of $T$ if $r$ is not listed |
| $T$ | time patterns; each $t$ is a set of meetings $(\text{day}, \text{start}, \text{end})$, e.g. MWF 09:00–09:50, plus the section types it may host |
| $D$ | teaching days (Mon–Fri, configurable) |
| $f(t)$ | day family of pattern $t$: its set of meeting days written as a string, e.g. `MWF`, `TR` |
| $G$ | conflict groups: sets of courses students take together, which must not overlap |

### 3.2 Derived structures (computed in `scheduler.time`)

- **Overlap:** $t \sim t'$ iff some meeting of $t$ and some meeting of $t'$ are on the same day and their intervals intersect, after extending each end by `config.time.buffer_minutes`.
- **Overlap cliques $\mathcal{K}$:** maximal sets of pairwise-overlapping patterns. Because meetings are intervals, for each (day, meeting start point $\tau$), the set of patterns with a meeting active at $\tau$ is a clique; deduplicate and keep maximal ones. Every pair of overlapping patterns must appear together in at least one clique (property-tested).
- **Adjacency:** $t \to t'$ is an adjacent pair if they share a day $d$ and on $d$ the start of $t'$ minus the end of $t$ is in $[0, \text{config.time.adjacency\_gap\_minutes}]$.
- **Feasible triples $\mathcal{F}$:** $(s, t, r)$ such that $\text{cap}_r \ge \text{cap}_s$, room type matches, $t \in A_r$ (room availability), $t$ allows type $k(s)$, $t$ is not blocked, the professor of $s$ is not unavailable at any meeting of $t$, and pins (L4) are respected.

### 3.3 Parameters

| Symbol | Source | Meaning |
|---|---|---|
| $[\underline{L}_p, \overline{L}_p]$ | professors | teaching load range in units |
| $\pi_p$ | professors | priority points (default 1.0) |
| $\text{preps}_p$ | professors | max distinct courses (optional) |
| $\text{days}_p$ | professors | max teaching days per week (optional) |
| $\mu_p \in \{-1,0,1\}$ | professors | multi-section preference: dislikes / indifferent / likes |
| $\sigma_p \in \{\text{compact}, \text{spread}, \text{none}\}$ | professors | back-to-back preference |
| $\Phi_p$ | professors | preferred day families (optional; empty = any), e.g. $\{\text{MWF}\}$ (B13) |
| $\chi_p \in \{\text{allow}, \text{avoid}, \text{forbid}\}$ | professors | mixing day families (B13), default `allow` |
| $N_{c,k}$ | offerings | number of sections of course $c$, type $k$ |
| $u_{c,k}$ | offerings | units per section (default L=1, R=0.5, LAB=0.5) |
| $\rho^{C}_{p,c,k}$, $\rho^{T}_{p,t}$ | preferences | ranks, 1 = best; a course rank without a section type applies to every type of the course |
| $w^{C}_{p,c,k}$, $w^{T}_{p,t}$ | derived | weights in $[0,1]$, see §3.4 |
| $\text{pre}_{p,c,k}$ | pre_assignments | pre-assigned section counts |

### 3.4 Rank → weight conversion (`scheduler.preferences`)

Strategy chosen in config (`preferences.strategy`). For a professor with $m$ ranked items and an item ranked $\rho$:

- `linear`: $w = (m - \rho + 1)/m$
- `exponential`: $w = \beta^{\rho - 1}$, with $\beta \in (0,1)$ from config
- `top_k`: $w = 1$ if $\rho \le k$, else 0

Unranked items get weight `preferences.unranked_weight` (default 0).

Course preferences may name a section type (`course_preferences.section_type`). The rank of $(p,c,k)$ is the row for $(p,c,k)$ if present, else the row for $(p,c)$ without a type, else unranked. The items counted in $m$ are the professor's preference rows; the weights $w^C_{p,c,k}$ are then computed per offered $(c,k)$ and normalized over them. Weights are **normalized per professor** so their maximum is 1. This way, ranking many items does not buy a professor extra influence. Priority $\pi_p$ multiplies a professor's satisfaction terms in the objective.

---

## 4. Constraint index

`Status`: `planned` | `implemented`. `Default` is the mode used in `configs/default.yaml`.
The test `tests/test_spec_sync.py` parses this table: every `implemented` row must have a registered builder, a validator check and tests.

| ID | Name | Stage | Priority | Default | Status |
|---|---|---|---|---|---|
| A1 | Section coverage | A | must | hard* | implemented |
| A2 | Teaching load range | A | must | soft | implemented |
| A3 | Eligibility | A | must | hard | implemented |
| A4 | Pre-assignments | A | must | hard | implemented |
| A5 | Multi-section preference | A | should | soft | implemented |
| A6 | Max distinct preparations | A | should | soft | implemented |
| A7 | Lecture–recitation staffing | A | should | off | implemented |
| A8 | Timetable capacity pre-check | A | should | hard | implemented |
| A9 | Course satisfaction fairness | A | should | soft | implemented |
| B1 | Section scheduled once | B | must | hard* | implemented |
| B2 | No room overlap | B | must | hard | implemented |
| B3 | No professor overlap | B | must | hard | implemented |
| B4 | Unavailability and blocked slots | B | must | hard | implemented |
| B5 | Conflict groups | B | must | hard | implemented |
| B6 | Spread sections of a course | B | should | soft | implemented |
| B7 | Recitation–lecture relation | B | should | soft | implemented |
| B8 | Max teaching days | B | should | soft | implemented |
| B9 | Back-to-back preference | B | should | soft | implemented |
| B10 | Max consecutive teaching | B | could | off | implemented |
| B11 | Room stability | B | could | off | implemented |
| B12 | Time satisfaction fairness | B | should | soft | implemented |
| B13 | Day-family preference | B | should | soft | implemented |

\* A1 and B1 always carry a coverage slack minimized at objective level 1. "hard" here means *no other objective may trade against coverage*. The model stays feasible and reports what could not be covered.

**Modes:** `hard` = enforced, no slack. `soft` = slack variable added and penalized at the level given in config. `off` = not built and not checked.

---

## 5. Stage A — Assignment

### 5.1 Variables

- $n_{p,c,k} \in \mathbb{Z}_{\ge 0}$, upper bound $N_{c,k}$: sections of $(c,k)$ taught by $p$. Created only for eligible $(p,c,k)$ (A3).
- $z_{p,c} \in \{0,1\}$: $p$ teaches course $c$ at all. Always linked: $z_{p,c} \le \sum_k n_{p,c,k} \le \left(\sum_k N_{c,k}\right) z_{p,c}$.
- Slacks are introduced per constraint below, all $\ge 0$.

### 5.2 Constraints

**A1 — Section coverage**
$\sum_{p} n_{p,c,k} + a_{c,k} = N_{c,k} \quad \forall c,k$
The slack $a_{c,k}$ (uncovered sections) is minimized at level 1.

**A2 — Teaching load range**
$\underline{L}_p - \delta^-_p \le \sum_{c,k} u_{c,k}\, n_{p,c,k} \le \overline{L}_p + \delta^+_p \quad \forall p$
In hard mode $\delta^\pm = 0$. In soft mode the default is underload penalized at level 2 and overload forbidden (`allow_overload: false`).

**A3 — Eligibility**
No variable exists for $(p,c,k)$ if the rank of $(p,c,k)$ (§3.4) is "cannot teach", or if $(p,c,k)$ is unranked and `preferences.unranked_policy = forbid`. In soft mode each section taught while ineligible is a slack $e_{p,c,k} \ge n_{p,c,k}$ penalized at level 2. With `allow_low`, unranked courses get variables with weight `unranked_weight`.

**A4 — Pre-assignments**
$n_{p,c,k} \ge \text{pre}_{p,c,k}$. A pre-assignment overrides A3 eligibility (with a warning in diagnostics). Specific section labels in pre-assignments are preserved when labels are attached (§5.4).

**A5 — Multi-section preference**
- If $\mu_p = -1$: $\sum_k n_{p,c,k} \le 1 + e_{p,c}$, with excess $e_{p,c}$ penalized (soft) or forced to 0 (hard).
- If $\mu_p = +1$: an objective bonus of `bonus_per_extra` for each section beyond the first in the same course. Linearize with $x_{p,c} \le \sum_k n_{p,c,k} - z_{p,c}$, $x \ge 0$, and reward $x$.

**A6 — Max distinct preparations**
$\sum_c z_{p,c} \le \text{preps}_p + v_p$, only for professors with $\text{preps}_p$ set.

**A7 — Lecture–recitation staffing**
Config option `recitations.staffing`:
- `faculty`: recitations are assigned like lectures (default units 0.5).
- `same_as_lecture`: whoever teaches lecture sections of $c$ also takes $\lceil N_{c,R} \cdot (\text{their lecture share}) \rceil$ recitations. Linearize with integer shares.
- `external`: recitations are excluded from Stage A and staffed outside the model; they still go to Stage B with a placeholder instructor (`TBA-<course>`), so only room and conflict rules apply.

**A8 — Timetable capacity pre-check**
Let $\alpha_p$ be the maximum number of pairwise non-overlapping time patterns available to $p$. Compute it once with a small independent-set MIP on the overlap graph (cached). Then
$\sum_{c,k} n_{p,c,k} \le \alpha_p$.
This prevents Stage A from producing assignments Stage B cannot schedule.

**A9 — Course satisfaction fairness**
Normalized satisfaction $\text{sat}^C_p = \frac{1}{\overline{L}_p}\sum_{c,k} u_{c,k}\, w^C_{p,c,k}\, n_{p,c,k}$.
Add $m^C \le \text{sat}^C_p\ \forall p$ (professors with load > 0) and reward $\lambda^C m^C$.

### 5.3 Objective (lexicographic)

| Level | Sense | Expression |
|---|---|---|
| 1 | min | $\sum a_{c,k}$ (uncovered sections) |
| 2 | min | $\sum$ (configured weight × soft slack) for A2, A5, A6 |
| 3 | max | $\sum_p \pi_p\, \text{sat}^C_p + \lambda^C m^C + \text{A5 bonus}$ |

Lexicographic solve (`scheduler.solve.lexicographic`): optimize level $i$, then add the constraint "level-$i$ expression is within `tolerance_i` of its optimum" and continue. Default tolerance is 0 for level 1 and 0 for level 2.

### 5.4 Post-processing

Expand counts into labeled sections (1L, 2L, … per course and type). Pre-assigned labels go to their professors first. The remaining labels are assigned deterministically: by professor ID, then by label. If sections of a course have different caps, the larger caps go to professors in ID order. Make this rule explicit in output and editable by the chair.

Output: `assignments.xlsx/csv` with columns `professor_id, course_id, section_type, section_label, capacity, units, source` (`pre`, `model`, `manual`). This is the editable hand-off to Stage B.

---

## 6. Stage B — Timetabling

### 6.1 Variables

- $y_{s,t,r} \in \{0,1\}$ for $(s,t,r) \in \mathcal{F}$ only.
- Helper (expression, not a variable): $\text{busy}_{p,t} = \sum_{s \in S_p}\sum_r y_{s,t,r}$.

### 6.2 Constraints

**B1 — Section scheduled once**
$\sum_{t,r} y_{s,t,r} + b_s = 1 \quad \forall s$. The slack $b_s$ (unscheduled) is minimized at level 1.

**B2 — No room overlap**
$\sum_s \sum_{t \in Q} y_{s,t,r} \le 1 \quad \forall r,\ \forall Q \in \mathcal{K}$

**B3 — No professor overlap**
$\sum_{t \in Q} \text{busy}_{p,t} \le 1 \quad \forall p,\ \forall Q \in \mathcal{K}$
Placeholder instructors (`TBA-*`) are exempt.

**B4 — Unavailability and blocked slots**
Enforced through $\mathcal{F}$: the variables are never created. The validator still checks it explicitly, because human edits can violate it. In soft mode, "unavailable" becomes "strongly disliked": variables are created and penalized at level 2.
Room availability ($t \in A_r$) is physical: it is always filtered out of $\mathcal{F}$, in every mode, and the validator reports a placement with $t \notin A_r$ as a B4 error.

**B5 — Conflict groups**
For each group $g$ (config `hard` or `soft` per group), course $c \in g$, clique $Q$:
$h_{c,Q} \ge \sum_{t \in Q}\sum_r y_{s,t,r} \quad \forall s \in c$, with $h_{c,Q} \in \{0,1\}$
$\sum_{c \in g} h_{c,Q} \le 1 + o_{g,Q}$
Sections of the *same* course may overlap; different courses in a group may not. Only courses in some group get $h$ variables. Default groups: `level_300`, `level_400`, `graduate`, generated from course levels when `conflict_groups.auto_levels: true`, plus any groups from the input file (e.g. first-year core).

**B6 — Spread sections of a course**
For courses with $\ge 2$ sections of the same type: $\sum_{s \in c,k}\sum_{t\in Q}\sum_r y_{s,t,r} \le 1 + o^{6}_{c,k,Q}$, with $o^6$ penalized.

**B7 — Recitation–lecture relation**
For a recitation $s'$ linked to lecture $s$ (or every lecture of $c(s')$ if unlinked), and each clique $Q$:
$\sum_{t\in Q,r} (y_{s,t,r} + y_{s',t,r}) \le 1 + o^7$
Optional `recitation_after_first_lecture: true` additionally forbids patterns for $s'$ that start before the earliest weekly meeting of $s$. Linearize by pairwise exclusion of (lecture pattern, recitation pattern) combinations that violate the order.

**B8 — Max teaching days**
$\text{day}_{p,d} \ge \text{busy}_{p,t}\ \forall t$ meeting on $d$, with $\text{day}_{p,d} \in \{0,1\}$
$\sum_d \text{day}_{p,d} \le \text{days}_p + v^8_p$

**B9 — Back-to-back preference**
For each adjacent pair $(t,t')$:
- $\sigma_p = $ compact: $\beta_{p,t,t'} \le \text{busy}_{p,t}$, $\beta_{p,t,t'} \le \text{busy}_{p,t'}$, $\beta \in [0,1]$, rewarded at level 3.
- $\sigma_p = $ spread: $\text{busy}_{p,t} + \text{busy}_{p,t'} \le 1 + o^9_{p,t,t'}$, with $o^9$ penalized.

(This is linear; no absolute values needed.)

**B10 — Max consecutive teaching**
For each day and each window of $k+1$ consecutive adjacent patterns $t_1 \to \dots \to t_{k+1}$: $\sum_i \text{busy}_{p,t_i} \le k$, with $k$ = `max_consecutive`.

**B11 — Room stability**
$\gamma_{p,r} \ge y_{s,t,r}$ for each $s \in S_p$; minimize $\sum_r \gamma_{p,r}$ (number of rooms used per professor). Building-level variant via config.

**B12 — Time satisfaction fairness**
$\text{sat}^T_p = \frac{1}{|S_p|}\sum_{s\in S_p}\sum_{t,r} w^T_{p,t}\, y_{s,t,r}$
$m^T \le \text{sat}^T_p\ \forall p$; reward $\lambda^T m^T$.

**B13 — Day-family preference**
For professors with $\Phi_p$ set (placeholders exempt):
- Off-family sections: $\sum_{s \in S_p} \sum_{t:\, f(t) \notin \Phi_p} \sum_r y_{s,t,r} \le o^{13}_p$, with $o^{13}_p$ penalized. In hard mode those triples are removed from $\mathcal{F}$ instead (filter, never big-M).
- Mixing, for professors with $\chi_p \ne \text{allow}$: $\phi_{p,f} \ge \text{busy}_{p,t}$ for every $t$ with $f(t) = f$, $\phi_{p,f} \in \{0,1\}$, and $\sum_f \phi_{p,f} \le 1 + q^{13}_p$. The slack $q^{13}_p$ exists only when $\chi_p = \text{avoid}$ and the mode is soft; $\chi_p = \text{forbid}$ is always hard.

Both slacks are penalized with the B13 weight at level 2. The validator counts off-family sections and the number of families used beyond one.

### 6.3 Objective (lexicographic)

| Level | Sense | Expression |
|---|---|---|
| 1 | min | $\sum_s b_s$ (unscheduled sections) |
| 2 | min | $\sum$ (weight × soft slack) for B4–B11 and B13 in soft mode |
| 3 | max | $\sum_p \pi_p\, \text{sat}^T_p + \lambda^T m^T + \text{B9 compact reward} - \text{B11 room count}$ |

---

## 7. Cross-cutting logic

**L1 — Pre-solve diagnostics (must)**
Runs before model building. Returns structured findings (`severity`, `code`, `message`, `entities`), which the CLI prints in plain language. Checks:
- Total load capacity vs total section units.
- Per $(c,k)$: number of eligible professors and their combined free capacity vs $N_{c,k}$.
- Per section: at least one room large enough and of the right type.
- Per professor: $\alpha_p$ (A8) vs assigned or minimum load.
- Per conflict group: number of courses vs number of disjoint time cliques.
- Data integrity: unknown IDs, duplicate ranks, pre-assignments of non-offered courses, overlapping blocked slots.

After solving, report every nonzero slack with the entities involved ("MATH 161 L: 1 section uncovered; eligible professors all at max load: Prof 3, Prof 9").

**L2 — Independent validator (must)**
`scheduler.validation` checks a solution against an instance and config using plain Python only (no PuLP imports — enforced by a test). It has one check function per constraint ID, registered by ID, and returns `Violation(id, severity, message, entities)`. Hard-mode violations are errors; soft-mode ones are reported with their size. It runs automatically after every solve and on any user-supplied (edited) file via `scheduler validate`.

**L3 — Alternative solutions (should)**
After an optimal solution, generate up to $N$ alternatives:
- Stage A uses no-good cuts on $z$: $\sum_{z^*_{p,c}=1}(1 - z_{p,c}) + \sum_{z^*_{p,c}=0} z_{p,c} \ge d$.
- Stage B uses the same on $y$ restricted to $(s,t)$: the cut is on time choices, room changes do not count. Define $\tilde y_{s,t} = \sum_r y_{s,t,r}$.

Each alternative must keep level-1 optimality, and keep level-3 within `alternatives.optimality_gap` (default 2%). Output is a ranked list with a diff against the best solution.

**L4 — Pins and locks (must)**
- A pins file fixes Stage A decisions (`professor_id, course_id, section_type, count`) and Stage B decisions (`course_id, section_type, section_label, [pattern_id], [room_id]`; partial pins allowed).
- Pins are applied as variable fixings or by filtering $\mathcal{F}$.
- If a pin conflicts with the data, L1 reports it before solving.

**L5 — Repair mode (should)**
Input: previous solution + changed instance. An extra objective level is inserted right after coverage: minimize the number of changed decisions.
- Stage B: $\sum_{(s,t,r)\in \text{old}} (1 - y_{s,t,r})$.
- Stage A: changes in $z$.

**L6 — Reporting (must)**
- Excel workbook: timetable per professor, per room, per conflict group; assignment list; satisfaction table (rank received vs best possible per professor); violations and slacks; solver stats.
- Static HTML weekly grid for quick viewing.
- JSON solution file: the canonical machine format, used by `validate`, repair and experiments.

**L7 — Integrated mode (could)**
A single model with $y_{p,s,t,r}$ (or $n$ plus $y$ linked). Used only for experiments measuring the cost of the two-stage decomposition on small or medium instances.

**L8 — Instance generator (should)**
`scheduler.generate` creates synthetic instances with controllable size, tightness (load vs sections, rooms vs sections) and preference correlation. Used for property tests and scaling experiments. It is seeded and deterministic.

**L9 — Run folders (must)**
Every solve keeps its results in its own folder, so runs are never overwritten and can be reproduced and compared.
- Commands that write results (`run`, `assign`, `timetable`, `report`, `alternatives`, `repair`) write to a new folder `runs/<YYYY-MM-DD_HH-MM-SS>_<instance>/` when `--out` is not given. `<instance>` is the instance folder name (or the workbook name without extension). If the name is taken, `-2`, `-3`, … is appended. `--runs-dir` changes the parent folder. An explicit `--out` writes exactly there instead (with the same metadata files).
- `runs/latest` is a symlink to the newest run folder (skipped where symlinks are unsupported).
- `scheduler run <instance>` is the one-step pipeline: L1 check → Stage A → Stage B. With `--assignments FILE` it skips Stage A and uses the (possibly hand-edited) hand-off. L1 findings go to `check.txt` and do not stop the run (as in `assign` / `timetable`, the model reports what cannot be covered); a stage without a solution stops it with exit code 1, keeping what was written so far.
- Each run folder holds, besides the stage outputs (§5.4, L6): `run.json`, `config.yaml` (the resolved config actually used), `log.txt` (console output without colors); `run` also writes `check.txt` (L1 findings).
- `run.json` fields: `command`, `argv`, `started_at`, `finished_at` (local ISO 8601), `status` (`ok` / `failed`), `instance` (path) and `instance_sha256` (hash over the input files in sorted name order), `config` (path or `null` for built-in defaults), `assignments` (input hand-off path or `null`), `from_run` (name of the run folder the hand-off came from, if any), `scheduler_version`, `git_commit` and `git_dirty` (`null` outside a git checkout), and `stages`: per solved stage its status, objective levels and solver stats.
- `runs/` is git-ignored: runs on real data contain names.

---

## 8. Input formats

All inputs live in one folder, as CSV files or sheets of a single `.xlsx` with the same names. Every table is long-format. Validation uses pydantic models and gives row-level error messages.

| Table | Columns (required, *optional*) |
|---|---|
| `professors` | `professor_id, name, load_min, load_max`, *`priority, max_preps, max_days, multi_section_pref (-1/0/1), schedule_style (compact/spread/none), day_families (e.g. MWF;TR), day_family_mixing (allow/avoid/forbid)`* |
| `offerings` | `course_id, title, level, section_type, num_sections, capacity, units, room_type` |
| `rooms` | `room_id, building, capacity, room_type` |
| `room_availability` (optional) | `room_id, pattern_id`: a room listed here may only be used at its listed patterns ($A_r$) |
| `time_patterns` | `pattern_id, days (e.g. MWF), start (HH:MM), end (HH:MM), allowed_section_types (e.g. L;R)` |
| `course_preferences` | `professor_id, course_id, rank` (rank ≥ 1, or the literal `cannot`), *`section_type`* (blank = every type) |
| `time_preferences` | `professor_id, pattern_id, rank` (or `cannot`) |
| `unavailability` | `professor_id, day, start, end`, *`reason`* (a finer-grained alternative to `cannot` ranks) |
| `blocked_slots` | `day, start, end, reason` |
| `pre_assignments` | `professor_id, course_id, section_type, count`, *`section_label`* |
| `conflict_groups` | `group_id, course_id`, *`mode (hard/soft), weight`* |
| `pins` (optional) | see L4 |
| `section_links` (optional) | `course_id, recitation_label, lecture_label` |

Stage B additionally reads Stage A's `assignments` file (§5.4).

Provide a converter `scheduler convert-legacy` that turns the previous capstone's wide Excel files (one column per course and per time slot) into this format, if the legacy files are available.

### 8.1 Legacy converter (`scheduler convert-legacy`)

Input folder with `courses.xlsx`, `professors.xlsx`, `time_room.xlsx` and `preferences.xlsx` (the Qualtrics export). Output: a CSV folder in the format above, plus `review.csv` listing everything that needs a human decision (free-text comments, unmatched or duplicate responses, mismatches). Real data is written only under `data/private/`; `--anonymize` replaces names and IDs with `P01, P02, …`, drops e-mails and comments, and is the only way data goes to `data/examples/`.

| Legacy source | Target |
|---|---|
| `courses`: one row per section (`Course_code, Course_title, Section_number, Section_type, Capacity`) | `offerings`: one row per (course, type, capacity) with `num_sections`; `course_id` = code without spaces and without the cross-listing suffix (`MATH 571 (MATH 721)` → `MATH571`); `level` = first digit × 100; units from §3.3 defaults; `room_type = classroom` |
| `--add-offering COURSE:TYPE:N:CAP` (repeatable) | extra `offerings` rows for sections missing from `courses` (e.g. recitations) |
| `time_room`: one row per usable (days, time, room, cap) | `time_patterns` (distinct days+time; `allowed_section_types = L;R`), `rooms` (building = part of the room ID before the first `.`), `room_availability` (every listed pair) |
| `professors`: `load` | `load_min = load_max = load` |
| `professors`: `course_points`, `time_points` | `priority = course_points / 100` (a review row if they differ, D6) |
| `professors`: `MWForTR = 1` | `day_family_mixing = forbid` |
| `professors`: `course<i>, section<i>` | `pre_assignments` (type L, count 1, `section_label = <i>L`) |
| Survey Q1 (rank every course; columns whose question text mentions a recitation are type R) | `course_preferences`; lecture-column ranks get `section_type = L` when the course also has a recitation column, otherwise no type |
| Survey Q2 (Yes / No / No preference) | `multi_section_pref` = 1 / −1 / 0 |
| Survey Q3 (MWF only / TR only / either but not mixed / any day) | `day_families` = MWF / TR / MWF;TR / MWF;TR and `day_family_mixing` = allow / allow / avoid / allow (a `forbid` from `MWForTR` wins) |
| Survey Q4, Q5 (rank MWF slots, rank TR slots) | `time_preferences`, ranks as given in each list |
| Survey Q6 (Yes, one-hour break / comfortable back-to-back) | `schedule_style` = spread / none |
| Survey Q7 (comments) | `review.csv` only, never interpreted |

Responses are matched to professors by e-mail, then by last name (a review row either way if the match is not exact). If a professor answered twice, the latest `RecordedDate` wins (review row). Professors without a response get no preferences.

---

## 9. Configuration

`configs/default.yaml` is loaded into a pydantic `Config`. Each constraint is set by ID:

```yaml
solver:
  backend: cbc            # cbc | highs
  time_limit_s: 300
  threads: 4
  seed: 42
  mip_gap: 0.0
preferences:
  strategy: linear        # linear | exponential | top_k
  beta: 0.7
  top_k: 5
  unranked_policy: forbid # forbid | allow_low
  unranked_weight: 0.0
time:
  buffer_minutes: 0
  adjacency_gap_minutes: 15
  days: [Mon, Tue, Wed, Thu, Fri]
recitations:
  staffing: faculty       # faculty | same_as_lecture | external
conflict_groups:
  auto_levels: true
objective:
  lambda_course_fairness: 0.5
  lambda_time_fairness: 0.5
  tolerances: {level1: 0.0, level2: 0.0}
alternatives:
  count: 0
  min_difference: 3
  optimality_gap: 0.02
constraints:
  A1: {mode: hard}
  A2: {mode: soft, weight: 10, allow_overload: false}
  A5: {mode: soft, weight: 1, bonus_per_extra: 0.1}
  B5: {mode: hard}
  B9: {mode: soft, weight: 1, reward: 0.05}
  B10: {mode: off, max_consecutive: 3}
  B13: {mode: soft, weight: 5}
  # ... one entry per ID in §4
```

Unknown keys are an error. Unknown constraint IDs are an error.

---

## 10. Architecture

```
class-scheduler/
├── CLAUDE.md
├── README.md
├── pyproject.toml              # uv; ruff; mypy (strict); pytest
├── configs/default.yaml
├── docs/
│   ├── SPEC.md                 # this file
│   ├── CHANGELOG.md
│   └── report_notes.md         # experiment results for the capstone write-up
├── data/
│   ├── examples/tiny/          # hand-checkable instance (3 profs, 4 sections)
│   ├── examples/medium/        # anonymized realistic instance
│   └── private/                # real data — git-ignored
├── runs/                       # L9 run folders — git-ignored
├── src/scheduler/
│   ├── domain/                 # frozen dataclasses: Professor, Offering, Section, Room, TimePattern, Meeting, Instance, Assignment, Solution
│   ├── io/                     # readers (csv/xlsx → domain), schemas (pydantic), writers, legacy converter, run folders (L9)
│   ├── time/                   # parsing, overlap, cliques, adjacency, independent-set α_p
│   ├── preferences/            # rank → weight strategies
│   ├── config.py               # pydantic Config
│   ├── model/
│   │   ├── context.py          # ModelContext: pulp problem, variable registries, objective terms by level
│   │   ├── registry.py         # @constraint("A1") decorator, lookup by ID/stage
│   │   ├── stage_a/            # variables.py, objective.py, constraints/a01_coverage.py ...
│   │   └── stage_b/            # variables.py (builds 𝓕), objective.py, constraints/b01_once.py ...
│   ├── solve/
│   │   ├── backend.py          # thin adapter over PuLP solvers (CBC, HiGHS); status mapping; stats
│   │   ├── lexicographic.py
│   │   ├── alternatives.py     # L3
│   │   └── repair.py           # L5
│   ├── validation/             # L2: checks/a01.py ... registered by ID; NO pulp imports
│   ├── diagnostics/            # L1 pre-solve checks + post-solve slack explanations
│   ├── reporting/              # L6 excel, html, json
│   ├── generate/               # L8 synthetic instances
│   ├── pipeline.py             # run_stage_a / run_stage_b / run_integrated — library entry points
│   └── cli.py                  # typer: check, run, assign, timetable, validate, alternatives, repair, report, generate, experiment
├── experiments/                # scripted, reproducible experiment runs; write CSV + plots
└── tests/
    ├── unit/                   # domain, io, time, preferences, each constraint
    ├── integration/            # full pipeline on examples
    ├── property/               # hypothesis over generated instances
    └── test_spec_sync.py
```

### Key interfaces

```python
class ConstraintBuilder(Protocol):
    id: ClassVar[str]          # "B5"
    stage: ClassVar[Stage]
    def build(self, ctx: ModelContext, settings: ConstraintSettings) -> None: ...
    # adds constraints/slacks; registers slack terms with ctx.add_objective_term(level, expr, label)

def check(instance: Instance, solution: Solution, settings: ConstraintSettings) -> list[Violation]: ...
# registered with @check("B5") in scheduler.validation
```

- `Instance` is immutable and fully validated. Derived structures (cliques, $\mathcal{F}$, $\alpha_p$) are computed once and cached.
- `ModelContext` is the only object that touches PuLP inside model code. Builders never read files or pandas objects.
- pandas is allowed in `io/` and `reporting/` only.
- All iteration over sets uses sorted IDs, so models and outputs are deterministic.
- Variable names are readable and sanitized: `n[prof_3,MATH161,L]`, `y[MATH161-1L,MWF0900,7.101]`.

---

## 11. Change workflow (how constraints evolve)

When a rule is added or changed:

1. **Spec:** edit §4 (index row, status `planned`) and the constraint's section in §5 or §6: formulation, modes, config keys. Add config keys to §9.
2. **Validator first:** implement `validation/checks/<id>.py`, plus unit tests that hand-build a violating and a satisfying solution.
3. **Ablation pair test:** build a tiny instance where the rule binds. Solve with the constraint `off` and assert that the validator reports a violation. Solve with it `hard` (or `soft`) and assert there is none.
4. **Builder:** implement `model/stage_x/constraints/<id>_<name>.py`.
5. **Config:** add defaults to `configs/default.yaml`.
6. **Status:** set to `implemented` in §4, and add an entry to `docs/CHANGELOG.md`.
7. `uv run pytest` and `uv run ruff check` / `mypy` must pass.

Changing an existing constraint's meaning requires updating its validator check and tests in the same change. Never edit only the builder.

---

## 12. Testing strategy

- **Unit:** time parsing and overlap (incl. edge cases: touching intervals, buffers, multi-day patterns); clique completeness (every overlapping pair shares a clique); rank→weight strategies; schema validation errors.
- **Per constraint:** validator tests and the ablation pair test from §11.
- **Golden:** the tiny example (from the old report: professors A–C; MATH 161 ×2, 351, 361), with hand-computed optimal objective values per level.
- **Property (hypothesis + generator):** for random small instances, every hard constraint passes the validator; level-1 coverage equals the LP-relaxation bound whenever the instance is provably coverable; the solution is identical across two runs with the same seed.
- **Regression:** the bugs of the previous implementation as named tests, e.g. `test_room_cannot_be_double_booked`, `test_overlapping_patterns_with_different_labels_conflict`, `test_same_course_sections_may_overlap_in_conflict_group`.
- **Spec sync:** parse §4. Every `implemented` ID needs a builder, a check, a config entry and a test file mentioning the ID. Every registered ID must appear in §4.
- **Architecture tests:** `scheduler.validation` does not import pulp; `scheduler.model` does not import pandas.
- **Speed:** unit and property tests use tiny instances and finish in under 60 s total. Experiment-sized runs are marked `@pytest.mark.slow`.

---

## 13. Build plan (milestones)

Each milestone ends with green tests and an updated CHANGELOG.

| # | Milestone | Content |
|---|---|---|
| M0 | Scaffold | pyproject (uv), ruff, mypy, pytest, GitHub Actions CI, CLAUDE.md, empty package layout |
| M1 | Domain + IO | dataclasses, pydantic schemas, readers/writers, tiny example data, config loading |
| M2 | Time engine | parsing, overlap, cliques, adjacency, $\alpha_p$; heavy unit and property tests |
| M3 | Validator + diagnostics | L2 checks for all *must* IDs; L1 pre-solve checks |
| M4 | Model framework | ModelContext, registry, solver backend (CBC + HiGHS), lexicographic solve |
| M5 | Stage A core | A1–A4, objective, label attachment, assignments output; golden test |
| M6 | Stage B core | $\mathcal{F}$ construction, B1–B5, objective; regression tests |
| M7 | Pipeline + CLI + reporting | `check / assign / timetable / validate / report`; L4 pins; Excel + HTML + JSON |
| M8 | Should-constraints | A5–A9, B6–B9, B12, each via §11 workflow |
| M9 | Alternatives + repair | L3, L5 |
| M10 | Experiments | L8 generator; ablations, scaling (size vs time), weight-strategy comparison, fairness vs total satisfaction trade-off; results to `docs/report_notes.md` |
| M11 | Could | B10, B11, L7 integrated mode, legacy converter |

---

## 14. Open decisions

Record the decision and date here when settled; update the affected sections.

| # | Question | Current default |
|---|---|---|
| D1 | Which constraints did the supervisor require? (Those become `must`.) | priorities as in §4 |
| D2 | Recitation staffing: faculty, same as lecture, or external (TAs)? | `faculty`, units 0.5 |
| D3 | Do we have curriculum/cohort data for conflict groups beyond course level? | level-based groups only |
| D4 | Is integrated mode (L7) in capstone scope? | M11, experiment only |
| D5 | Are real legacy data files available (for the converter and the medium example)? | yes (2026-10-18): Fall 2026 survey export; converter per §8.1, mapping confirmed by the user |
| D6 | Do priority points $\pi_p$ apply to course preferences, time preferences, or both? | both |
| D7 | Default rank→weight strategy | `linear` |

---

## 15. Glossary

- **Section:** one teachable unit of a course (e.g. MATH 161 lecture section 2 = "2L").
- **Time pattern:** a weekly meeting pattern, e.g. MWF 09:00–09:50 (three meetings).
- **Clique:** a set of time patterns that all overlap each other; at most one can be used by the same room or professor.
- **Slack:** a nonnegative variable measuring how much a soft rule is violated.
- **Lexicographic objective:** objectives optimized in strict priority order.
