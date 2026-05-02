"""
SchedulingDataRepository: reads Excel files and exposes clean entity dataclasses
and pre-computed structures consumed by the optimization layer.

Data flow: Excel → pandas (internal only) → entity dataclasses / dicts / DataFrames
No PuLP variables or optimization logic live here.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

import pandas as pd

from config import (
    TOP_N_COURSES,
    TOP_N_TIMESLOTS,
    SECTION_TYPE_WEIGHTS,
    TIME_LIST,
)
from models.entities import CourseSection, Professor, RoomTimeSlot


class SchedulingDataRepository:
    """Loads and pre-processes all scheduling input data from Excel files."""

    def __init__(
        self,
        professors_path: str,
        courses_path: str,
        preferences_path: str,
        rooms_path: Optional[str] = None,
    ) -> None:
        self._professors_path = professors_path
        self._courses_path = courses_path
        self._preferences_path = preferences_path
        self._rooms_path = rooms_path

        # Populated by load()
        self._professors: List[Professor] = []
        self._course_sections: List[CourseSection] = []
        self._course_dict: Dict[str, int] = {}
        self._load_dict: Dict[str, int] = {}
        self._w_by_course: Dict[str, float] = {}
        self._course_preferences: Optional[pd.DataFrame] = None
        self._modified_preferences: Optional[pd.DataFrame] = None
        self._assigned_dict: Dict[str, Dict[str, List[int]]] = {}
        self._two_section_pref: Optional[pd.Series] = None
        self._preferred_courses: Dict[str, List[str]] = {}
        self._prof_fullname_df: Optional[pd.DataFrame] = None
        self._room_timeslots: List[RoomTimeSlot] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Read and process all Excel files; populate all internal state."""
        raw_prefs = self._load_preferences_raw()
        raw_courses = self._load_courses_raw()
        raw_professor = self._load_professors_raw()

        self._build_course_structures(raw_courses)
        self._build_professor_structures(raw_professor, raw_prefs)
        self._build_preference_structures(raw_prefs)

        if self._rooms_path:
            self._room_timeslots = self.load_room_timeslots(self._rooms_path)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def professors(self) -> List[Professor]:
        return self._professors

    @property
    def course_sections(self) -> List[CourseSection]:
        return self._course_sections

    @property
    def course_dict(self) -> Dict[str, int]:
        """course_code -> total number of sections."""
        return self._course_dict

    @property
    def load_dict(self) -> Dict[str, int]:
        """last_name -> integer load."""
        return self._load_dict

    @property
    def w_by_course(self) -> Dict[str, float]:
        """course_code -> section-type weight (L=1.0, R=0.5)."""
        return self._w_by_course

    @property
    def course_preferences(self) -> pd.DataFrame:
        """DataFrame indexed by last_name, cols=course_codes, values=normalized weights."""
        return self._course_preferences

    @property
    def modified_preferences(self) -> pd.DataFrame:
        """course_preferences multiplied by course_points/100."""
        return self._modified_preferences

    @property
    def assigned_dict(self) -> Dict[str, Dict[str, List[int]]]:
        """last_name -> {course_code -> [0-based section indices]}."""
        return self._assigned_dict

    @property
    def two_section_pref(self) -> pd.Series:
        """Series indexed by last_name, values -1/0/1."""
        return self._two_section_pref

    @property
    def preferred_courses(self) -> Dict[str, List[str]]:
        """last_name -> list of preferred course codes."""
        return self._preferred_courses

    @property
    def room_timeslots(self) -> List[RoomTimeSlot]:
        return self._room_timeslots

    # ------------------------------------------------------------------
    # Private loading helpers
    # ------------------------------------------------------------------

    def _load_professors_raw(self) -> pd.DataFrame:
        df = pd.read_excel(self._professors_path)
        df.drop(columns=["email"], inplace=True, errors="ignore")
        return df

    def _load_courses_raw(self) -> pd.DataFrame:
        df = pd.read_excel(self._courses_path)
        df.drop(columns=["Course_title"], inplace=True, errors="ignore")
        return df

    def _load_preferences_raw(self) -> pd.DataFrame:
        """Return the cleaned preferences DataFrame (still wide format with all columns)."""
        prefs = pd.read_excel(self._preferences_path)

        # Drop first 9 columns, then cols 1-8 after that, then row 0
        drop_first = prefs.columns[:9]
        prefs.drop(columns=drop_first, inplace=True)
        drop_next = prefs.columns[1:8]
        prefs.drop(columns=drop_next, inplace=True)
        prefs.drop(index=0, inplace=True)

        # Rename Q1* columns with course codes from the courses file
        raw_courses = pd.read_excel(self._courses_path)
        raw_courses.drop(columns=["Course_title"], inplace=True, errors="ignore")
        course_list_raw = raw_courses["Course_code"].unique()

        new_columns = []
        q1_index = 0
        for col in prefs.columns:
            if str(col).startswith("Q1"):
                new_columns.append(course_list_raw[q1_index])
                q1_index += 1
            else:
                new_columns.append(col)
        prefs.columns = new_columns

        # Clean RecipientLastName
        prefs["RecipientLastName"] = (
            prefs["RecipientLastName"].astype("string").str.strip().replace("", pd.NA)
        )
        prefs = prefs.dropna(subset=["RecipientLastName"])
        prefs = prefs.drop_duplicates(subset=["RecipientLastName"], keep="last")

        return prefs

    def _build_course_structures(self, raw_courses: pd.DataFrame) -> None:
        """Populate course_sections, course_dict, w_by_course."""
        # Build CourseSection list
        sections = []
        for _, row in raw_courses.iterrows():
            sections.append(
                CourseSection(
                    code=str(row["Course_code"]),
                    section_number=int(row["Section_number"]),
                    section_type=str(row["Section_type"]).strip().upper(),
                    capacity=int(row["Capacity"]),
                )
            )
        self._course_sections = sections

        # course_dict: course_code -> max section number (= total sections)
        section_number_df = raw_courses.drop(["Section_type", "Capacity"], axis=1)
        section_number_df = section_number_df.groupby("Course_code", as_index=False)[
            "Section_number"
        ].max()
        self._course_dict = (
            section_number_df.groupby("Course_code")["Section_number"].sum().to_dict()
        )

        # w_by_course: course_code -> weight
        self._w_by_course = (
            raw_courses.set_index("Course_code")["Section_type"]
            .str.strip()
            .str.upper()
            .map(SECTION_TYPE_WEIGHTS)
            .to_dict()
        )

    def _build_professor_structures(
        self, raw_professor: pd.DataFrame, raw_prefs: pd.DataFrame
    ) -> None:
        """Build Professor entities, load_dict, prof_fullname_df, assigned_dict."""
        professors_list = raw_prefs["RecipientLastName"].tolist()

        # Save fullname df for output layer
        self._prof_fullname_df = raw_professor[["first_name", "second_name"]].copy()

        # Build load_dict using last names from preferences (preserves ordering)
        raw_professor["Professor"] = raw_professor["second_name"]
        load_series = raw_professor.iloc[:, [0, 1]].copy()  # Professor, load
        # Overwrite Professor column with preference ordering
        load_series = load_series.copy()
        load_series.iloc[:, 0] = professors_list
        self._load_dict = (
            load_series.groupby(load_series.columns[0])[load_series.columns[1]]
            .sum()
            .astype(int)
            .to_dict()
        )

        # Build pre-assigned dict (1-based -> 0-based)
        assigned_df = raw_professor.drop(
            columns=["load", "course_points", "time_points"], errors="ignore"
        )
        # Also drop first_name, second_name if present (already captured)
        assigned_df_clean = assigned_df.copy()
        if "first_name" in assigned_df_clean.columns:
            assigned_df_clean.drop(columns=["first_name", "second_name"], inplace=True)

        raw_assigned: Dict[str, Dict[str, List[int]]] = {}
        for idx, row in assigned_df_clean.iterrows():
            prof_name = row["Professor"]
            courses_map: Dict[str, List[int]] = {}
            for i in range(1, 5):
                c_col = f"course{i}"
                s_col = f"section{i}"
                if c_col not in row or s_col not in row:
                    continue
                course_val = row[c_col]
                section_val = row[s_col]
                if pd.notna(course_val) and pd.notna(section_val):
                    c_key = str(course_val)
                    if c_key not in courses_map:
                        courses_map[c_key] = []
                    courses_map[c_key].append(int(section_val))
            if courses_map:
                raw_assigned[prof_name] = courses_map

        # Convert to 0-based
        self._assigned_dict = {
            prof: {
                course: [s - 1 for s in secs]
                for course, secs in courses_map.items()
            }
            for prof, courses_map in raw_assigned.items()
        }

        # Build Professor dataclass list
        self._professors = []
        for _, row in raw_professor.iterrows():
            last = str(row["second_name"])
            first = str(row["first_name"])
            load_val = int(row["load"]) if pd.notna(row.get("load")) else 0
            cp = float(row["course_points"]) if pd.notna(row.get("course_points")) else 0.0
            tp = float(row["time_points"]) if pd.notna(row.get("time_points")) else 0.0
            mwf = int(row["MWForTR"]) if pd.notna(row.get("MWForTR")) else 1
            pre = self._assigned_dict.get(last, {})
            msp = 0
            self._professors.append(
                Professor(
                    last_name=last,
                    first_name=first,
                    load=load_val,
                    course_points=cp,
                    time_points=tp,
                    mwf_or_tr=mwf,
                    pre_assigned=pre,
                    multi_section_pref=msp,
                )
            )

    def _build_preference_structures(self, raw_prefs: pd.DataFrame) -> None:
        """Build course_preferences, modified_preferences, two_section_pref, preferred_courses."""
        # Extract course preference columns (MATH* cols)
        names = raw_prefs["RecipientLastName"].reset_index(drop=True)
        math_cols = raw_prefs.filter(regex=r"^MATH")

        top_n = TOP_N_COURSES
        row_sum = top_n * (top_n + 1) / 2

        numeric = math_cols.apply(pd.to_numeric, errors="coerce").fillna(0.0)
        numeric = numeric.mask(numeric > top_n, 0.0)
        normalized = ((top_n + 1 - numeric) / row_sum).where(numeric != 0, 0.0)

        cp = pd.concat([names, normalized.reset_index(drop=True)], axis=1)
        cp.set_index("RecipientLastName", inplace=True)
        self._course_preferences = cp

        # preferred_courses
        self._preferred_courses = {
            prof: cp.columns[(row != 0).values].tolist()
            for prof, row in cp.iterrows()
        }

        # modified_preferences = course_preferences * (course_points / 100)
        # We need to find course_points per professor from raw data
        raw_professor = pd.read_excel(self._professors_path)
        raw_professor.drop(columns=["email"], inplace=True, errors="ignore")
        raw_professor["Professor"] = raw_professor["second_name"]

        points = raw_professor[["Professor", "course_points"]].copy()
        points.set_index("Professor", inplace=True)

        mod_pref = cp.copy()
        mod_pref = mod_pref.multiply(points["course_points"], axis=0)
        mod_pref = mod_pref / 100
        self._modified_preferences = mod_pref

        # two_section_pref: second-to-last column, map {1:1, 2:-1, 3:0}
        tsp = raw_prefs.iloc[:, [0, -2]].copy()
        val_col = tsp.columns[-1]
        tsp[val_col] = pd.to_numeric(tsp[val_col], errors="coerce")
        mapping = {1: 1, 2: -1, 3: 0}
        tsp[val_col] = tsp[val_col].map(mapping).fillna(tsp[val_col])
        tsp.set_index(tsp.columns[0], inplace=True)
        self._two_section_pref = tsp.iloc[:, 0]

        # Update multi_section_pref on professors
        tsp_dict = self._two_section_pref.to_dict()
        updated = []
        for prof in self._professors:
            msp = tsp_dict.get(prof.last_name, 0)
            try:
                msp = int(msp)
            except (ValueError, TypeError):
                msp = 0
            updated.append(
                Professor(
                    last_name=prof.last_name,
                    first_name=prof.first_name,
                    load=prof.load,
                    course_points=prof.course_points,
                    time_points=prof.time_points,
                    mwf_or_tr=prof.mwf_or_tr,
                    pre_assigned=prof.pre_assigned,
                    multi_section_pref=msp,
                )
            )
        self._professors = updated

    # ------------------------------------------------------------------
    # Additional public methods
    # ------------------------------------------------------------------

    def load_room_timeslots(self, rooms_path: str) -> List[RoomTimeSlot]:
        """Read time_room xlsx and return list of RoomTimeSlot."""
        df = pd.read_excel(rooms_path)
        df["combined"] = df["day"].str.replace(" ", "") + " " + df["time"]
        df.drop(columns=["day", "time"], inplace=True)
        df = df[["combined", "room", "cap"]]
        df.rename(columns={"combined": "timeslot", "cap": "room_capacity"}, inplace=True)

        # Sort by the canonical TIME_LIST ordering
        df["timeslot"] = pd.Categorical(df["timeslot"], categories=TIME_LIST, ordered=True)
        df = df.sort_values("timeslot").reset_index(drop=True)

        result = []
        for idx, row in df.iterrows():
            result.append(
                RoomTimeSlot(
                    index=idx,
                    timeslot=str(row["timeslot"]),
                    room=str(row["room"]),
                    room_capacity=int(row["room_capacity"]),
                )
            )
        return result

    def get_time_preferences(self, professors: List[Professor]) -> pd.DataFrame:
        """
        Return a DataFrame (indexed by last_name, cols=TIME_LIST) of weighted time
        preferences, zeroed out for wrong day-type slots and multiplied by time_points/100.
        """
        raw_prefs = self._load_preferences_raw()

        # Rename Q2/Q3 columns to TIME_LIST labels; drop MATH* and Q4/Q5/Q6
        new_columns = []
        time_index = 0
        drop_cols = []
        for col in raw_prefs.columns:
            col_str = str(col)
            if col_str.startswith("Q2") or col_str.startswith("Q3"):
                new_columns.append(TIME_LIST[time_index])
                time_index += 1
            elif col_str.startswith("MATH"):
                drop_cols.append(col)
            elif col_str.startswith("Q5") or col_str.startswith("Q4") or col_str.startswith("Q6"):
                drop_cols.append(col)
            else:
                new_columns.append(col)

        raw_prefs.drop(columns=drop_cols, inplace=True)
        raw_prefs.columns = new_columns

        top_n_time = TOP_N_TIMESLOTS
        row_sum_time = top_n_time * (top_n_time + 1) / 2

        # Build dtw indexed by last name with all time cols as float64 from the start
        name_col = raw_prefs["RecipientLastName"]
        time_cols_df = raw_prefs.drop(columns=["RecipientLastName"])
        numeric = time_cols_df.apply(pd.to_numeric, errors="coerce").fillna(0.0)
        normalized = ((top_n_time + 1 - numeric) / row_sum_time).where(numeric != 0, 0.0)
        dtw = normalized.copy()
        dtw.index = name_col.values

        # Build MWForTR flag indexed by last_name
        raw_professor = pd.read_excel(self._professors_path)
        raw_professor.drop(columns=["email"], inplace=True, errors="ignore")
        raw_professor["Professor"] = raw_professor["second_name"].astype(str).str.strip()
        flag = raw_professor.set_index("Professor")["MWForTR"].reindex(dtw.index).astype(int)

        ucols = pd.Index(dtw.columns).str.upper()
        mwf_cols = dtw.columns[ucols.str.startswith("MWF")]
        tr_cols = dtw.columns[
            ucols.str.startswith("TR") | ucols.str.startswith("TW") | ucols.str.startswith("TTH")
        ]

        keep_mwf = flag == 1
        keep_tr = flag == 0
        # Use .loc with column lists (not boolean masks) to avoid dtype inference issues
        dtw.loc[keep_mwf[keep_mwf].index, tr_cols] = -100.0
        dtw.loc[keep_tr[keep_tr].index, mwf_cols] = -100.0

        # Multiply by time_points / 100
        time_points_df = raw_professor[["Professor", "time_points"]].copy()
        time_points_df["time_points"] = time_points_df["time_points"] / 100.0
        time_points_df.set_index("Professor", inplace=True)
        tp_series = time_points_df["time_points"].reindex(dtw.index)
        dtw = dtw.multiply(tp_series, axis=0)

        return dtw

    def get_prof_fullname_df(self) -> pd.DataFrame:
        """Return DataFrame with first_name and second_name columns."""
        return self._prof_fullname_df.copy()
