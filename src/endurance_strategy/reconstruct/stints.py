from __future__ import annotations

import pandas as pd

CAR_KEY = ["event_key", "NUMBER"]
LAP_KEY = CAR_KEY + ["LAP_NUMBER"]
GARAGE_STOP_RATIO = 3.0


def add_stint_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Add `is_in_lap`, `is_out_lap`, `stint_number` and `stint_lap`.

    "B" in CROSSING_FINISH_LINE_IN_PIT is the in-lap and PIT_TIME sits on the
    out-lap after it. A lap-1 out-lap is a pit-lane start, not a new stint.
    Returns a copy sorted by car and lap.
    """
    out = frame.sort_values(LAP_KEY).copy()

    out["is_in_lap"] = out["CROSSING_FINISH_LINE_IN_PIT"].eq("B")
    out["is_out_lap"] = out["PIT_TIME_S"].notna()

    first_lap = out.groupby(CAR_KEY).cumcount().eq(0)
    starts_stint = out["is_out_lap"] & ~first_lap
    out["stint_number"] = starts_stint.groupby([out[k] for k in CAR_KEY]).cumsum() + 1
    out["stint_lap"] = out.groupby(CAR_KEY + ["stint_number"]).cumcount() + 1

    return out


def add_garage_stop_flag(frame: pd.DataFrame, ratio: float = GARAGE_STOP_RATIO) -> pd.DataFrame:
    """Add `is_garage_stop`: an out-lap whose PIT_TIME is over `ratio` times the race median.

    Needs `is_out_lap`. The ratio is a choice, not a measurement.
    """
    out = frame.copy()
    median = out["PIT_TIME_S"].groupby(out["event_key"]).transform("median")
    out["is_garage_stop"] = out["is_out_lap"] & (out["PIT_TIME_S"] > ratio * median)
    return out
