from __future__ import annotations

import numpy as np
import pandas as pd

from endurance_strategy.features.clean_laps import (
    EXCLUSION_FLAGS,
    add_clean_lap_flags,
    exclusion_summary,
)
from endurance_strategy.reconstruct.stints import add_stint_columns


def laps(car: str, times: list[float], flags: str | None = None, pits: str | None = None,
         car_class: str = "HYPERCAR", event: str = "SYNTH", rain: list[int] | None = None) -> pd.DataFrame:
    n = len(times)
    flags = flags or "G" * n
    pits = pits or "." * n
    flag_codes = {"G": "GF", "F": "FCY", "S": "SF"}
    pit_time = [np.nan] * n
    for i, c in enumerate(pits[:-1]):
        if c == "B":
            pit_time[i + 1] = 80.0
    return pd.DataFrame({
        "event_key": event,
        "NUMBER": car,
        "CLASS": car_class,
        "LAP_NUMBER": range(1, n + 1),
        "LAP_TIME_S": times,
        "S1_S": [t / 3 for t in times],
        "S2_S": [t / 3 for t in times],
        "S3_S": [t / 3 for t in times],
        "FLAG_AT_FL": [flag_codes[c] for c in flags],
        "CROSSING_FINISH_LINE_IN_PIT": ["B" if c == "B" else "" for c in pits],
        "PIT_TIME_S": pit_time,
        "RAIN": rain if rain is not None else [0] * n,
    })


def run(frame: pd.DataFrame, **kwargs) -> pd.DataFrame:
    return add_clean_lap_flags(add_stint_columns(frame), **kwargs)


def test_plain_green_laps_are_usable_after_lap_one() -> None:
    out = run(laps("1", [110, 100, 100, 100]))
    assert out["is_usable_for_pace_model"].tolist() == [False, True, True, True]
    assert out["is_first_lap"].tolist() == [True, False, False, False]


def test_in_and_out_laps_are_pit_laps() -> None:
    out = run(laps("1", [110, 100, 104, 150, 100, 100], pits="..B..."))
    assert out["is_pit_lap"].tolist() == [False, False, True, True, False, False]


def test_caution_lap_and_the_lap_after_are_excluded() -> None:
    out = run(laps("1", [110, 100, 140, 105, 100, 100], flags="GGFGGG"))
    assert out["is_caution_lap"].tolist() == [False, False, True, False, False, False]
    assert out["is_after_caution"].tolist() == [False, False, False, True, False, False]
    assert out["is_usable_for_pace_model"].tolist() == [False, True, False, False, True, True]


def test_after_caution_does_not_leak_between_cars() -> None:
    frame = pd.concat([laps("1", [100, 100, 140], flags="GGS"), laps("2", [100, 100, 100])])
    out = run(frame)
    assert not out.loc[out["NUMBER"] == "2", "is_after_caution"].any()


def test_missing_sector_is_flagged() -> None:
    frame = laps("1", [110, 100, 100])
    frame.loc[2, "S2_S"] = np.nan
    out = run(frame)
    assert out["is_missing_data"].tolist() == [False, False, True]


def test_missing_weather_is_flagged() -> None:
    frame = laps("1", [110, 100, 100])
    frame["RAIN"] = frame["RAIN"].astype(float)
    frame.loc[1, "RAIN"] = np.nan
    out = run(frame)
    assert out["is_missing_data"].tolist() == [False, True, False]


def test_rain_makes_a_lap_wet_and_unusable() -> None:
    out = run(laps("1", [110, 100, 100, 100], rain=[0, 0, 1, 0]))
    assert out["is_wet"].tolist() == [False, False, True, False]
    assert out["is_usable_for_pace_model"].tolist() == [False, True, False, True]


def test_wet_laps_do_not_set_the_reference() -> None:
    frame = laps("1", [100, 100, 130, 130, 130, 130, 130, 108], rain=[0, 0, 1, 1, 1, 1, 1, 0])
    out = run(frame)
    assert out["is_slow_lap"].iloc[-1]


def test_slow_lap_threshold_is_relative_to_class_median() -> None:
    out = run(laps("1", [100, 100, 100, 106, 108]))
    assert out["is_slow_lap"].tolist() == [False, False, False, False, True]


def test_threshold_can_be_changed() -> None:
    out = run(laps("1", [100, 100, 100, 106, 108]), slow_lap_ratio=1.05)
    assert out["is_slow_lap"].tolist() == [False, False, False, True, True]


def test_each_class_has_its_own_reference() -> None:
    frame = pd.concat([
        laps("1", [100, 100, 100, 100]),
        laps("2", [120, 120, 120, 120], car_class="LMGT3"),
    ])
    out = run(frame)
    assert not out["is_slow_lap"].any()


def test_pit_and_caution_laps_do_not_set_the_reference() -> None:
    frame = laps("1", [100, 100, 300, 300, 300, 300, 300, 100, 108], flags="GGSSSSSGG")
    out = run(frame)
    assert out["is_slow_lap"].iloc[-1]


def test_input_is_not_modified() -> None:
    frame = add_stint_columns(laps("1", [110, 100, 100]))
    before = frame.copy()
    add_clean_lap_flags(frame)
    pd.testing.assert_frame_equal(frame, before)


def test_summary_counts_laps_excluded_for_one_reason_only() -> None:
    out = run(laps("1", [110, 100, 140, 105, 100], flags="GGFGG"))
    summary = exclusion_summary(out)
    assert list(summary.index) == EXCLUSION_FLAGS
    assert summary.loc["is_first_lap", "laps_flagged"] == 1
    assert summary.loc["is_caution_lap", "laps_flagged"] == 1
    assert summary.loc["is_caution_lap", "only_reason"] == 0
    assert summary.loc["is_after_caution", "only_reason"] == 1
