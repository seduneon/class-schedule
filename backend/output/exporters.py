"""Export formatted DataFrames to .xlsx files."""

from __future__ import annotations

import pandas as pd


def export_phase1(df: pd.DataFrame, path: str) -> None:
    """Write Phase 1 output DataFrame to an Excel file."""
    df.to_excel(path, index=False)


def export_phase2(df: pd.DataFrame, path: str) -> None:
    """Write Phase 2 output DataFrame to an Excel file."""
    df.to_excel(path, index=False)
