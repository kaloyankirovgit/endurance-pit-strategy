from __future__ import annotations

import numpy as np
import pandas as pd

CAR_KEY = ["event_key", "NUMBER"]
LAP_KEY = CAR_KEY + ["LAP_NUMBER"]
CLASS_RANK = {"HYPERCAR": 0, "LMP2": 1, "LMGT3": 2}


def class_pace_gap(laps: pd.DataFrame, faster: str = "HYPERCAR", slower: str = "LMGT3") -> pd.Series:
    """Per event: median usable lap of the slower class minus that of the faster class, in seconds.

    Uses the whole race, so it describes the race; it is not information a team has at lap t.
    """
    usable = laps[laps["is_usable_for_pace_model"]]
    medians = usable.groupby(["event_key", "CLASS"])["LAP_TIME_S"].median().unstack()
    return (medians[slower] - medians[faster]).rename("class_pace_gap_s")


def count_crossings_near_lap_start(laps: pd.DataFrame, low_s: pd.Series | float, high_s: pd.Series | float,
                                   which: str = "slower") -> np.ndarray:
    """For each lap, count line crossings by other classes in [lap start + low_s, lap start + high_s).

    `laps` must be sorted by car and lap with a `lap_start_s` column and a unique default index.
    `which` is "slower" (classes ranked below the car's) or "same" (its own class, where the car's
    own crossing at the lap start is outside any window that ends at 0). Pit-lane crossings are
    left out. Negative offsets look ahead on the road, positive ones behind. NaN on a first lap.
    """
    rank = laps["CLASS"].map(CLASS_RANK).to_numpy()
    on_track = laps["CROSSING_FINISH_LINE_IN_PIT"].ne("B").to_numpy()
    has_start = laps["lap_start_s"].notna().to_numpy()
    elapsed, start = laps["ELAPSED_S"].to_numpy(dtype=float), laps["lap_start_s"].to_numpy(dtype=float)
    low = np.broadcast_to(np.asarray(low_s, dtype=float), len(laps))
    high = np.broadcast_to(np.asarray(high_s, dtype=float), len(laps))
    counts = np.full(len(laps), np.nan)
    for rows in laps.groupby("event_key").indices.values():
        for class_rank in np.unique(rank[rows]):
            other = (rank[rows] > class_rank) if which == "slower" else (rank[rows] == class_rank)
            crossings = np.sort(elapsed[rows[other & on_track[rows]]])
            cars = rows[(rank[rows] == class_rank) & has_start[rows]]
            counts[cars] = (np.searchsorted(crossings, start[cars] + high[cars], side="left")
                            - np.searchsorted(crossings, start[cars] + low[cars], side="left"))
    return counts


def add_traffic_exposure(laps: pd.DataFrame, window_s: float | pd.Series) -> pd.DataFrame:
    """Count slower-class cars that a car is expected to catch during each lap.

    At the start of a lap (the car's previous line crossing), a slower-class car that crossed
    the line within `window_s` seconds before it is that far ahead on the road. With `window_s`
    set to the class pace gap, it should be caught before the lap ends. Crossings made in the
    pit lane are left out, since that car is off the track. Counted at the start of the lap,
    so the lap's own outcome can't create its exposure. The count is a candidate exposure,
    not an observed overtake (D-004). A car's first lap has no start crossing and gets NaN.

    `window_s` is one number for every event, or a Series indexed by event_key.
    """
    out = laps.sort_values(LAP_KEY).reset_index(drop=True)
    out["lap_start_s"] = out.groupby(CAR_KEY)["ELAPSED_S"].shift()
    out["traffic_window_s"] = out["event_key"].map(window_s) if isinstance(window_s, pd.Series) else float(window_s)
    counts = count_crossings_near_lap_start(out, -out["traffic_window_s"].to_numpy(), 0.0)
    out["candidate_traffic_count"] = counts
    out["is_candidate_traffic"] = counts > 0
    return out


def add_placebo_counts(exposed: pd.DataFrame, same_class_gap_s: float = 2.0) -> pd.DataFrame:
    """Counts that shouldn't matter, or that stand for other causes, to check the exposure against.

    - `slower_behind_count`: slower cars in the window behind at lap start. They can't be caught.
    - `slower_far_ahead_count`: slower cars 2W to 3W ahead. Too far to catch this lap.
    - `same_class_ahead_count`: same-class cars within `same_class_gap_s` ahead (same-class traffic).
    - `exposure_two_laps_later`: the car's own count two laps on, which can't affect this lap.
    """
    out = exposed.copy()
    window = out["traffic_window_s"].to_numpy(dtype=float)
    out["slower_behind_count"] = count_crossings_near_lap_start(out, 0.0, window)
    out["slower_far_ahead_count"] = count_crossings_near_lap_start(out, -3 * window, -2 * window)
    out["same_class_ahead_count"] = count_crossings_near_lap_start(out, -same_class_gap_s, 0.0, which="same")
    out["exposure_two_laps_later"] = out.groupby(CAR_KEY)["candidate_traffic_count"].shift(-2)
    return out
