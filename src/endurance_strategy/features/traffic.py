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


PAST_FLAGS = ["is_first_lap", "is_pit_lap", "is_caution_lap", "is_after_caution", "is_missing_data", "is_wet"]
DIRECTIONS = {
    # direction: (class that causes it, window ahead (-) or behind (+) of the car on the road)
    "catching": ("slower", -1),
    "being_caught": ("faster", +1),
}


def past_class_pace_gap(laps: pd.DataFrame, min_laps: int = 20, faster: str = "HYPERCAR", slower: str = "LMGT3") -> np.ndarray:
    """Per lap: the class pace gap from laps that ended before this lap began.

    Each class median uses that class's laps so far that are green, dry, not a first or pit lap
    and not just after a caution, so nothing from later in the race is used. The slow-lap flag
    is left out on purpose, because it is set from the whole-race median. NaN until each class
    has `min_laps` such laps. `laps` needs `lap_start_s` and a unique default index.
    """
    usable = ~laps[PAST_FLAGS].any(axis=1)
    start = laps["lap_start_s"].to_numpy(dtype=float)
    gap = np.full(len(laps), np.nan)
    for rows in laps.groupby("event_key").indices.values():
        medians = []
        for car_class in (slower, faster):
            done = laps.iloc[rows][usable.iloc[rows].to_numpy() & laps["CLASS"].iloc[rows].eq(car_class).to_numpy()]
            done = done.sort_values("ELAPSED_S")
            running = done["LAP_TIME_S"].expanding().median().to_numpy()
            n_done = np.searchsorted(done["ELAPSED_S"].to_numpy(), start[rows], side="left")
            enough = n_done >= min_laps
            median = np.full(len(rows), np.nan)
            median[enough] = running[n_done[enough] - 1]
            medians.append(median)
        gap[rows] = medians[0] - medians[1]
    return gap


def count_crossings_near_lap_start(laps: pd.DataFrame, low_s: pd.Series | float, high_s: pd.Series | float,
                                   which: str = "slower") -> np.ndarray:
    """For each lap, count line crossings by other classes in [lap start + low_s, lap start + high_s).

    `laps` must be sorted by car and lap with a `lap_start_s` column and a unique default index.
    `which` is "slower" or "faster" (classes ranked below or above the car's), or "same" (its own
    class, where the car's own crossing at the lap start is outside any window that ends at 0).
    Pit-lane crossings are left out. Negative offsets look ahead on the road, positive ones behind.
    NaN on a first lap, or where the window is NaN.
    """
    rank = laps["CLASS"].map(CLASS_RANK).to_numpy()
    on_track = laps["CROSSING_FINISH_LINE_IN_PIT"].ne("B").to_numpy()
    elapsed, start = laps["ELAPSED_S"].to_numpy(dtype=float), laps["lap_start_s"].to_numpy(dtype=float)
    low = np.broadcast_to(np.asarray(low_s, dtype=float), len(laps))
    high = np.broadcast_to(np.asarray(high_s, dtype=float), len(laps))
    countable = ~np.isnan(start) & ~np.isnan(low) & ~np.isnan(high)
    counts = np.full(len(laps), np.nan)
    for rows in laps.groupby("event_key").indices.values():
        for class_rank in np.unique(rank[rows]):
            other = {"slower": rank[rows] > class_rank, "faster": rank[rows] < class_rank,
                     "same": rank[rows] == class_rank}[which]
            crossings = np.sort(elapsed[rows[other & on_track[rows]]])
            cars = rows[(rank[rows] == class_rank) & countable[rows]]
            counts[cars] = (np.searchsorted(crossings, start[cars] + high[cars], side="left")
                            - np.searchsorted(crossings, start[cars] + low[cars], side="left"))
    return counts


def window_offsets(direction: str, window: np.ndarray, near: float = 0.0, far: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """The road window from `near`*W to `far`*W on the side of the car that `direction` looks at."""
    sign = DIRECTIONS[direction][1]
    a, b = sign * near * window, sign * far * window
    return np.minimum(a, b), np.maximum(a, b)


def add_traffic_exposure(laps: pd.DataFrame, window_s: float | pd.Series | str, direction: str = "catching") -> pd.DataFrame:
    """Count the other-class cars a car is expected to meet on the road during each lap.

    At the start of a lap (the car's previous line crossing), another car that crossed the line
    up to W seconds before it is that far ahead on the road, and one crossing up to W seconds
    after it is that far behind. With W set to the class pace gap:

    - "catching": slower-class cars ahead within W, which the car should catch this lap;
    - "being_caught": faster-class cars behind within W, which should catch the car this lap.

    Pit-lane crossings are left out, since that car is off the track. Counted at the start of the
    lap, so the lap's own outcome can't create its exposure. The count is a candidate exposure,
    not an observed overtake (D-004). A car's first lap has no start crossing and gets NaN.

    `window_s` is one number for every event, a Series indexed by event_key, or "past" for the
    gap from laps completed before each lap began (`past_class_pace_gap`).
    """
    out = laps.sort_values(LAP_KEY).reset_index(drop=True)
    out["lap_start_s"] = out.groupby(CAR_KEY)["ELAPSED_S"].shift()
    if isinstance(window_s, str):
        if window_s != "past":
            raise ValueError(f"unknown window {window_s!r}")
        out["traffic_window_s"] = past_class_pace_gap(out)
    elif isinstance(window_s, pd.Series):
        out["traffic_window_s"] = out["event_key"].map(window_s)
    else:
        out["traffic_window_s"] = float(window_s)
    out["traffic_direction"] = direction
    which = DIRECTIONS[direction][0]
    low, high = window_offsets(direction, out["traffic_window_s"].to_numpy(dtype=float))
    counts = count_crossings_near_lap_start(out, low, high, which=which)
    out["candidate_traffic_count"] = counts
    out["is_candidate_traffic"] = counts > 0
    return out


def add_placebo_counts(exposed: pd.DataFrame, same_class_gap_s: float = 2.0) -> pd.DataFrame:
    """Counts that shouldn't matter, or that stand for other causes, to check the exposure against.

    - `other_side_count`: the same class of car within W on the other side of the car at lap
      start (just caught, or just passed). It won't be met this lap.
    - `far_count`: the same class of car 2W to 3W away on the exposure's side. Too far to meet this lap.
    - `same_class_ahead_count`: same-class cars within `same_class_gap_s` ahead (same-class traffic).
    - `exposure_two_laps_later`: the car's own count two laps on, which can't affect this lap.
    """
    out = exposed.copy()
    direction = out["traffic_direction"].iloc[0]
    which = DIRECTIONS[direction][0]
    window = out["traffic_window_s"].to_numpy(dtype=float)
    opposite = "being_caught" if direction == "catching" else "catching"
    out["other_side_count"] = count_crossings_near_lap_start(out, *window_offsets(opposite, window), which=which)
    out["far_count"] = count_crossings_near_lap_start(out, *window_offsets(direction, window, 2.0, 3.0), which=which)
    out["same_class_ahead_count"] = count_crossings_near_lap_start(out, -same_class_gap_s, 0.0, which="same")
    out["exposure_two_laps_later"] = out.groupby(CAR_KEY)["candidate_traffic_count"].shift(-2)
    return out
