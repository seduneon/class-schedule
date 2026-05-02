"""
Upload routes.

POST /upload/professors   → saves professors Excel to temp storage
POST /upload/courses      → saves courses Excel
POST /upload/preferences  → saves preferences Excel
POST /upload/rooms        → saves rooms Excel
"""

from __future__ import annotations

import os
import tempfile
import uuid

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/upload", tags=["upload"])

# In-process storage: maps job_id -> {file_type -> path}
_UPLOAD_STORE: dict[str, dict[str, str]] = {}

# Single global session key for simplicity; a real app would use per-user sessions
_SESSION_KEY = "default"


def _get_or_create_job() -> str:
    """Return the current default job_id, creating a temp dir entry if needed."""
    if _SESSION_KEY not in _UPLOAD_STORE:
        _UPLOAD_STORE[_SESSION_KEY] = {}
    return _SESSION_KEY


def _save_upload(file: UploadFile, file_type: str) -> str:
    """Save an uploaded file to a temp path and record it."""
    job_id = _get_or_create_job()
    suffix = os.path.splitext(file.filename or "upload")[1] or ".xlsx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        content = file.file.read()
        tmp.write(content)
        tmp.flush()
    finally:
        tmp.close()
    _UPLOAD_STORE[job_id][file_type] = tmp.name
    return job_id


def get_upload_paths(job_id: str) -> dict[str, str]:
    """Return the upload paths for a given job_id."""
    return _UPLOAD_STORE.get(job_id, {})


@router.post("/professors")
async def upload_professors(file: UploadFile):
    job_id = _save_upload(file, "professors")
    return JSONResponse({"job_id": job_id, "message": "Professors file uploaded."})


@router.post("/courses")
async def upload_courses(file: UploadFile):
    job_id = _save_upload(file, "courses")
    return JSONResponse({"job_id": job_id, "message": "Courses file uploaded."})


@router.post("/preferences")
async def upload_preferences(file: UploadFile):
    job_id = _save_upload(file, "preferences")
    return JSONResponse({"job_id": job_id, "message": "Preferences file uploaded."})


@router.post("/rooms")
async def upload_rooms(file: UploadFile):
    job_id = _save_upload(file, "rooms")
    return JSONResponse({"job_id": job_id, "message": "Rooms file uploaded."})
