# Class Scheduler

A tool that builds the teaching timetable for the Department of Mathematics at Nazarbayev University
(MATH 499 capstone). It decides **who teaches which section**, and **when and where** each
section meets, while following the department's rules and respecting professors' preferences
as far as possible.

## In one paragraph

You give it the course offerings, the professors (with their preferences), the rooms and the
allowed class times. It first assigns professors to sections, then gives every section a
time and a room. It never breaks a firm rule to satisfy a preference. If something cannot
be done (for example, not enough large rooms), it still produces the best possible
timetable and tells you in plain words what is missing and why. The result is an Excel
workbook and a weekly timetable you can open in a browser.

---

## 1. Inputs

One folder of spreadsheets (CSV files, or one Excel workbook with these sheets).

| File | What it says | Example |
|---|---|---|
| **offerings** | Which courses run this term, how many sections of each, their size, and whether they are lectures (L), recitations (R) or labs | MATH 161, lecture, 2 sections of 200 students |
| **professors** | Each professor's minimum and maximum teaching load, plus optional personal settings (see below) | Load 3–4 units, at most 2 different courses |
| **course_preferences** *(optional, but see note)* | Each professor's ranking of the courses they would like to teach (1 = favourite), or `cannot` | MATH 351: rank 1 |
| **time_preferences** *(optional)* | Each professor's ranking of class times, or `cannot` | Mon/Wed/Fri 9:00: rank 2 |
| **rooms** | Rooms with their capacity and type | Room 7.210, 54 seats, classroom |
| **room_availability** *(optional)* | When each room may be used, if not always | Room 7.210 only on Tue/Thu mornings |
| **time_patterns** | The allowed class times | MWF 9:00–9:50, TR 10:30–11:45 |
| **unavailability** *(optional)* | Times a professor cannot teach | Prof X, Friday after 15:00 |
| **blocked_slots** *(optional)* | Times nobody teaches | Wednesday 12:00–13:00 (seminar) |
| **pre_assignments** *(optional)* | Decisions already made by the chair | Prof Y teaches MATH 161 |
| **conflict_groups** *(optional)* | Courses students take together, so they must not clash | First-year core |
| **pins** *(optional)* | Decisions to keep fixed when solving again: who teaches a course, or a section's time and/or room | MATH 161 1L stays at MWF 9:00 |
| **section_links** *(optional)* | Which lecture each recitation belongs to (otherwise a recitation is matched against every lecture of its course) | MATH 161 1R goes with 1L |

Note: by default a professor may only teach courses they ranked, so without
`course_preferences` nobody can be assigned (unless pre-assigned).

Optional personal settings per professor: priority (whose preferences weigh more), maximum
number of different courses, maximum teaching days, whether they like several sections of
the same course, whether they prefer classes back-to-back or spread out, and preferred
weekday pattern (Mon/Wed/Fri or Tue/Thu).

The supervisor's spreadsheets (courses, professors, survey export, and rooms/times when
available) can be converted into this format automatically. The converter
also lists everything that needs a human decision (free-text comments, duplicate or
unmatched survey answers) in `review.csv`. The old `MWForTR` column is ignored: the
survey question on weekday patterns decides instead.

The received files are never edited by hand. Small layout differences (the header row a
little higher or lower, columns in another order, extra spaces) are handled automatically,
but anything whose *meaning* is unclear stops the conversion with a message saying where.
The fix is then written once in a short **fixes file**, for example "the courses file has
one row per course" or "the unlabeled column AZ is MATH 818". Each fix is listed in
`review.csv`, and a fix that no longer applies (because corrected files were sent) is
reported, so it cannot silently do the wrong thing.

**Only part of the data?** Without rooms and class times the tool still assigns professors
(step 2) and stops there. The checks that need rooms or times are listed as
*not checked* in `check.txt` and the report instead of being skipped silently.

---

## 2. Process

```
 data folder ──► 1. Check ──► 2. Assign professors ──► 3. Build timetable ──► results
                    │              (Stage A)                (Stage B)
                    ▼                  │
             data problems     chair may edit the assignments here,
             in plain words    then re-run step 3 only
```

1. **Check the data.** Before solving, it looks for problems: unknown names, too few
   professors for a course, sections too big for any room, more sections than rooms and
   times can hold, and so on. These are listed in `check.txt`.
2. **Assign professors (Stage A).** Decides how many sections of each course every
   professor teaches.
3. **Build the timetable (Stage B).** Gives every section a time and a room, using the
   professor assignment from step 2.

Splitting the work into two steps keeps each step fast and lets the chair review and edit
the assignment before times are fixed.

**How it decides (in this order):**

1. **Cover every section.** Leaving a section without a professor, time or room is the
   worst outcome. Nothing else is traded against it.
2. **Break as few "strongly preferred" rules as possible** (the second table below).
3. **Make professors as happy as possible**: best-ranked courses and times, weighted by
   priority, while making sure nobody is left with only bad choices.

A lower step is never improved at the cost of a higher one.

---

## 3. Rules (constraints)

Every rule has an ID (used in reports and settings) and can be switched between
**firm** (never broken), **preferred** (broken only if unavoidable, and reported) or
**off**, in the settings file `configs/default.yaml`, without changing any code.

### Always respected: physical facts

- A section only goes into a room that is **big enough** and of the **right type**.
- A section only uses a time pattern **allowed for its type** (lecture, recitation, lab).
- A room is only used at times it is **available**.

### Firm rules (on by default)

| ID | Rule | In plain words |
|---|---|---|
| A1 | Section coverage | Every section gets exactly one professor. |
| A3 | Eligibility | Professors only teach courses they ranked; never one marked `cannot`. |
| A4 | Pre-assignments | The chair's decisions made in advance are kept. |
| A8 | Timetable capacity | Nobody is given more sections than they can fit into non-clashing time slots, and professors who teach only on Mon/Wed/Fri (or only Tue/Thu) are not given more than those days' rooms and times can hold. |
| B1 | Scheduled once | Every section gets exactly one time and one room. |
| B2 | No room clash | A room never holds two classes at the same time. |
| B3 | No professor clash | A professor never teaches two classes at the same time. |
| B4 | Unavailability | No class when its professor is unavailable or the time is blocked. |
| B5 | Conflict groups | Courses that students take together do not clash (by default: 300-level, 400-level and graduate courses, plus any listed groups). Sections of the *same* course may overlap. |
| B13 | Weekday pattern | A professor teaches only on the days chosen in the survey (Mon/Wed/Fri or Tue/Thu), and never on both unless they answered "any day". |

A1 and B1 are special: if covering everything is truly impossible, the tool still returns a
timetable and lists exactly which sections are left uncovered.

### Preferred rules (on by default)

| ID | Rule | In plain words |
|---|---|---|
| A2 | Teaching load | Each professor teaches between their minimum and maximum load. Going *over* the maximum is not allowed; falling *under* the minimum is allowed only if unavoidable. |
| A5 | Several sections of one course | Respects whether a professor prefers one section per course or likes teaching several. |
| A6 | Different courses | Respects a professor's maximum number of different courses to prepare. |
| A9 | Fair course choices | Avoids leaving any single professor with only low-ranked courses. |
| A10 | Top-5 courses | Gives professors courses from their own top 5 (the survey's promise); a course ranked lower only when needed to cover a section or fill a load. |
| B6 | Spread sections | Sections of the same course are offered at different times, so students have a choice. |
| B7 | Recitation vs lecture | A recitation does not clash with its own lecture. |
| B8 | Teaching days | Respects a professor's maximum number of teaching days per week. |
| B9 | Compact or spread | Puts a professor's classes back-to-back or apart, as they prefer. |
| B12 | Fair time choices | Avoids leaving any single professor with only bad times. |

### Optional rules (off by default)

| ID | Rule | In plain words |
|---|---|---|
| A7 | Recitation staffing | Who teaches recitations: professors like any other section (current default), the lecture's own professor, or teaching assistants outside the model. |
| B10 | Consecutive classes | At most N classes in a row (default 3). |
| B11 | Same room | A professor stays in as few different rooms (or buildings) as possible. |

---

## 4. Outputs

Each run creates its own folder, named by date and time, e.g.
`runs/2026-10-19_15-40-52_tiny/`. Old results are never overwritten, and
`runs/latest` always points to the newest one. Runs on real data go next to that data instead
(`--runs-dir data/private/<term>/runs`, see below).

| File | What it is |
|---|---|
| **report.xlsx** | The main result. Sheets: timetable per professor, per room and per conflict group; list of assignments; satisfaction table (what each professor got vs. their best possible); broken rules; data warnings; solver statistics. |
| **timetable.html** | Weekly timetable grid; open it in any browser. |
| **assignments.csv** | Who teaches which section. **The chair may edit this file** and re-run only the timetable step. |
| **check.txt** | Data problems found before solving. |
| **run.json** | Record of the run: which data and settings were used, when, how long it took, and how many firm rules are broken (`hard_violations`, ideally 0). |
| **solution.json**, **stage_a.json** | The same results in a machine-readable form (for re-checking and repairs). |
| **config.yaml**, **log.txt** | The exact settings used, and the full screen output. |

Every result, including one edited by hand, is re-checked by an independent checker that
does not trust the solver, so rule violations are always reported.

Other things it can do: list a few **alternative** near-best timetables to choose from, and
**repair** an existing timetable after a change (e.g. a professor leaves) while moving as
few classes as possible.

---

## 5. How to run it

Install once (needs [uv](https://docs.astral.sh/uv/)):

```bash
uv sync
```

Run everything on a data folder:

```bash
uv run scheduler run data/examples/tiny
```

After editing `runs/latest/assignments.csv`, rebuild only the timetable (into a new folder):

```bash
uv run scheduler run data/examples/tiny --assignments runs/latest/assignments.csv
```

If the folder has no `rooms` or `time_patterns`, `run` stops after the professor
assignment and says so (the report then has no timetable).

To try different data, point at another folder. For example,
`data/examples/medium_no_recitations` is the (anonymized) Fall 2026 data without recitations.
To try different rules, copy `configs/default.yaml`, change it, and add `-c my_config.yaml`.

Example data:

| Folder | Contents |
|---|---|
| `data/examples/tiny` | 3 professors, 4 sections; small enough to check by hand |
| `data/examples/medium` | Fall 2026, anonymized: 26 professors, 74 sections, 5 rooms |
| `data/examples/medium_no_recitations` | The same without the 26 recitation sections |

Real data with names stays in `data/private/` and is never shared or committed. One folder per
term:

```
data/private/
  <term>/                      e.g. fall2026, spring2027
    raw/<YYYY-MM-DD>/          the supervisor's files exactly as received; never edited
    fixes.yaml                 declared corrections (SPEC §8.1.2)
    instance/                  converter output (variants: instance_<name>/)
    runs/                      results: --runs-dir data/private/<term>/runs
    experiments/<name>/        what-if copies with their own fixes.yaml, instance/, runs/
    deliveries/<YYYY-MM-DD>/   exactly what was prepared for the supervisor that day
    verify/                    independent check scripts
    VERIFICATION_<date>.md
  reference/                   past-capstone material (source of requirements only)
```

Nothing else goes at the repository root: new files from the supervisor go straight into
`data/private/<term>/raw/<date>/`. Excel, zip and PDF files are git-ignored everywhere.

---

## For developers

The full specification (every rule as a formula, data formats, design decisions) is
[`docs/SPEC.md`](docs/SPEC.md); changes are logged in [`docs/CHANGELOG.md`](docs/CHANGELOG.md).
Both stages are mixed-integer linear programs (PuLP, CBC by default) with lexicographic
objectives.

```bash
uv run scheduler --help                     # all commands
uv run scheduler check DATA                 # step 1 only
uv run scheduler assign DATA                # step 2 only
uv run scheduler timetable DATA --assignments FILE
uv run scheduler validate DATA solution.json
uv run scheduler alternatives DATA --assignments FILE
uv run scheduler repair DATA --previous solution.json
uv run scheduler report DATA solution.json  # Excel + HTML for an existing solution
uv run scheduler generate OUT --seed 1      # synthetic test instance
uv run scheduler experiment ablation        # ablation | scaling | weights | fairness | all
uv run pytest                               # fast tests; -m slow for large ones
uv run ruff check . && uv run mypy src
```

Experiments for the report: `uv run python experiments/run_all.py [--quick]` →
`experiments/results/` (notes in `docs/report_notes.md`).

Converting the Fall 2026 survey files (lectures only; recitations are not scheduled):

```bash
uv run scheduler convert-legacy data/private/fall2026/raw/2026-10-18 \
  -o data/private/fall2026/instance_no_recitations
# remove the section_type = R rows from course_preferences.csv (see below),
# read data/private/fall2026/instance_no_recitations/review.csv, then:
uv run scheduler check data/private/fall2026/instance_no_recitations
uv run scheduler run data/private/fall2026/instance_no_recitations --runs-dir data/private/fall2026/runs
```

The survey also ranks recitations, so the converter writes `section_type = R` rows to
`course_preferences.csv` even when no recitation is offered. Delete them: every preference
row counts toward a professor's number of ranked items (SPEC §3.4), so leftover rows shift
the course weights. With all 26 recitations added (`--add-offering MATH161:R:8:57` etc.)
the department's 5 rooms offer only 66 (room, time) slots for 74 sections, so that
instance cannot be fully scheduled.

`--anonymize` produces a shareable copy (that is how `data/examples/medium` was made).
Mapping: SPEC §8.1.

Spring 2027 (courses one row per course, an unlabeled MATH 818 survey column, no
rooms/times yet), in the layout above:

```yaml
# fixes.yaml
courses_format: per_course                 # Section_number = number of sections
survey_columns:
  AZ: {question: Q1, course: "MATH 818"}   # column without a header in the export
```

```bash
uv run scheduler convert-legacy data/private/spring2027/raw/2026-11-05 \
  -o data/private/spring2027/instance --fixes data/private/spring2027/fixes.yaml
uv run scheduler run data/private/spring2027/instance \
  --runs-dir data/private/spring2027/runs               # Stage A only: no rooms/times
```

When corrected files arrive, put them in a new `raw/<date>/` folder and convert again with
the same fixes; the converter says which fixes are no longer needed.

Before sending anything to the supervisor, check the result against the Excel files with the
term's independent scripts (SPEC §8.1.3), and record the outcome in `VERIFICATION_<date>.md`:

```bash
D=data/private/spring2027
uv run python -I $D/verify/verify_all.py $D/raw/2026-11-05 $D/instance $D/runs/latest
```
