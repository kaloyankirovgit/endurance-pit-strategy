from __future__ import annotations

import numpy as np
import pandas as pd

from endurance_strategy.io.load import load_race_csv
from endurance_strategy.paths import FIXTURES_DIR
from endurance_strategy.reconstruct.stints import add_stint_columns


def laps(car: str, pit_flags: str, pit_times: dict[int, float] | None = None,
         event: str = "SYNTH_EVENT") -> pd.DataFrame:
    n = len(pit_flags)
    flags = ["B" if c == "B" else "" for c in pit_flags]
    pit = [np.nan] * n
    if pit_times is None:
        for i, c in enumerate(pit_flags[:-1]):
            if c == "B":
                pit[i + 1] = 80.0
    else:
        for lap, value in pit_times.items():
            pit[lap - 1] = value
    return pd.DataFrame({
        "event_key": event,
        "NUMBER": car,
        "LAP_NUMBER": range(1, n + 1),
        "CROSSING_FINISH_LINE_IN_PIT": flags,
        "PIT_TIME_S": pit,
    })


def run(frame: pd.DataFrame) -> pd.DataFrame:
    return add_stint_columns(frame).sort_values(["event_key", "NUMBER", "LAP_NUMBER"])


def test_in_lap_is_the_b_lap() -> None:
    out = run(laps("1", "..B...."))
    assert out["is_in_lap"].tolist() == [False, False, True, False, False, False, False]


def test_out_lap_is_the_lap_after_b() -> None:
    out = run(laps("1", "..B...."))
    assert out["is_out_lap"].tolist() == [False, False, False, True, False, False, False]


def test_two_stops_give_three_stints() -> None:
    out = run(laps("1", "..B..B.."))
    assert out["stint_number"].tolist() == [1, 1, 1, 2, 2, 2, 3, 3]


def test_stint_lap_restarts_on_out_lap() -> None:
    out = run(laps("1", "..B..B.."))
    assert out["stint_lap"].tolist() == [1, 2, 3, 1, 2, 3, 1, 2]


def test_no_stops_is_one_stint() -> None:
    out = run(laps("1", "....."))
    assert out["stint_number"].tolist() == [1] * 5
    assert out["stint_lap"].tolist() == [1, 2, 3, 4, 5]


def test_pit_lane_start_is_still_stint_one() -> None:
    frame = laps("1", "...B..", pit_times={1: 40.0, 5: 80.0})
    out = run(frame)
    assert out["is_out_lap"].tolist() == [True, False, False, False, True, False]
    assert out["stint_number"].tolist() == [1, 1, 1, 1, 2, 2]
    assert out["stint_lap"].tolist() == [1, 2, 3, 4, 1, 2]


def test_retiring_in_the_pits_opens_no_new_stint() -> None:
    out = run(laps("1", "..B..B"))
    assert out["is_in_lap"].iloc[-1]
    assert out["stint_number"].tolist() == [1, 1, 1, 2, 2, 2]


def test_cars_do_not_leak_into_each_other() -> None:
    frame = pd.concat([laps("1", "B...."), laps("2", "....B")])
    out = run(frame)
    car2 = out[out["NUMBER"] == "2"]
    assert car2["stint_number"].tolist() == [1] * 5
    assert car2["stint_lap"].tolist() == [1, 2, 3, 4, 5]


def test_same_car_number_in_two_events_is_two_cars() -> None:
    frame = pd.concat([laps("7", "B...", event="A"), laps("7", "....", event="B")])
    out = run(frame)
    assert out.loc[out["event_key"] == "B", "stint_number"].tolist() == [1] * 4


def test_row_order_does_not_matter() -> None:
    frame = pd.concat([laps("1", "..B..B.."), laps("2", ".B....")])
    shuffled = frame.sample(frac=1, random_state=0)
    pd.testing.assert_frame_equal(
        run(frame).reset_index(drop=True), run(shuffled).reset_index(drop=True)
    )


def test_input_is_not_modified_and_rows_are_kept() -> None:
    frame = laps("1", "..B..B..")
    before = frame.copy()
    out = add_stint_columns(frame)
    pd.testing.assert_frame_equal(frame, before)
    assert len(out) == len(frame)


def test_stint_laps_are_contiguous_from_one() -> None:
    frame = pd.concat([laps("1", ".B..B...B"), laps("2", "B.B.B.")])
    out = run(frame)
    for _, stint in out.groupby(["event_key", "NUMBER", "stint_number"]):
        assert stint["stint_lap"].tolist() == list(range(1, len(stint) + 1))


def test_synthetic_fixture_driver_change_stop() -> None:
    out = add_stint_columns(load_race_csv(FIXTURES_DIR / "synthetic_race.CSV"))
    car = out[out["NUMBER"] == "007"]
    assert car["stint_number"].tolist() == [1, 1, 1, 2]
    assert car["DRIVER_NUMBER"].tolist() == ["1", "1", "1", "2"]
