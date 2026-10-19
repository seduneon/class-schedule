# medium_no_recitations

Copy of `data/examples/medium` without recitations: every `section_type = R` row is removed from
`offerings.csv` and `course_preferences.csv` (rows with a blank type apply to the
remaining lectures as before). All other files are unchanged copies.

Purpose: test whether the room shortage in `medium` comes from the 26 recitation
sections (MATH161 R x8, MATH162 R x15, MATH263 R x1, MATH273 R x2).
