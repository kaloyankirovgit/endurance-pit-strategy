from __future__ import annotations

import numpy as np
import pytest
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
        "ELAPSED_S": np.cumsum(times, dtype=float),
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


def field(cars: int, times_by_lap: list[float], car_class: str = "HYPERCAR") -> pd.DataFrame:
    """Several cars on identical laps, so the whole class shares the same pace at the same time."""
    return pd.concat([laps(str(k), times_by_lap, car_class=car_class) for k in range(cars)], ignore_index=True)


def test_a_whole_class_running_slow_is_a_field_slow_period():
    out = run(field(12, [100] * 10 + [110] * 5 + [100] * 10), slow_lap_ratio=1.5)
    slow_period = out["LAP_NUMBER"].between(12, 15)
    assert out.loc[slow_period, "is_field_slow"].all()
    assert not out.loc[out["LAP_NUMBER"].between(2, 8), "is_field_slow"].any()
    assert not out.loc[slow_period, "is_usable_for_pace_model"].any()


def test_one_slow_car_does_not_make_a_field_slow_period():
    frame = pd.concat([field(12, [100] * 20), laps("99", [100] * 10 + [110] * 10)], ignore_index=True)
    out = run(frame, slow_lap_ratio=1.5)
    assert not out["is_field_slow"].any()


def test_field_slow_needs_enough_laps_in_the_window():
    out = run(field(1, [100] * 3 + [110] * 3))
    assert out["field_pace_ratio"].isna().all()
    assert not out["is_field_slow"].any()


def test_field_slow_threshold_can_be_changed():
    frame = field(12, [100] * 10 + [103] * 6 + [100] * 10)
    assert not run(frame, slow_lap_ratio=1.5)["is_field_slow"].any()
    assert run(frame, slow_lap_ratio=1.5, field_slow_ratio=1.02)["is_field_slow"].any()


# --- E-021: a wet race switches to the weekend's practice pace (synthetic laps) ---

def _wet_race() -> pd.DataFrame:
    """Most of the race slow (wet), a dry end. Every lap here is synthetic."""
    return pd.concat([laps(c, [100.0] + [120.0] * 12 + [101.0] * 6) for c in "ABCDEFGHIJKL"], ignore_index=True)


def _dry_race() -> pd.DataFrame:
    return pd.concat([laps(c, [100.0] + [101.0] * 10 + [112.0]) for c in "ABCDEFGHIJKL"], ignore_index=True)


def practice_table(pace: float = 100.0, cars: int = 12, practice_laps: int = 200, event: str = "SYNTH") -> pd.DataFrame:
    index = pd.MultiIndex.from_tuples([(event, "HYPERCAR")], names=["event_key", "CLASS"])
    return pd.DataFrame({"pace": [pace], "cars": [cars], "laps": [practice_laps]}, index=index)


def test_race_median_reference_lets_a_wet_race_through():
    out = run(_wet_race())
    assert not out.loc[out["LAP_TIME_S"].eq(120.0), "is_slow_lap"].any()


def test_a_wet_race_switches_to_practice_and_its_wet_laps_are_flagged():
    out = run(_wet_race(), practice=practice_table(100.0))
    wet, dry = out["LAP_TIME_S"].eq(120.0), out["LAP_TIME_S"].eq(101.0)
    assert (out["slow_lap_reference_source"] == "practice").all()
    assert out.loc[wet, "is_slow_lap"].all()
    assert not out.loc[dry, "is_slow_lap"].any()
    assert not out.loc[wet, "is_usable_for_pace_model"].any()


def test_a_dry_race_close_to_practice_keeps_its_flags_exactly():
    out = run(_dry_race(), practice=practice_table(99.0))
    assert (out["slow_lap_reference_source"] == "race").all()
    for flag in ["is_slow_lap", "is_field_slow", "is_usable_for_pace_model"]:
        assert out[flag].tolist() == run(_dry_race())[flag].tolist()


def test_a_wet_practice_cannot_loosen_the_rule():
    out = run(_dry_race(), practice=practice_table(130.0))
    assert (out["slow_lap_reference_source"] == "race").all()
    assert out["is_slow_lap"].tolist() == run(_dry_race())["is_slow_lap"].tolist()


@pytest.mark.parametrize("cars, practice_laps", [(5, 200), (12, 60)])
def test_thin_practice_is_not_used(cars, practice_laps):
    out = run(_wet_race(), practice=practice_table(100.0, cars=cars, practice_laps=practice_laps))
    assert (out["slow_lap_reference_source"] == "race").all()


def test_missing_practice_keeps_the_race_median():
    out = run(_wet_race(), practice=practice_table(100.0, event="OTHER"))
    assert out["is_slow_lap"].tolist() == out["is_slow_lap_race_ref"].tolist()
    assert (out["slow_lap_reference_source"] == "race").all()


def test_old_flags_are_kept_beside_the_new_ones():
    out = run(_wet_race(), practice=practice_table(100.0))
    plain = run(_wet_race())
    for flag, old in [("is_slow_lap", "is_slow_lap_race_ref"), ("is_field_slow", "is_field_slow_race_ref"),
                      ("is_usable_for_pace_model", "is_usable_race_ref")]:
        assert out[old].tolist() == plain[flag].tolist()
    assert out["field_pace_ratio_race_ref"].tolist() == pytest.approx(plain["field_pace_ratio"].tolist(), nan_ok=True)


def test_field_slow_uses_practice_once_switched():
    out = run(_wet_race(), practice=practice_table(100.0))
    wet = out["LAP_TIME_S"].eq(120.0) & ~out["is_first_lap"]
    assert out.loc[wet, "is_field_slow"].mean() > 0.9
    assert not out.loc[wet, "is_field_slow_race_ref"].all()


def test_apply_clean_rule_swaps_in_the_old_flags():
    from endurance_strategy.features.clean_laps import apply_clean_rule
    out = run(_wet_race(), practice=practice_table(100.0))
    old = apply_clean_rule(out, "race")
    assert old["is_usable_for_pace_model"].tolist() == out["is_usable_race_ref"].tolist()
    assert apply_clean_rule(out, "practice") is out
    with pytest.raises(ValueError):
        apply_clean_rule(out, "neither")


def test_practice_reference_table_counts_cars_laps_and_dropped_sessions():
    from endurance_strategy.features.practice import practice_pace, practice_reference_table
    rows = []
    for session, scale in (("FP1", 1.0), ("FP2", 1.2)):
        for car in "ABC":
            for lap in range(1, 6):
                rows.append({"event_key": "SYNTH", "session": session, "CLASS": "HYPERCAR", "NUMBER": car, "LAP_NUMBER": lap,
                             "LAP_TIME_S": 100.0 * scale, "S1_S": 30.0, "S2_S": 30.0, "S3_S": 40.0, "FLAG_AT_FL": "GF",
                             "is_in_lap": False, "is_out_lap": False, "stint_lap": lap})
    practice = pd.DataFrame(rows)
    table = practice_reference_table(practice)
    row = table.loc[("SYNTH", "HYPERCAR")]
    assert (row["pace"], row["cars"], row["laps"], row["sessions_dropped"]) == (100.0, 3, 12, 1)
    assert practice_pace(practice).loc[("SYNTH", "HYPERCAR")] == row["pace"]
