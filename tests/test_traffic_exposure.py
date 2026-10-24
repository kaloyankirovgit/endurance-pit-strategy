from __future__ import annotations

import pandas as pd

from endurance_strategy.features.traffic import add_placebo_counts, add_traffic_exposure, class_pace_gap


def crossings(rows: list[tuple], event: str = "E") -> pd.DataFrame:
    """Synthetic line crossings: (car, class, lap, elapsed seconds, crossed in pit lane)."""
    frame = pd.DataFrame(rows, columns=["NUMBER", "CLASS", "LAP_NUMBER", "ELAPSED_S", "in_pit"])
    frame["CROSSING_FINISH_LINE_IN_PIT"] = frame.pop("in_pit").map({True: "B", False: ""})
    return frame.assign(event_key=event)


def count(out: pd.DataFrame, car: str, lap: int) -> float:
    return out[(out["NUMBER"] == car) & (out["LAP_NUMBER"] == lap)]["candidate_traffic_count"].iloc[0]


# Hypercar 1 starts lap 2 at t=100. GT3 cars crossed 2 s and 9 s earlier; one crossed 15 s
# earlier, outside a 10 s window; one crosses after t=100, so it is behind on the road.
BASE = [
    ("1", "HYPERCAR", 1, 100.0, False), ("1", "HYPERCAR", 2, 200.0, False),
    ("51", "LMGT3", 5, 98.0, False),
    ("52", "LMGT3", 5, 91.0, False),
    ("53", "LMGT3", 5, 85.0, False),
    ("54", "LMGT3", 5, 101.0, False),
]


def test_counts_slower_cars_within_the_window_ahead_at_lap_start():
    out = add_traffic_exposure(crossings(BASE), window_s=10.0)
    assert count(out, "1", 2) == 2


def test_first_lap_has_no_start_crossing_and_is_nan():
    out = add_traffic_exposure(crossings(BASE), window_s=10.0)
    assert pd.isna(count(out, "1", 1))
    assert not out[(out["NUMBER"] == "1") & (out["LAP_NUMBER"] == 1)]["is_candidate_traffic"].iloc[0]


def test_same_and_faster_class_cars_are_not_counted():
    rows = BASE + [("2", "HYPERCAR", 7, 99.0, False)]
    out = add_traffic_exposure(crossings(rows), window_s=10.0)
    assert count(out, "1", 2) == 2


def test_slower_class_car_gets_no_count_from_faster_cars_ahead():
    rows = [("51", "LMGT3", 1, 50.0, False), ("51", "LMGT3", 2, 160.0, False), ("1", "HYPERCAR", 3, 45.0, False)]
    out = add_traffic_exposure(crossings(rows), window_s=10.0)
    assert count(out, "51", 2) == 0


def test_a_crossing_in_the_pit_lane_is_not_on_track():
    rows = BASE[:2] + [("51", "LMGT3", 5, 98.0, True), ("52", "LMGT3", 5, 91.0, False)]
    out = add_traffic_exposure(crossings(rows), window_s=10.0)
    assert count(out, "1", 2) == 1


def test_window_edges_include_the_far_end_and_exclude_the_start_instant():
    rows = BASE[:2] + [("51", "LMGT3", 5, 90.0, False), ("52", "LMGT3", 5, 100.0, False)]
    out = add_traffic_exposure(crossings(rows), window_s=10.0)
    assert count(out, "1", 2) == 1


def test_other_events_do_not_leak_in():
    other = crossings([("51", "LMGT3", 5, 98.0, False)], event="F")
    out = add_traffic_exposure(pd.concat([crossings(BASE[:2]), other]), window_s=10.0)
    assert count(out, "1", 2) == 0


def test_window_can_differ_by_event():
    frames = pd.concat([crossings(BASE, event="E"), crossings(BASE, event="F")])
    out = add_traffic_exposure(frames, window_s=pd.Series({"E": 10.0, "F": 20.0}))
    by_event = out[(out["NUMBER"] == "1") & (out["LAP_NUMBER"] == 2)].set_index("event_key")["candidate_traffic_count"]
    assert by_event.to_dict() == {"E": 2, "F": 3}


def test_class_pace_gap_is_slower_median_minus_faster_median():
    laps = pd.DataFrame({
        "event_key": ["E"] * 5, "CLASS": ["HYPERCAR", "HYPERCAR", "LMGT3", "LMGT3", "LMGT3"],
        "LAP_TIME_S": [100.0, 102.0, 112.0, 113.0, 300.0], "is_usable_for_pace_model": [True, True, True, True, False],
    })
    assert class_pace_gap(laps)["E"] == 11.5


def test_placebo_counts_look_behind_far_ahead_and_at_the_same_class():
    rows = BASE + [
        ("55", "LMGT3", 5, 105.0, False),
        ("56", "LMGT3", 5, 75.0, False),
        ("2", "HYPERCAR", 7, 99.0, False), ("3", "HYPERCAR", 7, 97.0, False),
    ]
    out = add_placebo_counts(add_traffic_exposure(crossings(rows), window_s=10.0))
    lap = out[(out["NUMBER"] == "1") & (out["LAP_NUMBER"] == 2)].iloc[0]
    assert lap["candidate_traffic_count"] == 2
    assert lap["slower_behind_count"] == 2
    assert lap["slower_far_ahead_count"] == 1
    assert lap["same_class_ahead_count"] == 1


def test_exposure_two_laps_later_is_the_cars_own_future_count():
    rows = [("1", "HYPERCAR", k, 100.0 * k, False) for k in range(1, 5)] + [("51", "LMGT3", 1, 295.0, False)]
    out = add_placebo_counts(add_traffic_exposure(crossings(rows), window_s=10.0))
    car = out[out["NUMBER"] == "1"].set_index("LAP_NUMBER")
    assert car.loc[4, "candidate_traffic_count"] == 1
    assert car.loc[2, "exposure_two_laps_later"] == 1
