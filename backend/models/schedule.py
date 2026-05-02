from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Phase1Assignment:
    professor: str          # last name
    course: str
    sections: List[int]     # 0-based section indices
    status: str             # "Pre-assigned" or "New"


@dataclass
class Phase1Result:
    status: str
    objective_value: Optional[float]
    assignments: List[Phase1Assignment]
    unassigned_professors: List[str]
    unfilled_courses: List[str]
    professor_loads: Dict[str, int]


@dataclass
class Phase2Assignment:
    course: str
    section: int
    professor: str
    timeslot: str
    room: str
    course_capacity: int
    room_capacity: int
    professor_preference: float


@dataclass
class Phase2Result:
    status: str
    assignments: List[Phase2Assignment]
    unscheduled: List[str]
