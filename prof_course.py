from pulp import *
import pandas as pd
import numpy as np
from collections import defaultdict

professor = pd.read_excel("professors_new1.xlsx")
courses = pd.read_excel("courses_new2.xlsx")
preferences = pd.read_excel("preferences1.xlsx")

professor.drop(columns=['email'], inplace=True)
courses.drop(columns=['Course_title'], inplace=True)
course_list = courses['Course_code'].unique()


# preferences: dropping unneecesary data
drop = preferences.columns[:9]
preferences.drop(columns=drop, inplace=True)
drop = preferences.columns[1:8]
preferences.drop(columns=drop, inplace=True)
preferences.drop(index=0, inplace=True)


new_columns = []
new_name_index = 0

# preferences: renaming columns with course names
for col in preferences.columns:
    if col.startswith('Q1'):
        # Replace the column name with the corresponding value from the list
        new_columns.append(course_list[new_name_index])
        new_name_index += 1
    else:
        # Keep the existing column name
        new_columns.append(col)

preferences.columns = new_columns


# 1) Normalize (optional): trim spaces and turn empty strings into NaN
preferences['RecipientLastName'] = (
    preferences['RecipientLastName'].astype('string').str.strip()
)
preferences['RecipientLastName'].replace('', pd.NA, inplace=True)

# 2) Drop rows where the name is NaN
preferences = preferences.dropna(subset=['RecipientLastName'])

# 3) Keep only the last occurrence of each last name (based on current row order)
preferences = preferences.drop_duplicates(subset=['RecipientLastName'], keep='last')

# course_preferences = preferences.iloc[:, 0:30]
course_preferences = preferences[['RecipientLastName']].join(
    preferences.filter(regex=r'^MATH')
)
course_preferences = course_preferences.fillna(0)
course_preferences.reset_index(drop=True, inplace=True)

# top n and weighting
top_n = 5
row_sum = top_n * (top_n + 1) / 2  # = 15 when top_n=5

# Work only on the MATH columns (all except the first col which is RecipientLastName)
C = course_preferences.iloc[:, 1:].apply(pd.to_numeric, errors='coerce').fillna(0)

# 1) Any rank > top_n -> 0
C = C.mask(C > top_n, 0)

# 2) Convert remaining ranks r (1..top_n) to weights: (top_n+1 - r) / row_sum; keep zeros as 0
C = ((top_n + 1 - C) / row_sum).where(C != 0, 0)

# Put back
course_preferences.iloc[:, 1:] = C

# professor list
professors_list = course_preferences["RecipientLastName"].tolist()

# set lastname as index not column name
course_preferences.set_index(course_preferences.columns[0], inplace=True)

# professor df cleaning part

professor['Professor'] = professor['second_name']
prof_fullname_df = professor[['first_name', 'second_name']].copy()
professor.drop(columns = ['first_name', 'second_name'], inplace=True)
columns = ['Professor'] + [col for col in professor.columns if col != 'Professor']
professor = professor[columns]


# load dictionary
load = professor.iloc[:, [0, 1]].copy()
load['Professor'] = professors_list
load_dict = load.groupby('Professor')['load'].sum().to_dict()

# course section dictionary
section_number = courses.drop(['Section_type', 'Capacity'], axis = 1)
section_number = section_number.groupby('Course_code', as_index=False)['Section_number'].max()
section_number.rename(columns={'Section_number': 'Total_sections'}, inplace=True)
course_dict = section_number.groupby('Course_code')['Total_sections'].sum().to_dict()

# dictionary: total load (sum of weights) per Course_code
w_by_course = (
    courses.set_index("Course_code")["Section_type"]
           .str.strip().str.upper()
           .map({"L": 1.0, "R": 0.5})
           .to_dict()
)

print(course_dict)

# preferred course list
preferred_courses_for_professors = {
    professor_i: course_preferences.columns[(row != 0).values].tolist()
    for professor_i, row in course_preferences.iterrows()
}


# course list
course_list = section_number["Course_code"].tolist()

# two section preference
two_section_preference = preferences.iloc[:, [0, -2]].copy()
val_col = two_section_preference.columns[-1]
two_section_preference[val_col] = pd.to_numeric(two_section_preference[val_col], errors='coerce')
mapping = {1: 1, 2: -1, 3: 0}
two_section_preference[val_col] = two_section_preference[val_col].map(mapping).fillna(
    two_section_preference[val_col]
)
two_section_preference.set_index(two_section_preference.columns[0], inplace=True)


# multiply the weights to the course points
modified_preferences = course_preferences.copy()
points = professor.iloc[:, [0, 2]]
points.set_index(points.columns[0], inplace=True)
modified_preferences = modified_preferences.multiply(points["course_points"], axis=0)
modified_preferences = modified_preferences / 100


# pre assigned prof-course dictionary
assigned_df = professor.drop(columns=['load', 'course_points', 'time_points'])
assigned_dict = {}

for _, row in assigned_df.iterrows():
    professor_one_time = row["Professor"]
    courses_one_time = {}
    for i in range(1, 5):
        course_col = f"course{i}"
        section_col = f"section{i}"
        course = row[course_col]
        section = row[section_col]
        if pd.notna(course) and pd.notna(section):
            if course not in courses_one_time:
                courses_one_time[course] = []
            courses_one_time[course].append(int(section))
    if courses_one_time:
        assigned_dict[professor_one_time] = courses_one_time

# pre-assigned section number for each professor
professor_sections = {}

for professor_j, courses_i in assigned_dict.items():
    total_sections = sum(len(sections) for sections in courses_i.values())
    professor_sections[professor_j] = total_sections

# update load dict
updated_load = {}

for prof, total in load_dict.items():
    used = professor_sections.get(prof, 0)  # default to 0 if not in assigned_sections
    updated_load[prof] = total - used


def merge_dicts(dict1, dict2):
    merged = {}

    # Add entries from the first dictionary
    for prof, courses in dict1.items():
        if prof not in merged:
            merged[prof] = {}
        for course, sections in courses.items():
            if course not in merged[prof]:
                merged[prof][course] = []
            merged[prof][course].extend(sections)

    # Add entries from the second dictionary
    for prof, courses in dict2.items():
        if prof not in merged:
            merged[prof] = {}
        for course, sections in courses.items():
            if course not in merged[prof]:
                merged[prof][course] = []
            merged[prof][course].extend(sections)

    return merged


assigned_dict = {
    professor_x: {course: [x - 1 for x in sections] for course, sections in courses.items()}
    for professor_x, courses in assigned_dict.items()
}

print(assigned_dict)


# LinProg for Course Assigning
prob = LpProblem("Professor_Course_Assignment", LpMaximize)
# pre-assignments
assigned_slots = set()
prof_preassigned_count = defaultdict(int)
course_preassigned_count = defaultdict(int)

for prof in assigned_dict:
    for course_one_time in assigned_dict[prof]:
        sections_one_time = assigned_dict[prof][course_one_time]
        prof_preassigned_count[prof] += len(sections_one_time)
        course_preassigned_count[course_one_time] += len(sections_one_time)
        for section_one_time in sections_one_time:
            assigned_slots.add((prof, course_one_time, section_one_time))

for prof in professors_list:
    if prof_preassigned_count[prof] > load_dict[prof]:
        raise ValueError(f"Professor {prof} has more pre-assignments ({prof_preassigned_count[prof]}) "
                       f"than required load ({load_dict[prof]})")

# Decision variable

# x[i, j, k] - professor i teaches section k of course j
x = LpVariable.dicts("assigned", ((i, j, k) for i in professors_list for j in course_list for k in range(course_dict[j]) if (i, j, k) not in assigned_slots) , cat="Binary")

# y[i, j] - professor i teaches multiple sections of course j
y = LpVariable.dicts("multiple_sections", ((i, j) for i in professors_list for j in course_list))

# Relaxation variables
p = LpVariable.dicts("prof_relax", professors_list, lowBound=0)
s = LpVariable.dicts("section_relax", course_list, lowBound=0)
r = LpVariable.dicts("preferred_relax", professors_list, lowBound=0)
q = LpVariable.dicts("multi_section_relax",
                     ((i, j) for i in professors_list
                      for j in course_list
                      if two_section_preference.loc[i, two_section_preference.columns[0]] == -1),
                     lowBound=0)

# Helper function to count total assignments for a professor (new + assigned)

# for a professor
def get_total_assignments(prof):
    pre = prof_preassigned_count[prof]
    new = lpSum(w_by_course[j] * x[prof,j,k] for j in course_list for k in range(course_dict[j]) if (prof,j,k) not in assigned_slots)
    return pre + new

# for a course

def get_course_assignments(course):
    pre = course_preassigned_count[course]
    new = lpSum(x[i,course,k] for i in professors_list for k in range(course_dict[course]) if (i,course,k) not in assigned_slots)
    return pre + new

def get_prof_course_assignments(prof, course):
    pre = len(pre_assignments.get(prof, {}).get(course, []))
    new = lpSum(x[prof,course,k] for k in range(load_dict[course]) if (prof,course,k) not in assigned_slots)
    return pre + new


# sum of not preferred = 0

def get_non_preferred_assignments(prof):
    new = lpSum(x[prof,j,k]
               for j in course_list if j not in preferred_courses_for_professors[prof]
               for k in range(course_dict[j])
               if (prof,j,k) not in assigned_slots)
    return new


# sum of preferred section = professors load

def get_preferred_assignments(prof):
    pre = sum(len(sections)
              for course, sections in assigned_dict.get(prof, {}).items()
              if course in preferred_courses_for_professors[prof])

    # Count new preferred sections
    new = lpSum(x[prof, j, k]
                for j in preferred_courses_for_professors[prof]
                for k in range(course_dict[j])
                if (prof, j, k) not in assigned_slots)
    return pre + new

# Objective function

prob += (
    # Original preference maximization with modified preferences
    lpSum(modified_preferences.loc[i,j]*x[i,j,k]
            for i in professors_list
            for j in course_list
            for k in range(course_dict[j])
            if (i, j, k) not in assigned_slots)
            # Original relaxation penalties
            -5*lpSum(p[i] for i in professors_list)
            -5*lpSum(s[j] for j in course_list)
            -5*lpSum(r[i] for i in professors_list)
            # New multi-section relaxation penalty
            -5*lpSum(q[i,j]
                        for i in professors_list
                        for j in course_list
                       if two_section_preference.loc[i, two_section_preference.columns[0]] == -1)
)


# Constraints

print(course_dict)

# Each section taught only by 1 professor

for j in course_list:
    for k in range(course_dict[j]):
        if not any((p, j, k) in assigned_slots for p in professors_list):
            prob += lpSum(x.get((i, j, k), 0) for i in professors_list
                        if (i, j, k) not in assigned_slots) <= 1

# Each professor teaches their load sections with relaxation

for i in professors_list:
    prob += get_total_assignments(i) + p[i] == load_dict[i]

# Each course must have all sections assigned with relaxation

for j in course_list:
    prob += get_course_assignments(j) + s[j] == course_dict[j]

# Professor must teach course which is in his preference

for i in professors_list:
    prob += get_preferred_assignments(i) + r[i] == load_dict[i]

# Professor cannot teach course which is not in his preference

for i in professors_list:
        prob += get_non_preferred_assignments(i) == 0

print(two_section_preference)

# there should be Q4 constraint
for i in professors_list:
    if two_section_preference.loc[i, two_section_preference.columns[0]] == -1:
        for j in course_list:
            # Sum of all sections for each course should be <= 1 (plus relaxation)
            prob += (lpSum(x.get((i,j,k), 0)
                         for k in range(course_dict[j])
                         if (i,j,k) not in assigned_slots)
                    + q[i,j] <= 1)


# Solving part

status = prob.solve(pulp.PULP_CBC_CMD(msg=True, options=['dual']))
print(f"Number of Variables: {len(prob.variables())}")
print(f"Number of Constraints: {len(prob.constraints)}")

assignments = []

for prof in assigned_dict:
        for course in assigned_dict[prof]:
            sections = assigned_dict[prof][course]
            assignments.append({
                'Professor': prof,
                'Course': course,
                'Sections': sections,
                'Number_of_Sections': len(sections),
                'Preference_Weight': course_preferences.loc[prof, course],
                'Status': 'Pre-assigned'
            })

prof_total_sections = defaultdict(int)
for prof in assigned_dict:
    prof_total_sections[prof] = sum(len(sections) for sections in assigned_dict[prof].values())

for i in professors_list:
    for j in course_list:
        new_sections = []
        for k in range(course_dict[j]):
            if (i, j, k) not in assigned_slots and \
                    x.get((i, j, k)) and value(x[i, j, k]) == 1:
                new_sections.append(k)

        if new_sections:
            prof_total_sections[i] += len(new_sections)
            assignments.append({
                'Professor': i,
                'Course': j,
                'Sections': new_sections,
                'Number_of_Sections': len(new_sections),
                'Preference_Weight': course_preferences.loc[i, j],
                'Teaching_Multiple': value(y[i, j]) == 1,
                'Status': 'New'
            })

for prof in professors_list:
    if prof_total_sections[prof] > load_dict[prof]:
        print(f"Warning: Professor {prof} assigned {prof_total_sections[prof]} sections "
              f"but required only {load_dict[prof]}")

unassigned_profs = [i for i in professors_list if value(p[i]) > 0]
num_sections_unassigned_prof = [value(p[i]) for i in professors_list if value(p[i]) > 0]
unfilled_courses = [j for j in course_list if value(s[j]) > 0]
num_sections_unassigned_courses = [value(s[j]) for j in course_list if value(s[j]) > 0]

answer = {
        'status': LpStatus[status],
        'objective_value': value(prob.objective),
        'assignments': pd.DataFrame(assignments),
        'unassigned_professors': unassigned_profs,
        'unfilled_courses': unfilled_courses,
        'professor_loads': dict(prof_total_sections)
    }

print("\n")
print(f'Number of total unassigned section for professors = {sum(num_sections_unassigned_prof)}')
# Encoded
new_list = [s for s in answer["unassigned_professors"]]
print("Unassigned Professors:", unassigned_profs)
# Not encoded
#print("Unassigned Professors:", answer['unassigned_professors'])
print("Unassigned professors section amount: ", num_sections_unassigned_prof)

print("\n")
print(f'Number of total unassigned section for courses = {sum(num_sections_unassigned_courses)}')
print("Unfilled Courses:", answer['unfilled_courses'])
print("Unassigned Courses section amount: ", num_sections_unassigned_courses)

# cleaning and modifying output
result = pd.DataFrame(answer['assignments'])

# adding 1 to section
result['Sections'] = result['Sections'].apply(lambda x: [i + 1 for i in x])

# sort in specific way
result['Professor'] = pd.Categorical(result['Professor'], categories=professors_list, ordered=True)

# adding 2 section preference
result['Two_Section_Preference'] = result['Professor'].map(
    lambda x: two_section_preference.loc[x, two_section_preference.columns[0]]
)

# courses df cleaning
courses.rename(columns={"Section_number": "Sections", "Course_code": "Course"}, inplace=True)
#courses['Sections'] = courses['Sections'] +1
courses.drop(columns=['Section_type'], inplace=True)

# dropping unnecessary columns
result.drop(columns=['Number_of_Sections', 'Preference_Weight', 'Status', 'Teaching_Multiple', 'Two_Section_Preference'], inplace=True)
result = result.explode("Sections", ignore_index=True)
result = pd.merge(result, courses, on=['Course', 'Sections'], how='left')
#result.to_excel('solution.xlsx', index=False)

# part 1 output cleaning
part_1_output = result.copy()
part_1_output['Sections'] = part_1_output['Sections'].astype(str) + 'L'

#assignments_df_clean.merge(prof_fullname_df, how='left', on=assignments_df_clean[professor])
part_1_output = part_1_output.rename(columns={'Professor': 'second_name'})
part_1_output = part_1_output.merge(prof_fullname_df, on='second_name', how='left')
part_1_output['Professor'] = part_1_output['first_name'] + ' ' + part_1_output['second_name']
part_1_output = part_1_output.drop(columns = ['first_name', 'second_name'])

part_1_output = part_1_output.rename(columns={'course': 'Course', 'Sections': 'Section', 'capacity': 'Capacity'})
part_1_output = part_1_output[['Professor', 'Course', 'Section', 'Capacity']]

modified_preferences.reset_index(inplace=True)
modified_preferences.rename(columns={'index': 'RecipientLastName'}, inplace=True)  # Just in case

# Convert df2 from wide format to long format
preferences_long = modified_preferences.melt(id_vars=["RecipientLastName"], var_name="Course", value_name="Weight")

popo = preferences_long[preferences_long["Weight"] != 0]
part_1_output["LastName"] = part_1_output["Professor"].apply(lambda x: x.split()[-1])

part_1_output_merged = part_1_output.merge(popo, left_on=['LastName', 'Course'], right_on=['RecipientLastName', 'Course'], how='left')
part_1_output_merged.loc[:,'Weight'] = part_1_output_merged['Weight'].round(2)
# Drop extra columns and fill NaN weights with 0
part_1_output_merged.drop(columns=['RecipientLastName', 'LastName'], inplace=True)
weight_to_rank = {'0.33': 1, '0.27': 2, '0.2': 3, '0.13': 4, '0.07': 5}
part_1_output_merged['Ranking'] = part_1_output_merged['Weight'].astype(str).map(weight_to_rank)
part_1_output_merged.drop(columns=['Weight'], inplace=True)

part_1_output_merged.to_excel('solution.xlsx', index=False)
# part_1_output_merged.sort_values("Professor")


part_1_output_merged.sort_values("Course")
print(part_1_output_merged.sort_values("Professor"))

# ------------PART 2-------------

time_room_df = pd.read_excel("time_room1.xlsx")

time_room_df['day_time'] = time_room_df['day'] + ' ' +time_room_df['time']
time_room_df['combined'] = time_room_df['day'].str.replace(' ', '') + ' ' + time_room_df['time']
time_room_df.drop(columns = ['day', 'time'], inplace=True)
time_room_df = time_room_df[['combined', 'room', 'cap']]
time_room_df.rename(columns={'combined': 'day_time'}, inplace=True)

# rename the column names

time_list = ['MWF 09:00 AM-09:50 AM', 'MWF 10:00 AM-10:50 AM', 'MWF 11:00 AM-11:50 AM', 'MWF 12:00 PM-12:50 PM', 'MWF 01:00 PM-01:50 PM', 'MWF 02:00 PM-02:50 PM', 'MWF 03:00 PM-03:50 PM', 'MWF 04:00 PM-04:50 PM', 'MWF 05:00 PM-05:50 PM',
             'TR 09:00 AM-10:15 AM', 'TR 10:30 AM-11:45 AM', 'TR 12:00 PM-01:15 PM', 'TR 01:30 PM-02:45 PM', 'TR 03:00 PM-04:15 PM', 'TR 04:30 PM-05:45 PM']

new_columns = []
new_name_index = 0
drop_cols = []
for col in preferences.columns:
    if col.startswith('Q2') or col.startswith('Q3'):
        # Replace the column name with the corresponding value from the list
        new_columns.append(time_list[new_name_index])
        new_name_index += 1
    elif col.startswith('MATH'):
        drop_cols.append(col)
    elif col.startswith('Q5') or col.startswith('Q4'):
        drop_cols.append(col)
    else:
        # Keep the existing column name
        new_columns.append(col)
#drop_cols.append('Q4')
preferences.drop(columns = drop_cols, inplace=True)
preferences.columns = new_columns

# getting only day time weights
day_time_weights = preferences.iloc[:, :].copy()

# top_n_time = 15
# row_sum_time = (top_n_time*(top_n_time+1))/2
# day_time_weights = day_time_weights.copy()
#
# # old
# #day_time_weights.iloc[:, 1:] = day_time_weights.iloc[:, 1:].applymap(lambda x: 2 ** (top_n_time - x) if x != 0 else 0)
# # new
# day_time_weights.iloc[:, 1:] = day_time_weights.iloc[:, 1:].map(lambda x: (top_n_time+1-x)/row_sum_time if x != 0 else 0)

top_n_time = 15
row_sum_time = top_n_time * (top_n_time + 1) / 2

d = day_time_weights.iloc[:, 1:]  # the numeric rank columns
day_time_weights.iloc[:, 1:] = ((top_n_time + 1 - d) / row_sum_time).where(d != 0, 0)

dtw = day_time_weights.copy().set_index('RecipientLastName')
prof_df = professor.copy()

print(prof_df)
# align flags
prof_df['Professor'] = prof_df['Professor'].astype(str).str.strip()
flag = prof_df.set_index('Professor')['MWForTR'].reindex(dtw.index)
if flag.isna().any():
    missing = dtw.index[flag.isna()].unique().tolist()
    raise KeyError(f"No MWForTR found for: {missing}")
flag = flag.astype(int)

# masks now built over *all* columns (since index holds names)
ucols = dtw.columns.str.upper()
mwf_mask  = ucols.str.startswith('MWF')            # <- starts with True if first time col is MWF
tuth_mask = ucols.str.startswith('TR') | ucols.str.startswith('TW') | ucols.str.startswith('TTH')

# ensure numeric
dtw.loc[:, mwf_mask | tuth_mask] = dtw.loc[:, mwf_mask | tuth_mask].apply(pd.to_numeric, errors='coerce').fillna(0)

# row boolean masks
keep_mwf = (flag == 1)
keep_tr  = (flag == 0)

# zero out
dtw.loc[keep_mwf, tuth_mask] = -100
dtw.loc[keep_tr,  mwf_mask]  = -100

# put the name column back if you prefer the original shape
day_time_weights = dtw.reset_index()

print(day_time_weights)

day_time_weights.rename(columns={"RecipientLastName": "Professor"}, inplace=True)

# Multiply to the points

time_points = professor.iloc[:, [0, 3]]
time_points = time_points.copy()
time_points['time_points'] = time_points['time_points']/100
day_time_weights = day_time_weights.merge(time_points, on='Professor')

cols_to_multiply = day_time_weights.columns.difference(['Professor'])
day_time_weights[cols_to_multiply] = day_time_weights[cols_to_multiply].mul(day_time_weights['time_points'], axis=0)
day_time_weights.drop(columns=['time_points'], inplace=True)

# lists
day_time_weights.set_index('Professor', inplace=True)


def get_course_level(course_name):
    """Extract course level (300 or 400) from course name."""
    match = re.search(r'(\d{3})', course_name)
    if match:
        level = int(match.group(1))
        if level >= 300 and level < 400:
            return 300
        elif level >= 400 and level < 500:
            return 400
        elif level >= 500:
            return 500
    return None

# data preparation part

professor_course_df = result
# professor_course_df = pd.read_excel("solution.xlsx")
professor_course_df.rename(columns={'Professor':'professor', 'Course':'course', 'Capacity':'capacity', 'Sections':'section'}, inplace=True)
professor_course_df = professor_course_df.reset_index()



gap_preference_df = preferences[['RecipientLastName', 'Q6']]
mapping = {1: 'positive', 2: 'negative', 3: 'neutral'}
gap_preference_df = gap_preference_df.rename(columns = {'RecipientLastName': 'professor'})
gap_preference_df['Q6'] = gap_preference_df['Q6'].map(mapping)

# len1 = len(gap_preference_df)
# len1 = 3 * len1 // 4
# random_change = np.random.choice(gap_preference_df.index, size=len1, replace=False)
# gap_preference_df.loc[random_change, 'Q6'] = 'negative'

time_preference_df = day_time_weights
time_room_df.rename(columns={'day_time':'timeslot', 'cap':'room_capacity'}, inplace=True)
gap_preference_df = gap_preference_df.replace({'positive': 1, 'neutral': 0, 'negative': -1})
new = pd.merge(professor_course_df, gap_preference_df, on='professor', how='left')
timeslot_pairs_list = [
    (time_list[i], time_list[i + 1])
    for i in range(len(time_list) - 1)
    if time_list[i].split()[0] == time_list[i + 1].split()[0]
]

time_room_df['timeslot'] = pd.Categorical(time_room_df['timeslot'], categories=time_list, ordered = True)
time_room_df_sorted = time_room_df.sort_values(by='timeslot')
#time_room_df_sorted['timeslot'].value_counts()


time_room_df_sorted = time_room_df_sorted.reset_index()
time_room_df_sorted.drop(columns=['index'], inplace=True)
#time_room_df_sorted

# with pd.option_context('display.max_rows', None, 'display.max_columns', None):
#     print(time_room_df_sorted)          # or: display(df) in Jupyter

lastnames = new[['index', 'professor']]
lastname_groups = lastnames.groupby('professor')['index'].apply(list).tolist()
#lastname_groups

# linear programm function


def create_course_schedule_q3(prof_courses_df, timeslots_df, prof_preferences_df):
    prob = LpProblem("Course_Scheduling", LpMaximize)

    # Create sets for indices
    courses = prof_courses_df.index.tolist()
    timeslots = timeslots_df.index.tolist()
    professors = prof_courses_df['professor'].unique().tolist()

    # new
    time_groups = timeslots_df.groupby('timeslot', observed=True).apply(lambda x: x.index.tolist()).to_dict()

    # Get course information
    course_levels = {c: get_course_level(prof_courses_df.loc[c, 'course'])
                     for c in courses}
    base_courses = {c: prof_courses_df.loc[c, 'course']
                    for c in courses}
    course_sections = {c: prof_courses_df.loc[c, 'section']
                       for c in courses}

    # Create full course identifiers (course + section)
    full_course_ids = {c: f"{base_courses[c]}-{course_sections[c]}"
                       for c in courses}

    # Group courses by level
    courses_300 = [c for c in courses if course_levels[c] == 300]
    courses_400 = [c for c in courses if course_levels[c] == 400]
    courses_500 = [c for c in courses if course_levels[c] == 500]

    # Calculate big-M constant
    M = 2 * timeslots_df['room_capacity'].max()

    # Decision variables
    x = LpVariable.dicts("schedule",
                         ((c, t) for c in courses for t in timeslots),
                         cat='Binary')

    # Slack variables for capacity constraints
    slack = LpVariable.dicts("slack",
                             (c for c in courses),
                             lowBound=0,
                             cat='Binary')

    # Objective function
    objective = 0

    # Add professor preferences to objective
    for c in courses:
        professor1 = prof_courses_df.loc[c, 'professor']
        for t in timeslots:
            timeslot = timeslots_df.loc[t, 'timeslot']
            preference_weight = prof_preferences_df.loc[professor1, timeslot]
            objective += preference_weight * x[c, t]

    # Add course scheduling and slack terms
    objective += lpSum(x[c, t] for c in courses for t in timeslots) - \
                 100 * lpSum(slack[c] for c in courses)

    prob += objective

    # 1. Each course section must be scheduled exactly once or use slack
    for c in courses:
        prob += lpSum(x[c, t] for t in timeslots) + slack[c] == 1

    # 2. Room capacity constraint with slack
    for c in courses:
        for t in timeslots:
            room = timeslots_df.loc[t, 'room']
            room_capacity = timeslots_df.loc[t, 'room_capacity']
            course_capacity = prof_courses_df.loc[c, 'capacity']

            # prob += course_capacity * x[c, t] <= room_capacity + M * slack[c]
            prob += course_capacity * x[c, t] <= room_capacity

    # 3. No room double-booking
    # for t in timeslots:
    #     for c in courses:
    #         prob += x[c, t] <= 1

    for t in timeslots:
        prob += lpSum(x[c, t] for c in courses) <= 1

    # 4. No professor double-booking
    for p in professors:
        prof_courses = prof_courses_df[prof_courses_df['professor'] == p].index
        for time_period, time_indices in time_groups.items():
            prob += lpSum(x[c, t] for c in prof_courses for t in time_indices) <= 1

    # 5. Modified constraint: Only one 300-level course can be taught at any given time
    for time_period, time_indices in time_groups.items():
        prob += lpSum(x[c, t] for c in courses_300 for t in time_indices) <= 1

    # 6. Allow different sections of same 400-level course at the same time
    for time_period, time_indices in time_groups.items():
        prob += lpSum(x[c, t] for c in courses_400 for t in time_indices) <= 1

    # 7. Allow different sections of same 500-level course at the same time
    for time_period, time_indices in time_groups.items():
        prob += lpSum(x[c, t] for c in courses_500 for t in time_indices) <= 1

    # Solve the problem
    prob.solve()
    print(f"Number of Variables: {len(prob.variables())}")
    print(f"Number of Constraints: {len(prob.constraints)}")
    # Process results
    if LpStatus[prob.status] == 'Optimal':
        # Create assignments dataframe
        assignments = []
        used_timeslots = set()  # Track which timeslots are used

        for c in courses:
            if value(slack[c]) < 0.5:  # Course was scheduled (not using slack)
                for t in timeslots:
                    if value(x[c, t]) > 0.5:
                        professor = prof_courses_df.loc[c, 'professor']
                        timeslot = timeslots_df.loc[t, 'timeslot']
                        room = timeslots_df.loc[t, 'room']
                        preference = prof_preferences_df.loc[professor, timeslot]

                        # Add to assignments
                        assignments.append({
                            'course': base_courses[c],
                            'section': course_sections[c],
                            'course_with_section': full_course_ids[c],
                            'course_level': course_levels[c],
                            'professor': professor,
                            'timeslot': timeslot,
                            'room': room,
                            'course_capacity': prof_courses_df.loc[c, 'capacity'],
                            'room_capacity': timeslots_df.loc[t, 'room_capacity'],
                            'professor_preference': preference
                        })

                        # Track used timeslot
                        used_timeslots.add((room, timeslot))

        assignments_df = pd.DataFrame(assignments)

        # Get unscheduled courses (using slack)
        unscheduled = [full_course_ids[c]
                       for c in courses if value(slack[c]) > 0.5]

        # Create unassigned slots dataframe
        unassigned_slots = []
        for _, row in timeslots_df.iterrows():
            if (row['room'], row['timeslot']) not in used_timeslots:
                unassigned_slots.append({
                    'room': row['room'],
                    'timeslot': row['timeslot'],
                    'room_capacity': row['room_capacity']
                })

        unassigned_slots_df = pd.DataFrame(unassigned_slots)

        return 'Optimal', assignments_df, unscheduled, unassigned_slots_df

    return 'No solution found', None, None, None

# Run the optimization
# with pd.option_context('display.max_rows', None, 'display.max_columns', None):
#     print(time_preference_df)          # or: display(df) in Jupyter

status, assignments_df, unscheduled, unassigned_time_slots = create_course_schedule_q3(
    professor_course_df,
    time_room_df,
    time_preference_df
)

if status == 'Optimal':
    if unscheduled:
        print("\nUnscheduled Courses (No suitable rooms):")
        print(unscheduled)
        print("\nUnassigned timeslots with rooms:")
        print(unassigned_time_slots)
    else:
        print("\nEvery class was scheduled")
else:
    print("No feasible solution found")

assignments_df_clean = assignments_df.drop(columns = ['course', 'section', 'course_level', 'course_capacity', 'room_capacity'])
assignments_df_clean['professor_preference'] = assignments_df_clean['professor_preference'] * row_sum_time
assignments_df_clean['professor_preference'] = top_n_time + 1 - assignments_df_clean['professor_preference']
#assignments_df_clean['professor'] = assignments_df_clean['professor'].str[:2]
assignments_df_clean.to_csv("output2.xlsx")

assignments_df_clean = assignments_df_clean.sort_values(by=['course_with_section'])

assignments_df_clean['Section'] = assignments_df_clean['course_with_section'].str.extract(r'(\d+)(?!.*\d)')
assignments_df_clean['course_with_section'] = assignments_df_clean['course_with_section'].str[:-2]

#assignments_df_clean.merge(prof_fullname_df, how='left', on=assignments_df_clean[professor])
assignments_df_clean = assignments_df_clean.rename(columns={'professor': 'second_name'})
assignments_df_clean = assignments_df_clean.merge(prof_fullname_df, on='second_name', how='left')
assignments_df_clean['Professor'] = assignments_df_clean['first_name'] + ' ' + assignments_df_clean['second_name']
assignments_df_clean = assignments_df_clean.drop(columns = ['first_name', 'second_name'])

assignments_df_clean['Section'] = assignments_df_clean['Section'] + 'L'
assignments_df_clean = assignments_df_clean.rename(columns={'course_with_section': 'Course', 'timeslot': 'Time', 'room': 'Room', 'professor_preference': 'Time Preference'})

assignments_df_clean = assignments_df_clean[['Professor', 'Course', 'Section', 'Time', 'Room', 'Time Preference']]
assignments_df_clean.to_excel("output_part_2.xlsx")
professor_mapping_2 = {prof: f"Professor {i+1}" for i, prof in enumerate(assignments_df_clean["Professor"].unique())}
assignments_df_clean["Professor"] = assignments_df_clean["Professor"].map(professor_mapping_2)
pd.set_option('display.max_columns', None)
print(assignments_df_clean.sort_values(by=['Course']))
