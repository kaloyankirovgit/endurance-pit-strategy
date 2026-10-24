from __future__ import annotations

import pandas as pd

from endurance_strategy.features.traffic import (
    add_class_pair_counts,
    add_placebo_counts,
    add_traffic_exposure,
    class_pace_gap,
    past_class_pace_gap,
)


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
    assert lap["other_side_count"] == 2
    assert lap["far_count"] == 1
    assert lap["same_class_ahead_count"] == 1


def test_exposure_two_laps_later_is_the_cars_own_future_count():
    rows = [("1", "HYPERCAR", k, 100.0 * k, False) for k in range(1, 5)] + [("51", "LMGT3", 1, 295.0, False)]
    out = add_placebo_counts(add_traffic_exposure(crossings(rows), window_s=10.0))
    car = out[out["NUMBER"] == "1"].set_index("LAP_NUMBER")
    assert car.loc[4, "candidate_traffic_count"] == 1
    assert car.loc[2, "exposure_two_laps_later"] == 1


def test_being_caught_counts_faster_cars_behind_within_the_window():
    # GT3 car 51 starts lap 2 at t=100. Hypercars cross 3 s and 8 s later (behind it on the road),
    # one 12 s later (outside a 10 s window), one 4 s earlier (just passed it), one in the pit lane.
    rows = [("51", "LMGT3", 1, 100.0, False), ("51", "LMGT3", 2, 215.0, False),
            ("1", "HYPERCAR", 9, 103.0, False), ("2", "HYPERCAR", 9, 108.0, False),
            ("3", "HYPERCAR", 9, 112.0, False), ("4", "HYPERCAR", 9, 96.0, False),
            ("5", "HYPERCAR", 9, 105.0, True), ("52", "LMGT3", 4, 104.0, False)]
    out = add_placebo_counts(add_traffic_exposure(crossings(rows), window_s=10.0, direction="being_caught"))
    lap = out[(out["NUMBER"] == "51") & (out["LAP_NUMBER"] == 2)].iloc[0]
    assert lap["candidate_traffic_count"] == 2
    assert lap["other_side_count"] == 1


def test_hypercar_laps_have_no_faster_class_to_be_caught_by():
    out = add_traffic_exposure(crossings(BASE), window_s=10.0, direction="being_caught")
    assert count(out, "1", 2) == 0


def past_race() -> pd.DataFrame:
    """Two classes lapping steadily: Hypercar 100 s laps then 104 s, GT3 112 s laps throughout."""
    rows = []
    for car, car_class, laps in (("1", "HYPERCAR", [100.0] * 5 + [104.0] * 5), ("51", "LMGT3", [112.0] * 10)):
        elapsed = 0.0
        for number, lap_time in enumerate(laps, start=1):
            elapsed += lap_time
            rows.append((car, car_class, number, elapsed, lap_time))
    frame = pd.DataFrame(rows, columns=["NUMBER", "CLASS", "LAP_NUMBER", "ELAPSED_S", "LAP_TIME_S"])
    for flag in ("is_first_lap", "is_pit_lap", "is_caution_lap", "is_after_caution", "is_missing_data", "is_wet"):
        frame[flag] = False
    frame["is_first_lap"] = frame["LAP_NUMBER"].eq(1)
    return frame.assign(event_key="E", CROSSING_FINISH_LINE_IN_PIT="")


def test_past_window_uses_only_laps_finished_before_the_lap_began():
    frame = past_race().sort_values(["event_key", "NUMBER", "LAP_NUMBER"]).reset_index(drop=True)
    frame["lap_start_s"] = frame.groupby(["event_key", "NUMBER"])["ELAPSED_S"].shift()
    gap = pd.Series(past_class_pace_gap(frame, min_laps=2), index=frame.index)
    hypercar = frame["NUMBER"].eq("1")
    # Hypercar lap 4 starts at t=300: GT3 has only lap 2 done (its first lap doesn't count), fewer than min_laps.
    assert pd.isna(gap[hypercar & frame["LAP_NUMBER"].eq(4)].iloc[0])
    # Lap 5 starts at t=400: Hypercar laps 2-3 (100 s; lap 4 ends at 400, not before) and GT3 laps 2-3 (112 s).
    assert gap[hypercar & frame["LAP_NUMBER"].eq(5)].iloc[0] == 12.0
    # Lap 9 starts at t=812: Hypercar laps 2-5 at 100 s and 6-7 at 104 s are done, median 100, so 12 s.
    # The whole-race median (104 s) would give 8 s, which needs laps that haven't happened yet.
    assert gap[hypercar & frame["LAP_NUMBER"].eq(9)].iloc[0] == 12.0
    assert class_pace_gap(frame.assign(is_usable_for_pace_model=~frame["is_first_lap"]))["E"] == 8.0


def test_past_window_feeds_the_exposure_and_leaves_early_laps_uncounted():
    out = add_traffic_exposure(past_race(), window_s="past")
    early = out[out["NUMBER"].eq("1") & out["LAP_NUMBER"].le(3)]
    assert early["candidate_traffic_count"].isna().all()


def test_past_window_leaves_caution_and_pit_laps_out_of_the_running_median():
    frame = past_race()
    hypercar = frame["NUMBER"].eq("1")
    frame.loc[hypercar & frame["LAP_NUMBER"].eq(2), ["LAP_TIME_S", "is_caution_lap"]] = [150.0, True]
    frame.loc[hypercar & frame["LAP_NUMBER"].eq(3), ["LAP_TIME_S", "is_pit_lap"]] = [160.0, True]
    frame = frame.sort_values(["event_key", "NUMBER", "LAP_NUMBER"]).reset_index(drop=True)
    frame["lap_start_s"] = frame.groupby(["event_key", "NUMBER"])["ELAPSED_S"].shift()
    gap = pd.Series(past_class_pace_gap(frame, min_laps=2), index=frame.index)
    # Lap 7 starts at t=604: usable Hypercar laps done are 4 and 5 (100 s), so the gap is 12 s.
    # With the caution and pit laps counted, the median would be 125 s and the gap -13 s.
    assert gap[frame["NUMBER"].eq("1") & frame["LAP_NUMBER"].eq(7)].iloc[0] == 12.0


def three_class_race() -> pd.DataFrame:
    """Made-up Le Mans-style crossings with usable laps so each pair has a pace gap.

    Medians: Hypercar 200 s, LMP2 210 s, GT3 230 s, so the windows are 10 s (HY-P2), 30 s (HY-GT3)
    and 20 s (P2-GT3).
    """
    rows = []
    for car, car_class, lap_time, offset in (("1", "HYPERCAR", 200.0, 0.0), ("31", "LMP2", 210.0, -5.0), ("51", "LMGT3", 230.0, -25.0)):
        for lap in range(1, 4):
            rows.append((car, car_class, lap, offset + lap * lap_time, lap_time))
    frame = pd.DataFrame(rows, columns=["NUMBER", "CLASS", "LAP_NUMBER", "ELAPSED_S", "LAP_TIME_S"])
    return frame.assign(event_key="LM", CROSSING_FINISH_LINE_IN_PIT="", is_usable_for_pace_model=True)


def test_each_other_class_is_counted_with_its_own_window():
    out = add_class_pair_counts(three_class_race())
    hypercar_lap2 = out[(out["NUMBER"] == "1") & (out["LAP_NUMBER"] == 2)].iloc[0]
    # Lap 2 starts at t=200. The LMP2 and the GT3 both cross next at t=205, behind the Hypercar, so neither is ahead.
    assert hypercar_lap2["count_LMP2"] == 0 and hypercar_lap2["count_LMGT3"] == 0
    assert pd.isna(hypercar_lap2["count_HYPERCAR"])


def test_pair_counts_pick_up_cars_ahead_and_behind():
    frame = three_class_race()
    extra = pd.DataFrame([("32", "LMP2", 7, 195.0, 210.0), ("52", "LMGT3", 7, 180.0, 230.0), ("2", "HYPERCAR", 7, 215.0, 200.0)],
                         columns=["NUMBER", "CLASS", "LAP_NUMBER", "ELAPSED_S", "LAP_TIME_S"]).assign(
        event_key="LM", CROSSING_FINISH_LINE_IN_PIT="", is_usable_for_pace_model=False)
    out = add_class_pair_counts(pd.concat([frame, extra]))
    hypercar = out[(out["NUMBER"] == "1") & (out["LAP_NUMBER"] == 2)].iloc[0]
    assert hypercar["count_LMP2"] == 1      # LMP2 at 195, 5 s ahead, inside 10 s
    assert hypercar["count_LMGT3"] == 1     # GT3 at 180, 20 s ahead, inside 30 s
    lmp2 = out[(out["NUMBER"] == "31") & (out["LAP_NUMBER"] == 2)].iloc[0]
    # LMP2 lap 2 starts at 205: Hypercar 2 crosses at 215, 10 s behind, outside [0, 10).
    assert lmp2["count_HYPERCAR"] == 0
    assert hypercar["candidate_traffic_count"] == 2


def test_gt3_counts_two_faster_classes_behind_with_their_own_windows_and_skips_the_pit_lane():
    # GT3 lap 2 starts at t=205. Windows behind: LMP2 20 s, so [205, 225); Hypercar 30 s, so [205, 235).
    frame = three_class_race()
    extra = pd.DataFrame([
        ("2", "HYPERCAR", 7, 220.0, ""),     # 15 s behind: in the Hypercar window
        ("33", "LMP2", 7, 210.0, "B"),       # in the window but in the pit lane
        ("34", "LMP2", 7, 250.0, ""),        # 45 s behind: in the LMP2 far window [245, 265)
    ], columns=["NUMBER", "CLASS", "LAP_NUMBER", "ELAPSED_S", "CROSSING_FINISH_LINE_IN_PIT"]).assign(
        event_key="LM", LAP_TIME_S=999.0, is_usable_for_pace_model=False)
    out = add_class_pair_counts(pd.concat([frame, extra]))
    gt3 = out[(out["NUMBER"] == "51") & (out["LAP_NUMBER"] == 2)].iloc[0]
    assert gt3["count_HYPERCAR"] == 1
    assert gt3["count_LMP2"] == 1          # car 31 crosses at exactly 205, the start of the window
    assert gt3["far_LMP2"] == 1
    assert pd.isna(gt3["count_LMGT3"]) and pd.isna(gt3["far_LMGT3"])
