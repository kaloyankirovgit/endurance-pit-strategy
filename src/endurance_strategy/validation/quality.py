"""Structural data-quality checks for WEC race data.
"""

from __future__ import annotations

import pandas as pd

LAP_KEY = ["event_key", "NUMBER", "LAP_NUMBER"]
CAR_KEY = ["event_key", "NUMBER"]


def find_duplicate_laps(frame: pd.DataFrame) -> pd.DataFrame:
    """Rows where the same car appears twice on the same lap of the same event.

    Returns all copies, not just the extras.
    """
    return frame[frame.duplicated(subset=LAP_KEY, keep=False)]


def find_elapsed_time_regressions(frame: pd.DataFrame) -> pd.DataFrame:
    """Rows where a car's ELAPSED_S is not greater than its previous lap's."""
    ordered = frame.sort_values(LAP_KEY)
    step = ordered.groupby(CAR_KEY)["ELAPSED_S"].diff()
    return ordered[step <= 0]


def find_lap_number_breaks(frame: pd.DataFrame) -> pd.DataFrame:
    """Rows where a car's LAP_NUMBER does not increase by exactly 1."""
    ordered = frame.sort_values(LAP_KEY)
    step = ordered.groupby(CAR_KEY)["LAP_NUMBER"].diff()
    return ordered[step.ne(1) & step.notna()]
