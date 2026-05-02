"""Pydantic request/response models for the scheduling API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SolvePhase2Request(BaseModel):
    job_id: str


class Phase1Response(BaseModel):
    status: str
    job_id: str
    assignments: List[Dict[str, Any]]
    unassigned: List[str]


class Phase2Response(BaseModel):
    status: str
    schedule: List[Dict[str, Any]]
    unscheduled: List[str]
