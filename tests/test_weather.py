from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from endurance_strategy.features.weather import join_weather
from endurance_strategy.reconstruct.race_clock import add_lap_utc


def laps(event: str, hours: list[str], elapsed: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "event_key": event,
        "NUMBER": "1",
        "LAP_NUMBER": range(1, len(hours) + 1),
        "HOUR": hours,
        "ELAPSED_S": elapsed,
    })


def weather(event: str, times_utc: list[str], rain: list[int]) -> pd.DataFrame:
    n = len(times_utc)
    return pd.DataFrame({
        "event_key": event,
        "weather_utc": pd.to_datetime(times_utc, utc=True),
        "AIR_TEMP": [20.0] * n,
        "TRACK_TEMP": [30.0] * n,
        "HUMIDITY": [50] * n,
        "PRESSURE": [1013.0] * n,
        "WIND_SPEED": [5] * n,
        "WIND_DIRECTION": [180] * n,
        "RAIN": rain,
    })


def test_local_clock_becomes_utc_with_the_circuit_timezone() -> None:
    frame = laps("2025_LE_MANS", ["16:03:43.009"], [223.009])
    out = add_lap_utc(frame, race_dates={"2025_LE_MANS": date(2025, 6, 14)})
    assert out["lap_end_utc"].iloc[0] == pd.Timestamp("2025-06-14 14:03:43.009", tz="UTC")


def test_race_past_midnight_moves_to_the_next_day() -> None:
    frame = laps("2025_LE_MANS", ["16:03:43", "23:59:00", "00:02:30"], [223, 28740, 28950])
    out = add_lap_utc(frame, race_dates={"2025_LE_MANS": date(2025, 6, 14)})
    assert out["lap_end_utc"].dt.date.tolist() == [date(2025, 6, 14), date(2025, 6, 14), date(2025, 6, 14)]
    assert out["lap_end_utc"].iloc[2] == pd.Timestamp("2025-06-14 22:02:30", tz="UTC")


def test_red_flag_pause_does_not_shift_the_clock() -> None:
    frame = laps("2024_SPA_FRANCORCHAMPS", ["13:02:00", "13:04:00", "15:30:00"], [120, 240, 400])
    out = add_lap_utc(frame, race_dates={"2024_SPA_FRANCORCHAMPS": date(2024, 5, 11)})
    assert out["lap_end_utc"].iloc[2] == pd.Timestamp("2024-05-11 13:30:00", tz="UTC")


def test_each_lap_gets_the_latest_earlier_reading() -> None:
    frame = pd.DataFrame({
        "event_key": "E", "NUMBER": "1", "LAP_NUMBER": [1, 2],
        "lap_end_utc": pd.to_datetime(["2025-01-01 12:00:30", "2025-01-01 12:01:59"], utc=True),
    })
    w = weather("E", ["2025-01-01 12:00:00", "2025-01-01 12:01:00", "2025-01-01 12:02:00"], [0, 1, 2])
    assert join_weather(frame, w)["RAIN"].tolist() == [0, 1]


def test_no_reading_within_tolerance_gives_nan() -> None:
    frame = pd.DataFrame({
        "event_key": "E", "NUMBER": "1", "LAP_NUMBER": [1],
        "lap_end_utc": pd.to_datetime(["2025-01-01 13:00:00"], utc=True),
    })
    w = weather("E", ["2025-01-01 12:00:00"], [0])
    assert np.isnan(join_weather(frame, w)["RAIN"].iloc[0])


def test_weather_does_not_cross_events() -> None:
    frame = pd.DataFrame({
        "event_key": "A", "NUMBER": "1", "LAP_NUMBER": [1],
        "lap_end_utc": pd.to_datetime(["2025-01-01 12:00:30"], utc=True),
    })
    w = weather("B", ["2025-01-01 12:00:00"], [5])
    assert np.isnan(join_weather(frame, w)["RAIN"].iloc[0])
