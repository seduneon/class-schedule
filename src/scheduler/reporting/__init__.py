"""Reporting (SPEC L6): Excel workbook, static HTML grid, JSON solution."""

from scheduler.io.writers import solution_to_dict, write_solution
from scheduler.reporting.excel import timetable_rows, write_excel_report
from scheduler.reporting.html import render_html

__all__ = [
    "render_html",
    "solution_to_dict",
    "timetable_rows",
    "write_excel_report",
    "write_solution",
]
