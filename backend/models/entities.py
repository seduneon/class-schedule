from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Professor:
    last_name: str
    first_name: str
    load: int
    course_points: float  # 0-100
    time_points: float    # 0-100
    mwf_or_tr: int        # 1 = MWF, 0 = TR
    pre_assigned: Dict[str, List[int]] = field(default_factory=dict)  # course -> 0-based section indices
    multi_section_pref: int = 0  # 1, 0, or -1


@dataclass
class CourseSection:
    code: str
    section_number: int   # 1-based
    section_type: str     # "L" or "R"
    capacity: int


@dataclass
class TimeSlot:
    label: str  # e.g. "MWF 09:00 AM-09:50 AM"


@dataclass
class Room:
    name: str
    capacity: int


@dataclass
class RoomTimeSlot:
    index: int
    timeslot: str
    room: str
    room_capacity: int
