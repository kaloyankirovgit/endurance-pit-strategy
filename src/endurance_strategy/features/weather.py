from __future__ import annotations

import pandas as pd

from endurance_strategy.io.weather import WEATHER_COLUMNS


def join_weather(laps: pd.DataFrame, weather: pd.DataFrame, tolerance: str = "5min") -> pd.DataFrame:
    """Attach the latest weather reading at or before each lap's crossing.

    Needs `lap_end_utc`. Laps with no reading inside `tolerance` get NaN.
    """
    left = laps.assign(lap_end_utc=laps["lap_end_utc"].astype("datetime64[ns, UTC]")).sort_values("lap_end_utc")
    right = weather[["event_key", "weather_utc", *WEATHER_COLUMNS]]
    right = right.assign(weather_utc=right["weather_utc"].astype("datetime64[ns, UTC]")).sort_values("weather_utc")
    joined = pd.merge_asof(
        left,
        right,
        left_on="lap_end_utc",
        right_on="weather_utc",
        by="event_key",
        direction="backward",
        tolerance=pd.Timedelta(tolerance),
    )
    return joined.sort_values(["event_key", "NUMBER", "LAP_NUMBER"]).reset_index(drop=True)
