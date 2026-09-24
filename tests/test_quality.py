from __future__ import annotations

import pandas as pd
import pytest

from endurance_strategy.io.load import load_race_csv
from endurance_strategy.paths import FIXTURES_DIR
from endurance_strategy.validation.quality import (
    find_duplicate_laps,
    find_elapsed_time_regressions,
    find_lap_number_breaks,
)

FIXTURE = FIXTURES_DIR / "synthetic_race.CSV"


@pytest.fixture
def clean() -> pd.DataFrame:
    return load_race_csv(FIXTURE)


def test_fixture_shape(clean: pd.DataFrame) -> None:
    assert len(clean) == 12
    assert clean["NUMBER"].nunique() == 3
    assert set(clean["CLASS"]) == {"HYPERCAR", "LMGT3"}


def test_car_number_keeps_leading_zero(clean: pd.DataFrame) -> None:
    assert "007" in set(clean["NUMBER"])
    assert "7" in set(clean["NUMBER"])
    assert clean.loc[clean["NUMBER"] == "007", "LAP_NUMBER"].tolist() == [1, 2, 3, 4]


def test_trailing_semicolon_column_is_dropped(clean: pd.DataFrame) -> None:
    assert not [c for c in clean.columns if c.startswith("Unnamed:") or c == ""]


def test_both_duration_formats_parse(clean: pd.DataFrame) -> None:
    first = clean.iloc[0]
    assert first["LAP_TIME_S"] == pytest.approx(210.0)
    assert first["ELAPSED_S"] == pytest.approx(210.0)

    out_lap = clean[clean["PIT_TIME"] != ""].iloc[0]
    assert out_lap["PIT_TIME_S"] == pytest.approx(75.0)


def test_clean_fixture_passes_every_check(clean: pd.DataFrame) -> None:
    assert find_duplicate_laps(clean).empty
    assert find_elapsed_time_regressions(clean).empty
    assert find_lap_number_breaks(clean).empty


def test_duplicate_lap_is_detected(clean: pd.DataFrame) -> None:
    corrupt = pd.concat([clean, clean.iloc[[5]]], ignore_index=True)

    found = find_duplicate_laps(corrupt)

    assert len(found) == 2
    assert set(found["NUMBER"]) == {"7"}
    assert set(found["LAP_NUMBER"]) == {2}


def test_same_car_number_in_two_events_is_not_a_duplicate(clean: pd.DataFrame) -> None:
    other = clean.copy()
    other["event_key"] = "2026_SYNTHETIC_OTHER"

    assert find_duplicate_laps(pd.concat([clean, other], ignore_index=True)).empty


def test_elapsed_going_backwards_is_detected(clean: pd.DataFrame) -> None:
    corrupt = clean.copy()
    corrupt.loc[2, "ELAPSED_S"] = 400.0

    found = find_elapsed_time_regressions(corrupt)

    assert len(found) == 1
    assert found.iloc[0]["NUMBER"] == "007"
    assert found.iloc[0]["LAP_NUMBER"] == 3


def test_elapsed_standing_still_is_detected(clean: pd.DataFrame) -> None:
    corrupt = clean.copy()
    corrupt.loc[2, "ELAPSED_S"] = corrupt.loc[1, "ELAPSED_S"]

    assert len(find_elapsed_time_regressions(corrupt)) == 1


def test_elapsed_check_ignores_row_order(clean: pd.DataFrame) -> None:
    shuffled = clean.sample(frac=1, random_state=0)

    assert find_elapsed_time_regressions(shuffled).empty


def test_elapsed_is_not_compared_across_cars(clean: pd.DataFrame) -> None:
    assert find_elapsed_time_regressions(clean).empty


def test_lap_gap_is_detected(clean: pd.DataFrame) -> None:
    corrupt = clean.drop(index=2)

    found = find_lap_number_breaks(corrupt)

    assert len(found) == 1
    assert found.iloc[0]["NUMBER"] == "007"
    assert found.iloc[0]["LAP_NUMBER"] == 4


def test_repeated_lap_number_is_detected(clean: pd.DataFrame) -> None:
    corrupt = clean.copy()
    corrupt.loc[2, "LAP_NUMBER"] = 2

    assert len(find_lap_number_breaks(corrupt)) == 2


def test_first_lap_of_each_car_is_not_flagged(clean: pd.DataFrame) -> None:
    found = find_lap_number_breaks(clean)

    assert found.empty


def test_driver_change_does_not_break_the_sequence(clean: pd.DataFrame) -> None:
    assert clean.loc[3, "DRIVER_NUMBER"] != clean.loc[2, "DRIVER_NUMBER"]
    assert find_lap_number_breaks(clean).empty


def test_lap_sequence_is_not_compared_across_events(clean: pd.DataFrame) -> None:
    other = clean.copy()
    other["event_key"] = "2026_SYNTHETIC_OTHER"

    assert find_lap_number_breaks(pd.concat([clean, other], ignore_index=True)).empty
