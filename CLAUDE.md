# Class Scheduling Automation — Claude Code Guide

## Project Overview

Capstone project (MATH 499, Nazarbayev University) that automates university class
scheduling using Mixed Integer Linear Programming (PuLP). Assigns professors to
course sections (Phase 1) then schedules those assignments into rooms and time slots
(Phase 2). Includes a FastAPI backend and React frontend.

## Stack

- **Backend**: Python 3.11+, FastAPI, PuLP (CBC solver), pandas, openpyxl
- **Frontend**: React 18, Vite, Tailwind CSS
- **Testing**: pytest (backend), Vitest (frontend)
- **Solver**: PULP_CBC_CMD (open-source, no license needed)

## Repo Structure

```
class-scheduling/
├── CLAUDE.md                  ← you are here
├── .gitignore
├── README.md
│
├── backend/
│   ├── main.py                ← FastAPI entry point
│   ├── requirements.txt
│   ├── config.py              ← all magic numbers/constants
│   │
│   ├── data/
│   │   ├── loaders.py         ← SchedulingDataRepository (reads Excel)
│   │   └── validators.py      ← input sanity checks, weight normalization
│   │
│   ├── models/
│   │   ├── entities.py        ← Professor, Course, Room, TimeSlot dataclasses
│   │   └── schedule.py        ← Schedule, Assignment result types
│   │
│   ├── optimization/
│   │   ├── phase1.py          ← Prof → Course section ILP
│   │   ├── phase2.py          ← Assignment → TimeSlot + Room ILP
│   │   └── constraints/
│   │       ├── base.py        ← abstract Constraint class (Strategy pattern)
│   │       ├── workload.py    ← load, pre-assignment constraints
│   │       ├── preferences.py ← course/time preference constraints
│   │       ├── scheduling.py  ← room capacity, no double-booking, level constraints
│   │       └── custom.py      ← NEW constraints added for this capstone
│   │
│   ├── api/
│   │   ├── routes/
│   │   │   ├── upload.py      ← POST /upload/{professors,courses,preferences,rooms}
│   │   │   ├── solve.py       ← POST /solve/phase1, POST /solve/phase2
│   │   │   └── results.py     ← GET /results/{job_id}, GET /results/download/{job_id}
│   │   └── schemas.py         ← Pydantic request/response models
│   │
│   └── output/
│       ├── formatters.py      ← format solver results → clean dicts/DataFrames
│       └── exporters.py       ← write .xlsx output files
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── components/
│       │   ├── FileUpload.jsx      ← drag-drop Excel uploads
│       │   ├── ScheduleTable.jsx   ← Phase 1 result table
│       │   ├── TimetableGrid.jsx   ← Phase 2 visual room×time grid
│       │   └── SolverStatus.jsx    ← running / optimal / infeasible badge
│       └── pages/
│           ├── Phase1.jsx
│           └── Phase2.jsx
│
└── tests/
    ├── fixtures/               ← small synthetic Excel files (3 profs, 4 courses)
    │   ├── professors_test.xlsx
    │   ├── courses_test.xlsx
    │   ├── preferences_test.xlsx
    │   └── rooms_test.xlsx
    ├── test_loaders.py
    ├── test_constraints.py
    ├── test_phase1.py
    └── test_phase2.py
```

## Commands

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload          # start API at localhost:8000
python -m pytest ../tests/         # run all tests

# Frontend
cd frontend
npm install
npm run dev                        # start UI at localhost:5173
npm run build                      # production build

# Run both (from repo root)
# Terminal 1: cd backend && uvicorn main:app --reload
# Terminal 2: cd frontend && npm run dev
```

## Architecture Rules

**Constraints are classes, not inline code.**
Every scheduling rule lives in its own class in `optimization/constraints/`.
Adding a new constraint = new class + add to list in phase1.py or phase2.py.
Never add constraint logic directly inside phase1.py or phase2.py bodies.

```python
# CORRECT — add a new constraint
class NoFridayAfternoonConstraint(Constraint):
    name = "no_friday_afternoon"
    def apply(self, model, variables, data): ...

# WRONG — don't do this
for prof in professors:
    model += lpSum(...) <= 1   # hardcoded inside phase file
```

**Relaxation variables are named to avoid collisions.**
The original code had `p = LpVariable.dicts("prof_relax", ...)` then `for p in professors`
which silently overwrites the dict. Always use:
- `prof_relax` for the professor relaxation LpVariable dict
- `course_relax` for course relaxation
- Avoid single-letter loop variable names that shadow outer scope

**All magic numbers go in config.py.**
```python
# config.py
TOP_N_COURSES = 5
TOP_N_TIMESLOTS = 15
PENALTY_WEIGHT = 100
BIG_M = 10_000
```

**Data flows in one direction.**
```
Excel files → loaders.py → entity dataclasses → optimization → result dataclasses → exporters/API
```
No raw DataFrames inside optimization code. No PuLP variables inside loaders.

## Known Bugs in the Original Code (do not reproduce)

1. **Variable name collision** (line 234 vs 317): `p` used as both relaxation dict and
   loop variable. Fix: rename dict to `prof_relax`.

2. **Undefined variable** (line 259): `pre_assignments` referenced but never defined.
   Should be `assigned_dict`.

3. **Big-M commented out** (line 726): room capacity constraint is too strict,
   makes the problem unnecessarily infeasible. Re-enable with proper Big-M.

4. **`y` variable unused**: declared but never appears in constraints or objective.
   Either use it or remove it.

5. **No-double-booking too weak in Phase 2**: constraint checks per raw timeslot index
   instead of per (room, timeslot) pair.

## New Constraints to Implement (capstone additions)

These are in `optimization/constraints/custom.py`:

- **NotPreferredTimeSlot**: professor cannot teach at times they marked as unavailable
  ```
  sum of x[p, t] for t in unavailable_times[p] == 0
  ```

- **ConsecutiveTimeSlotPenalty**: penalize (or optionally forbid) back-to-back
  assignments for same professor (linearized version — see paper §5)

- **[your additional constraints here]**

## API Endpoints

```
POST /upload/professors        multipart Excel → 200 OK
POST /upload/courses           multipart Excel → 200 OK
POST /upload/preferences       multipart Excel → 200 OK
POST /upload/rooms             multipart Excel → 200 OK

POST /solve/phase1             → { status, job_id, assignments, unassigned }
POST /solve/phase2             body: { job_id } → { status, schedule, unscheduled }

GET  /results/{job_id}         → full result JSON
GET  /results/download/{job_id}→ .xlsx file download
GET  /docs                     → Swagger UI (auto-generated by FastAPI)
```

## Testing Strategy

- Use fixtures in `tests/fixtures/` — the 3-professor, 4-course example from the
  paper (§3.4) whose solution can be verified by hand.
- Each constraint class has its own test: build a minimal model, apply only that
  constraint, solve, assert the expected variable values.
- Phase tests: run full phase on fixture data, check objective value matches expected.
- Never use real professor data in tests (privacy).

## Git Workflow

```bash
# Never commit to main directly
git checkout -b feature/constraint-no-friday
# ... work ...
git add .
git commit -m "feat: add NoFridayAfternoon constraint with test"
git push origin feature/constraint-no-friday
# open PR → merge to main
```

Branch naming: `feature/`, `fix/`, `refactor/`, `test/`

## Context Management Tips for Claude Code

- Run `/status` often — context fills up fast with solver output
- Start a new session after each major feature (use git commits as checkpoints)
- If Claude starts making mistakes, run `/clear` and paste only the relevant files
- Use Shift+Tab (plan mode) before any big refactor to review the plan first
- Keep sessions focused: one session = one constraint class or one API route
