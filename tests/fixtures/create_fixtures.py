"""
create_fixtures.py
------------------
Generates the four synthetic Excel files used by the test suite.
Run with:  python tests/fixtures/create_fixtures.py

Design (3 professors, 4 courses, 6 total sections = 6 total load):
    Prof A  Smith   load=2  MWF
    Prof B  Jones   load=2  TR
    Prof C  Brown   load=2  MWF

    MATH301  2 sections  L  cap=30
    MATH302  1 section   L  cap=25
    MATH401  2 sections  L  cap=20
    MATH402  1 section   L  cap=15

Preferences (Q1): Smith 301=1,302=2,401=3,402=0
                  Jones 302=1,401=2,402=3,301=0
                  Brown 401=1,301=2,302=3,402=0
Time prefs (Q2=MWF 9 slots, Q3=TR 6 slots): MWF profs rank MWF slots, TR prof ranks TR slots
Q4 (multi-section): Smith=3(neutral), Jones=3(neutral), Brown=2(negative→-1)
"""

import os
import sys

import openpyxl
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# professors_test.xlsx
# ---------------------------------------------------------------------------

def create_professors():
    """
    The loader (_build_professor_structures) does:
        raw_professor["Professor"] = raw_professor["second_name"]   # appends last col
        load_series = raw_professor.iloc[:, [0, 1]]   # → expects col0=last_name, col1=load
        load_series.iloc[:, 0] = professors_list      # overwrites col0 with pref ordering
        load_series.groupby(col0)[col1].sum().astype(int)  → col1 must be numeric (load)

    After 'email' is dropped the columns must be ordered so that:
        col 0 = second_name  (last name, used as professor identifier)
        col 1 = load         (int)
    Then first_name, course_points, time_points, MWForTR, course1..section4 follow.

    Original column order (after email drop):
        second_name, load, first_name, course_points, time_points, MWForTR,
        course1, section1, course2, section2, course3, section3, course4, section4
    """
    data = {
        "email": [
            "alice.smith@nu.edu.kz",
            "bob.jones@nu.edu.kz",
            "carol.brown@nu.edu.kz",
        ],
        # col 0 after email drop = second_name (last name)
        "second_name": ["Smith", "Jones", "Brown"],
        # col 1 after email drop = load
        "load": [2, 2, 2],
        # remaining columns
        "first_name": ["Alice", "Bob", "Carol"],
        "course_points": [80.0, 90.0, 75.0],
        "time_points": [70.0, 60.0, 80.0],
        "MWForTR": [1, 0, 1],
        # No pre-assignments — all NaN
        "course1": [None, None, None],
        "section1": [None, None, None],
        "course2": [None, None, None],
        "section2": [None, None, None],
        "course3": [None, None, None],
        "section3": [None, None, None],
        "course4": [None, None, None],
        "section4": [None, None, None],
    }
    df = pd.DataFrame(data)
    path = os.path.join(HERE, "professors_test.xlsx")
    df.to_excel(path, index=False)
    print(f"Created {path}")


# ---------------------------------------------------------------------------
# courses_test.xlsx
# ---------------------------------------------------------------------------

def create_courses():
    """
    Columns: Course_title, Course_code, Section_number, Section_type, Capacity

    MATH301 section 1 & 2
    MATH302 section 1
    MATH401 section 1 & 2
    MATH402 section 1
    """
    data = {
        "Course_title": [
            "Calculus I",
            "Calculus I",
            "Calculus II",
            "Linear Algebra",
            "Linear Algebra",
            "Abstract Algebra",
        ],
        "Course_code": [
            "MATH301",
            "MATH301",
            "MATH302",
            "MATH401",
            "MATH401",
            "MATH402",
        ],
        "Section_number": [1, 2, 1, 1, 2, 1],
        "Section_type": ["L", "L", "L", "L", "L", "L"],
        "Capacity": [30, 30, 25, 20, 20, 15],
    }
    df = pd.DataFrame(data)
    path = os.path.join(HERE, "courses_test.xlsx")
    df.to_excel(path, index=False)
    print(f"Created {path}")


# ---------------------------------------------------------------------------
# preferences_test.xlsx
# ---------------------------------------------------------------------------

def create_preferences():
    """
    The loader (_load_preferences_raw) does the following:
      1. Drop first 9 columns entirely.
      2. From the remaining columns, drop cols at positions 1-7 (indices 1..7).
      3. Drop row 0 (it's a second header row).
      4. Rename Q1_* columns to course codes from courses file.
      5. Use 'RecipientLastName' as the remaining non-Q column.

    So we need to build a DataFrame where:
      - columns[0..8]  = 9 filler columns (dropped)
      - columns[9]     = 'RecipientLastName'
      - columns[10..16]= 7 filler columns (dropped as cols 1..7 after first drop)
      - columns[17..20]= Q1_1, Q1_2, Q1_3, Q1_4  (course rankings)
      - columns[21..29]= Q2_1..Q2_9              (MWF timeslot rankings)
      - columns[30..35]= Q3_1..Q3_6              (TR  timeslot rankings)
      - columns[36]    = Q4                       (multi-section pref)
      - columns[37]    = Q5                       (any)

    Row 0 in the Excel file (after header) is a 'label row' that gets dropped by
    the loader (it does `prefs.drop(index=0, inplace=True)` which drops the first
    data row, i.e. index 0 after read_excel).

    So we need:
      actual Excel row 0 = column headers  (written by to_excel)
      Excel row 1        = dummy label row  (gets dropped by loader)
      Excel rows 2-4     = Smith, Jones, Brown
    """
    # Build column names
    filler_front = [f"_filler_{i}" for i in range(9)]   # 9 columns → dropped
    last_name_col = ["RecipientLastName"]
    filler_mid = [f"_mid_{i}" for i in range(7)]         # 7 columns → dropped
    q1_cols = [f"Q1_{i}" for i in range(1, 5)]           # Q1_1..Q1_4
    q2_cols = [f"Q2_{i}" for i in range(1, 10)]          # Q2_1..Q2_9  (MWF)
    q3_cols = [f"Q3_{i}" for i in range(1, 7)]           # Q3_1..Q3_6  (TR)
    q4_col = ["Q4"]
    q5_col = ["Q5"]

    all_cols = (
        filler_front
        + last_name_col
        + filler_mid
        + q1_cols
        + q2_cols
        + q3_cols
        + q4_col
        + q5_col
    )
    # Total columns = 9 + 1 + 7 + 4 + 9 + 6 + 1 + 1 = 38

    def make_row(last_name, q1, q2, q3, q4):
        """
        q1 = list of 4 values (MATH301,302,401,402 rankings, 0 = not ranked)
        q2 = list of 9 MWF rankings (0 = not ranked)
        q3 = list of 6 TR  rankings (0 = not ranked)
        q4 = int
        """
        row = (
            [""] * 9          # filler front
            + [last_name]
            + [""] * 7        # filler mid
            + q1
            + q2
            + q3
            + [q4]
            + [""]            # Q5
        )
        return row

    dummy_row = make_row("", [0]*4, [0]*9, [0]*6, 0)

    # Smith: MWF  — ranks MATH301=1, MATH302=2, MATH401=3, MATH402=0
    #               MWF slots 1-9 (ranks 1..9), TR slots all 0; Q4=3
    smith_q2 = list(range(1, 10))   # [1,2,3,4,5,6,7,8,9]
    smith_q3 = [0] * 6
    smith_row = make_row("Smith", [1, 2, 3, 0], smith_q2, smith_q3, 3)

    # Jones: TR   — ranks MATH302=1, MATH401=2, MATH402=3, MATH301=0
    #               TR slots 1-6, MWF slots all 0; Q4=3
    jones_q2 = [0] * 9
    jones_q3 = list(range(1, 7))    # [1,2,3,4,5,6]
    jones_row = make_row("Jones", [0, 1, 2, 3], jones_q2, jones_q3, 3)

    # Brown: MWF  — ranks MATH401=1, MATH301=2, MATH302=3, MATH402=0
    #               MWF slots 1-9, TR slots all 0; Q4=2 (negative → -1)
    brown_q2 = list(range(1, 10))
    brown_q3 = [0] * 6
    brown_row = make_row("Brown", [2, 3, 1, 0], brown_q2, brown_q3, 2)

    df = pd.DataFrame(
        [dummy_row, smith_row, jones_row, brown_row],
        columns=all_cols,
    )

    path = os.path.join(HERE, "preferences_test.xlsx")
    df.to_excel(path, index=False)
    print(f"Created {path}")


# ---------------------------------------------------------------------------
# rooms_test.xlsx
# ---------------------------------------------------------------------------

def create_rooms():
    """
    Columns: day, time, room, cap

    3 MWF timeslots × 2 rooms + 2 TR timeslots × 2 rooms = 10 rows.
    The loader does: combined = day.replace(' ','') + ' ' + time, then sorts
    by TIME_LIST ordering.

    TIME_LIST entries (from config.py):
      'MWF 09:00 AM-09:50 AM', 'MWF 10:00 AM-10:50 AM', 'MWF 11:00 AM-11:50 AM', ...
      'TR 09:00 AM-10:15 AM',  'TR 10:30 AM-11:45 AM', ...

    The loader strips spaces from the day column then concatenates with time:
        df["combined"] = df["day"].str.replace(" ", "") + " " + df["time"]
    So for 'MWF' day and '09:00 AM-09:50 AM' time → 'MWF 09:00 AM-09:50 AM'
    """
    mwf_times = [
        "09:00 AM-09:50 AM",
        "10:00 AM-10:50 AM",
        "11:00 AM-11:50 AM",
    ]
    tr_times = [
        "09:00 AM-10:15 AM",
        "10:30 AM-11:45 AM",
    ]
    rooms_large = "RoomA"   # cap=35  (fits all courses)
    rooms_small = "RoomB"   # cap=35  (also fits all courses)

    rows = []
    for t in mwf_times:
        rows.append({"day": "MWF", "time": t, "room": rooms_large, "cap": 35})
        rows.append({"day": "MWF", "time": t, "room": rooms_small, "cap": 35})
    for t in tr_times:
        rows.append({"day": "TR", "time": t, "room": rooms_large, "cap": 35})
        rows.append({"day": "TR", "time": t, "room": rooms_small, "cap": 35})

    df = pd.DataFrame(rows)
    path = os.path.join(HERE, "rooms_test.xlsx")
    df.to_excel(path, index=False)
    print(f"Created {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    create_professors()
    create_courses()
    create_preferences()
    create_rooms()
    print("All fixture files created successfully.")
