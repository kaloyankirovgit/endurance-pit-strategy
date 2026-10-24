from __future__ import annotations

import numpy as np
import pandas as pd

CAR_KEY = ["event_key", "NUMBER"]
LAP_KEY = CAR_KEY + ["LAP_NUMBER"]
SLOW_LAP_RATIO = 1.07
FIELD_SLOW_RATIO = 1.04
FIELD_WINDOW_S = 300.0
FIELD_MIN_LAPS = 10

EXCLUSION_FLAGS = [
    "is_first_lap",
    "is_pit_lap",
    "is_caution_lap",
    "is_after_caution",
    "is_missing_data",
    "is_slow_lap",
    "is_wet",
    "is_field_slow",
]


def field_pace_ratio(frame: pd.DataFrame, base: pd.Series, window_s: float = FIELD_WINDOW_S,
                     min_laps: int = FIELD_MIN_LAPS) -> pd.Series:
    """How slow the whole class was around each lap: the median lap-time ratio, against the class's
    dry reference, of the class's green laps that ended within `window_s` of this lap ending.

    NaN where fewer than `min_laps` such laps exist. It uses laps after this one, so it describes the
    race and isn't information a team has at lap t. The lap itself is one of the laps in its window.
    """
    reference = frame["LAP_TIME_S"].where(base & ~frame["is_wet"]).groupby([frame["event_key"], frame["CLASS"]]).transform("median")
    ratio = (frame["LAP_TIME_S"] / reference).to_numpy()
    elapsed = frame["ELAPSED_S"].to_numpy(dtype=float)
    usable = base.to_numpy()
    out = np.full(len(frame), np.nan)
    for rows in frame.groupby(["event_key", "CLASS"]).indices.values():
        pool = rows[usable[rows]]
        order = np.argsort(elapsed[pool])
        times, ratios = elapsed[pool][order], ratio[pool][order]
        low = np.searchsorted(times, elapsed[rows] - window_s, side="left")
        high = np.searchsorted(times, elapsed[rows] + window_s, side="right")
        out[rows] = [np.median(ratios[a:b]) if b - a >= min_laps else np.nan for a, b in zip(low, high)]
    return pd.Series(out, index=frame.index)


def add_clean_lap_flags(frame: pd.DataFrame, slow_lap_ratio: float = SLOW_LAP_RATIO,
                        field_slow_ratio: float = FIELD_SLOW_RATIO) -> pd.DataFrame:
    """Flag laps that shouldn't feed a pace model. Needs the stint columns, ELAPSED_S and RAIN.

    A lap is slow if it's more than `slow_lap_ratio` times the median green,
    non-pit, dry lap for its class at that event. A lap is in a field-slow period
    if its whole class ran more than `field_slow_ratio` times that median in the
    surrounding minutes (`field_pace_ratio`). That catches drying track the rain
    sensor misses, slow zones and local yellows, without saying which (D-025).
    Both ratios are choices, not measurements. Returns a copy sorted by car and lap.
    """
    out = frame.sort_values(LAP_KEY).copy()
    by_car = [out[k] for k in CAR_KEY]

    green = out["FLAG_AT_FL"].eq("GF")
    previous_green = green.groupby(by_car).shift(fill_value=True).astype(bool)

    out["is_first_lap"] = out.groupby(CAR_KEY).cumcount().eq(0)
    out["is_pit_lap"] = out["is_in_lap"] | out["is_out_lap"]
    out["is_caution_lap"] = ~green
    out["is_after_caution"] = ~previous_green
    out["is_wet"] = out["RAIN"].gt(0)
    out["is_missing_data"] = out[["LAP_TIME_S", "S1_S", "S2_S", "S3_S", "RAIN"]].isna().any(axis=1)

    reference = (
        out["LAP_TIME_S"]
        .where(green & ~out["is_pit_lap"] & ~out["is_wet"])
        .groupby([out["event_key"], out["CLASS"]])
        .transform("median")
    )
    out["is_slow_lap"] = out["LAP_TIME_S"] > slow_lap_ratio * reference

    base = green & ~out["is_pit_lap"] & ~out["is_first_lap"] & ~out["is_after_caution"] & ~out["is_missing_data"]
    out["field_pace_ratio"] = field_pace_ratio(out, base)
    out["is_field_slow"] = out["field_pace_ratio"].gt(field_slow_ratio)

    out["is_usable_for_pace_model"] = ~out[EXCLUSION_FLAGS].any(axis=1)
    return out


def exclusion_summary(flagged: pd.DataFrame) -> pd.DataFrame:
    """Per flag: laps it catches, and laps that only it excludes."""
    flags = flagged[EXCLUSION_FLAGS]
    only_this = flags & flags.sum(axis=1).eq(1).to_numpy()[:, None]
    return pd.DataFrame({
        "laps_flagged": flags.sum(),
        "only_reason": only_this.sum(),
    })
