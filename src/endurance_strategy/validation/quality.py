from __future__ import annotations

import pandas as pd

LAP_KEY = ["event_key", "NUMBER", "LAP_NUMBER"]
CAR_KEY = ["event_key", "NUMBER"]


def find_duplicate_laps(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame.duplicated(subset=LAP_KEY, keep=False)]


def find_elapsed_time_regressions(frame: pd.DataFrame) -> pd.DataFrame:
    ordered = frame.sort_values(LAP_KEY)
    step = ordered.groupby(CAR_KEY)["ELAPSED_S"].diff()
    return ordered[step <= 0]


def find_lap_number_breaks(frame: pd.DataFrame) -> pd.DataFrame:
    ordered = frame.sort_values(LAP_KEY)
    step = ordered.groupby(CAR_KEY)["LAP_NUMBER"].diff()
    return ordered[step.ne(1) & step.notna()]
