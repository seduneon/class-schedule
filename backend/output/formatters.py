"""
Format solver results into clean DataFrames for output/API consumption.

Functions
---------
format_phase1_output(result, repo) -> DataFrame
format_phase2_output(result, repo) -> DataFrame
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from data.loaders import SchedulingDataRepository
    from models.schedule import Phase1Result, Phase2Result


def format_phase1_output(
    result: "Phase1Result", repo: "SchedulingDataRepository"
) -> pd.DataFrame:
    """
    Produce a clean DataFrame with columns:
    Professor (full name), Course, Section (e.g. "1L"), Capacity, Ranking
    """
    from config import TOP_N_COURSES

    # Build rows from assignments (0-based -> 1-based sections)
    rows = []
    for assignment in result.assignments:
        for sec_0based in assignment.sections:
            rows.append(
                {
                    "second_name": assignment.professor,
                    "Course": assignment.course,
                    "Sections": sec_0based + 1,
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["Professor", "Course", "Section", "Capacity", "Ranking"])

    # Add capacity from course_sections
    capacity_map: dict[tuple, int] = {}
    for cs in repo.course_sections:
        capacity_map[(cs.code, cs.section_number)] = cs.capacity

    df["Capacity"] = df.apply(
        lambda row: capacity_map.get((row["Course"], row["Sections"]), 0), axis=1
    )

    # Append section type label ("L") — mirrors original
    df["Section"] = df["Sections"].astype(str) + "L"

    # Merge with full name
    fullname_df = repo.get_prof_fullname_df()
    df = df.merge(fullname_df, on="second_name", how="left")
    df["Professor"] = df["first_name"] + " " + df["second_name"]
    df = df.drop(columns=["first_name", "second_name", "Sections"])

    df = df[["Professor", "Course", "Section", "Capacity"]]

    # Add Ranking from modified_preferences weight -> rank mapping
    row_sum = TOP_N_COURSES * (TOP_N_COURSES + 1) / 2
    modified_pref = repo.modified_preferences.reset_index()
    # Rename index column to RecipientLastName if needed
    if "index" in modified_pref.columns:
        modified_pref.rename(columns={"index": "RecipientLastName"}, inplace=True)
    elif modified_pref.columns[0] != "RecipientLastName":
        modified_pref.rename(
            columns={modified_pref.columns[0]: "RecipientLastName"}, inplace=True
        )

    pref_long = modified_pref.melt(
        id_vars=["RecipientLastName"], var_name="Course", value_name="Weight"
    )
    pref_long = pref_long[pref_long["Weight"] != 0]

    df["LastName"] = df["Professor"].apply(lambda x: x.split()[-1])
    df = df.merge(
        pref_long,
        left_on=["LastName", "Course"],
        right_on=["RecipientLastName", "Course"],
        how="left",
    )
    df["Weight"] = df["Weight"].round(2)

    weight_to_rank = {0.33: 1, 0.27: 2, 0.2: 3, 0.13: 4, 0.07: 5}
    # Use string matching as in original
    weight_to_rank_str = {"0.33": 1, "0.27": 2, "0.2": 3, "0.13": 4, "0.07": 5}
    df["Ranking"] = df["Weight"].astype(str).map(weight_to_rank_str)

    df.drop(columns=["RecipientLastName", "LastName", "Weight"], inplace=True)

    return df[["Professor", "Course", "Section", "Capacity", "Ranking"]]


def format_phase2_output(
    result: "Phase2Result", repo: "SchedulingDataRepository"
) -> pd.DataFrame:
    """
    Produce a clean DataFrame with columns:
    Professor (full name), Course, Section, Time, Room, Time Preference
    """
    from config import TOP_N_TIMESLOTS

    rows = []
    for a in result.assignments:
        rows.append(
            {
                "second_name": a.professor,
                "course_with_section": f"{a.course}-{a.section}",
                "Course": a.course,
                "Section": str(a.section),
                "Time": a.timeslot,
                "Room": a.room,
                # Convert back to human-readable rank
                "Time Preference": a.professor_preference,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(
            columns=["Professor", "Course", "Section", "Time", "Room", "Time Preference"]
        )

    # Convert preference weight to rank integer (reverse of weighting formula)
    row_sum_time = TOP_N_TIMESLOTS * (TOP_N_TIMESLOTS + 1) / 2
    df["Time Preference"] = df["Time Preference"] * row_sum_time
    df["Time Preference"] = TOP_N_TIMESLOTS + 1 - df["Time Preference"]

    # Section label
    df["Section"] = df["Section"] + "L"

    # Merge full name
    fullname_df = repo.get_prof_fullname_df()
    df = df.merge(fullname_df, on="second_name", how="left")
    df["Professor"] = df["first_name"] + " " + df["second_name"]
    df = df.drop(columns=["first_name", "second_name", "course_with_section"])

    return df[["Professor", "Course", "Section", "Time", "Room", "Time Preference"]]
