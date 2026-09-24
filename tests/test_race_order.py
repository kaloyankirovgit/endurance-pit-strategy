from __future__ import annotations

import pandas as pd

from endurance_strategy.reconstruct.race_order import add_race_order


def crossings(rows: list[tuple[str, str, int, float]], event: str = "E") -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["NUMBER", "CLASS", "LAP_NUMBER", "ELAPSED_S"]).assign(event_key=event)


def at(out: pd.DataFrame, car: str, lap: int) -> pd.Series:
    return out[(out["NUMBER"] == car) & (out["LAP_NUMBER"] == lap)].iloc[0]


LAPPED = [
    ("1", "HC", 1, 100.0), ("1", "HC", 2, 200.0), ("1", "HC", 3, 300.0),
    ("9", "GT", 1, 110.0), ("9", "GT", 2, 225.0),
]


def test_same_lap_is_ordered_by_crossing_time() -> None:
    out = add_race_order(crossings([("1", "HC", 1, 100.0), ("2", "HC", 1, 101.5), ("3", "HC", 1, 103.0)]))
    assert [at(out, c, 1)["position"] for c in ("1", "2", "3")] == [1, 2, 3]
    assert at(out, "2", 1)["gap_ahead_s"] == 1.5
    assert pd.isna(at(out, "1", 1)["gap_ahead_s"])


def test_a_lapped_car_is_behind_even_if_it_crosses_first() -> None:
    out = add_race_order(crossings(LAPPED))
    assert at(out, "9", 2)["position"] == 2
    assert at(out, "9", 2)["gap_ahead_s"] == 25.0


def test_road_gap_is_to_whoever_crossed_just_before() -> None:
    out = add_race_order(crossings(LAPPED))
    assert at(out, "9", 2)["road_car_ahead"] == "1"
    assert at(out, "9", 2)["road_gap_ahead_s"] == 25.0
    assert at(out, "1", 3)["road_car_ahead"] == "9"
    assert at(out, "1", 3)["road_class_ahead"] == "GT"
    assert at(out, "1", 3)["road_gap_ahead_s"] == 75.0


def test_class_position_ignores_other_classes() -> None:
    out = add_race_order(crossings([("1", "HC", 1, 100.0), ("9", "GT", 1, 105.0), ("2", "HC", 1, 110.0), ("8", "GT", 1, 111.0)]))
    assert at(out, "8", 1)["class_position"] == 2
    assert at(out, "8", 1)["class_gap_ahead_s"] == 6.0
    assert at(out, "2", 1)["position"] == 3


def test_ties_break_on_car_number() -> None:
    out = add_race_order(crossings([("7", "HC", 1, 100.0), ("5", "HC", 1, 100.0)]))
    assert at(out, "5", 1)["position"] == 1
    assert at(out, "7", 1)["position"] == 2


def test_events_are_ordered_separately() -> None:
    frame = pd.concat([crossings([("1", "HC", 1, 100.0)], "A"), crossings([("2", "HC", 1, 50.0)], "B")])
    out = add_race_order(frame)
    assert out["position"].tolist() == [1, 1]
    assert out["road_car_ahead"].isna().all()


def test_positions_are_a_total_order_per_lap() -> None:
    frame = crossings([(str(c), "HC", lap, lap * 100.0 + c) for c in range(1, 6) for lap in range(1, 4)])
    out = add_race_order(frame)
    for _, lap in out.groupby("LAP_NUMBER"):
        assert sorted(lap["position"]) == list(range(1, 6))
    assert (out["gap_ahead_s"].dropna() >= 0).all()
    assert len(out) == len(frame)
