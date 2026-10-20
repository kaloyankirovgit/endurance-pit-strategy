from __future__ import annotations

import pandas as pd
import pytest

from endurance_strategy.validation.classification import (
    compare_to_classification,
    load_classification,
    rebuilt_final_order,
    summarise_by_race,
)

# Synthetic three-lap race. Car 1 wins, car 2 is second on the road but gets a 30 s penalty
# that drops it behind car 3, car 4 crosses three times but is officially credited two laps,
# and car 5 retires after one lap.
LAPS = pd.DataFrame(
    [
        ("1", 1, 100.0), ("1", 2, 200.0), ("1", 3, 300.0),
        ("2", 1, 101.0), ("2", 2, 201.0), ("2", 3, 301.0),
        ("3", 1, 110.0), ("3", 2, 215.0), ("3", 3, 320.0),
        ("4", 1, 120.0), ("4", 2, 240.0), ("4", 3, 360.0),
        ("5", 1, 130.0),
    ],
    columns=["NUMBER", "LAP_NUMBER", "ELAPSED_S"],
).assign(event_key="SYN")

# Retired car has a blank POSITION and the columns are not in the usual order, as in the 2024 Spa file.
CLASSIFICATION_CSV = """﻿NUMBER;POSITION;LAPS;STATUS;CLASS;TOTAL_TIME;TEAM
1;1;3;Classified;HYPERCAR;0:05'00.000;A
3;2;3;Classified;HYPERCAR;0:05:20.000;B
2;3;3;Classified;HYPERCAR;0:05'31.000;C
4;4;2;Classified;LMGT3;0:06'05.500;D
5;;1;Retired;LMGT3;0:02'10.000;E
"""


@pytest.fixture
def classification(tmp_path):
    path = tmp_path / "SYN.CSV"
    path.write_text(CLASSIFICATION_CSV, encoding="utf-8")
    return load_classification(path)


def test_load_reads_columns_by_name_and_both_time_formats(classification):
    car = classification.set_index("NUMBER")
    assert car.loc["3", "official_time_s"] == pytest.approx(320.0)
    assert car.loc["2", "official_time_s"] == pytest.approx(331.0)
    assert pd.isna(car.loc["5", "official_position"])
    assert car.loc["5", "official_status"] == "Retired"


def test_rebuilt_final_order_ranks_laps_then_time():
    final = rebuilt_final_order(LAPS).set_index("NUMBER")
    assert final["rebuilt_position"].to_dict() == {"1": 1, "2": 2, "3": 3, "4": 4, "5": 5}
    assert final.loc["4", "rebuilt_laps"] == 3


def test_rebuilt_final_order_breaks_ties_on_car_number():
    tied = pd.DataFrame([("9", 1, 100.0), ("10", 1, 100.0)], columns=["NUMBER", "LAP_NUMBER", "ELAPSED_S"]).assign(event_key="T")
    assert rebuilt_final_order(tied)["NUMBER"].tolist() == ["10", "9"]


def test_differences_are_labelled(classification):
    out = compare_to_classification(LAPS, classification).set_index("NUMBER")
    assert out["difference"].to_dict() == {
        "1": "exact", "3": "exact", "2": "time_penalty", "4": "fewer_official_laps", "5": "exact",
    }
    assert out.loc["2", "time_diff_s"] == pytest.approx(-30.0)


def test_penalty_breaks_raw_position_match_but_not_unpenalised_order(classification):
    out = compare_to_classification(LAPS, classification).set_index("NUMBER")
    assert out.loc[["2", "3"], "position_match"].tolist() == [False, False]
    assert out.loc[["1", "3"], "unpenalised_order_match"].all()
    assert not out.loc["5", "position_match"]


def test_missing_cars_show_up_on_both_sides(classification):
    extra = pd.concat([LAPS, pd.DataFrame([("6", 1, 140.0)], columns=["NUMBER", "LAP_NUMBER", "ELAPSED_S"]).assign(event_key="SYN")])
    trimmed = classification[classification["NUMBER"] != "1"]
    summary = summarise_by_race(compare_to_classification(extra, trimmed)).loc["SYN"]
    assert summary["missing_from_official"] == 2
    assert summary["missing_from_rebuild"] == 0
