from __future__ import annotations

import pandas as pd

CAR_KEY = ["event_key", "NUMBER"]
LAP_KEY = CAR_KEY + ["LAP_NUMBER"]
SLOW_LAP_RATIO = 1.07

EXCLUSION_FLAGS = [
    "is_first_lap",
    "is_pit_lap",
    "is_caution_lap",
    "is_after_caution",
    "is_missing_data",
    "is_slow_lap",
    "is_wet",
]


def add_clean_lap_flags(frame: pd.DataFrame, slow_lap_ratio: float = SLOW_LAP_RATIO) -> pd.DataFrame:
    """Flag laps that shouldn't feed a pace model. Needs the stint columns and RAIN.

    A lap is slow if it's more than `slow_lap_ratio` times the median green,
    non-pit, dry lap for its class at that event. The ratio is a choice, not a
    measurement. Returns a copy sorted by car and lap.
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
