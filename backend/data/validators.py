"""Input sanity checks for scheduling data."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from data.loaders import SchedulingDataRepository


def validate_loads(repository: "SchedulingDataRepository") -> None:
    """
    Raise ValueError if any professor's pre-assigned sections exceed their load.
    """
    assigned_dict = repository.assigned_dict
    load_dict = repository.load_dict

    prof_preassigned_count: dict[str, int] = defaultdict(int)
    for prof, courses_map in assigned_dict.items():
        for sections in courses_map.values():
            prof_preassigned_count[prof] += len(sections)

    for prof, count in prof_preassigned_count.items():
        required = load_dict.get(prof, 0)
        if count > required:
            raise ValueError(
                f"Professor {prof} has more pre-assignments ({count}) "
                f"than required load ({required})"
            )


def normalize_weights(preferences_df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure preference rows are correctly normalized.
    This is a pass-through if the data was already normalized by the loader.
    Rows that do not sum to 1 (ignoring zeros) are left as-is — normalization
    happens during loading via the rank-weight formula.
    """
    return preferences_df.copy()
