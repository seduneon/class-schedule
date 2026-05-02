"""
Solve routes.

POST /solve/phase1  → runs Phase 1 ILP, returns Phase1Response
POST /solve/phase2  → runs Phase 2 ILP, returns Phase2Response
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from api.routes.upload import get_upload_paths
from api.schemas import Phase1Response, Phase2Response, SolvePhase2Request
from data.loaders import SchedulingDataRepository
from data.validators import validate_loads
from optimization.phase1 import solve_phase1
from optimization.phase2 import solve_phase2

router = APIRouter(prefix="/solve", tags=["solve"])

# In-process result store: job_id -> {"phase1": Phase1Result, "phase2": Phase2Result, "repo": repo}
_RESULT_STORE: dict[str, dict] = {}


@router.post("/phase1", response_model=Phase1Response)
async def run_phase1():
    """Load uploaded files, run Phase 1, store results, return summary."""
    job_id = "default"
    paths = get_upload_paths(job_id)

    required = ["professors", "courses", "preferences"]
    missing = [r for r in required if r not in paths]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing uploaded files: {missing}. Upload them first via /upload/*.",
        )

    repo = SchedulingDataRepository(
        professors_path=paths["professors"],
        courses_path=paths["courses"],
        preferences_path=paths["preferences"],
        rooms_path=paths.get("rooms"),
    )
    repo.load()
    validate_loads(repo)

    result = solve_phase1(repo)

    _RESULT_STORE[job_id] = {"phase1": result, "repo": repo}

    assignments_out = [
        {
            "professor": a.professor,
            "course": a.course,
            "sections": [s + 1 for s in a.sections],
            "status": a.status,
        }
        for a in result.assignments
    ]
    unassigned = result.unassigned_professors

    return Phase1Response(
        status=result.status,
        job_id=job_id,
        assignments=assignments_out,
        unassigned=unassigned,
    )


@router.post("/phase2", response_model=Phase2Response)
async def run_phase2(request: SolvePhase2Request):
    """Run Phase 2 using Phase 1 results already stored for job_id."""
    job_id = request.job_id
    stored = _RESULT_STORE.get(job_id)
    if stored is None or "phase1" not in stored:
        raise HTTPException(
            status_code=404,
            detail=f"No Phase 1 result found for job_id={job_id}. Run /solve/phase1 first.",
        )

    phase1_result = stored["phase1"]
    repo: SchedulingDataRepository = stored["repo"]

    if not repo.room_timeslots:
        paths = get_upload_paths(job_id)
        if "rooms" not in paths:
            raise HTTPException(
                status_code=400,
                detail="Rooms file not uploaded. Upload via /upload/rooms first.",
            )
        room_timeslots = repo.load_room_timeslots(paths["rooms"])
        # Patch the repo's internal room_timeslots
        repo._room_timeslots = room_timeslots

    result = solve_phase2(phase1_result, repo)
    stored["phase2"] = result

    schedule_out = [
        {
            "course": a.course,
            "section": a.section,
            "professor": a.professor,
            "timeslot": a.timeslot,
            "room": a.room,
            "course_capacity": a.course_capacity,
            "room_capacity": a.room_capacity,
            "professor_preference": a.professor_preference,
        }
        for a in result.assignments
    ]

    return Phase2Response(
        status=result.status,
        schedule=schedule_out,
        unscheduled=result.unscheduled,
    )
