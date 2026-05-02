"""
Results routes.

GET /results/{job_id}            → full result JSON
GET /results/download/{job_id}   → .xlsx file download
"""

from __future__ import annotations

import os
import tempfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from api.routes.solve import _RESULT_STORE
from data.loaders import SchedulingDataRepository
from output.exporters import export_phase1, export_phase2
from output.formatters import format_phase1_output, format_phase2_output

router = APIRouter(prefix="/results", tags=["results"])


@router.get("/{job_id}")
async def get_results(job_id: str):
    """Return full Phase 1 and Phase 2 result JSON for the given job."""
    stored = _RESULT_STORE.get(job_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"No results found for job_id={job_id}.")

    out: dict = {"job_id": job_id}

    if "phase1" in stored:
        r1 = stored["phase1"]
        out["phase1"] = {
            "status": r1.status,
            "objective_value": r1.objective_value,
            "assignments": [
                {
                    "professor": a.professor,
                    "course": a.course,
                    "sections": [s + 1 for s in a.sections],
                    "status": a.status,
                }
                for a in r1.assignments
            ],
            "unassigned_professors": r1.unassigned_professors,
            "unfilled_courses": r1.unfilled_courses,
            "professor_loads": r1.professor_loads,
        }

    if "phase2" in stored:
        r2 = stored["phase2"]
        out["phase2"] = {
            "status": r2.status,
            "assignments": [
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
                for a in r2.assignments
            ],
            "unscheduled": r2.unscheduled,
        }

    return JSONResponse(out)


@router.get("/download/{job_id}")
async def download_results(job_id: str):
    """Return a combined .xlsx file with Phase 1 and Phase 2 sheets."""
    stored = _RESULT_STORE.get(job_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"No results found for job_id={job_id}.")

    repo: SchedulingDataRepository = stored.get("repo")
    if repo is None:
        raise HTTPException(status_code=500, detail="Repository not available for this job.")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    tmp.close()

    with __import__("openpyxl").Workbook() as wb:
        # Remove default empty sheet
        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

        if "phase1" in stored:
            df1 = format_phase1_output(stored["phase1"], repo)
            ws1 = wb.create_sheet("Phase1")
            # Write header
            ws1.append(list(df1.columns))
            for row in df1.itertuples(index=False):
                ws1.append(list(row))

        if "phase2" in stored:
            df2 = format_phase2_output(stored["phase2"], repo)
            ws2 = wb.create_sheet("Phase2")
            ws2.append(list(df2.columns))
            for row in df2.itertuples(index=False):
                ws2.append(list(row))

        wb.save(tmp.name)

    return FileResponse(
        path=tmp.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"schedule_{job_id}.xlsx",
    )
