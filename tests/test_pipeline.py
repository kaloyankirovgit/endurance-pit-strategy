from __future__ import annotations

import shutil
from datetime import date

import pandas as pd
import pandera.errors
import pytest

from endurance_strategy.paths import FIXTURES_DIR
from endurance_strategy.pipeline import build_interim_laps, run
from endurance_strategy.validation.schema import INTERIM_LAPS

RACE_DATES = {"2025_LE_MANS": date(2025, 6, 14)}


@pytest.fixture
def source(tmp_path):
    races = tmp_path / "races"
    weather = tmp_path / "weather"
    races.mkdir()
    weather.mkdir()
    shutil.copy(FIXTURES_DIR / "synthetic_race.CSV", races / "2025_LE_MANS.CSV")
    start = int(pd.Timestamp("2025-06-14 11:00:00", tz="UTC").timestamp())
    rows = [f"{start + 60 * m};x;20.0;30.0;50;1013.0;5;180;0;" for m in range(40)]
    header = "TIME_UTC_SECONDS;TIME_UTC_STR;AIR_TEMP;TRACK_TEMP;HUMIDITY;PRESSURE;WIND_SPEED;WIND_DIRECTION;RAIN;"
    (weather / "2025_LE_MANS.CSV").write_text("\n".join([header, *rows]) + "\n")
    return races, weather, tmp_path


def test_pipeline_writes_every_table(source) -> None:
    races, weather, root = source
    counts = run(races, weather, root / "interim", root / "processed", RACE_DATES)
    assert counts == {"laps": 12, "stints": 4, "pit_stops": 1}
    stops = pd.read_parquet(root / "processed" / "pit_stops.parquet")
    assert stops.iloc[0]["NUMBER"] == "007"
    assert stops.iloc[0]["driver_changed"]


def test_every_lap_gets_weather(source) -> None:
    races, weather, _ = source
    laps = build_interim_laps(races, weather, RACE_DATES)
    assert laps["RAIN"].notna().all()


def test_pipeline_is_deterministic(source) -> None:
    races, weather, root = source
    run(races, weather, root / "a", root / "pa", RACE_DATES)
    run(races, weather, root / "b", root / "pb", RACE_DATES)
    pd.testing.assert_frame_equal(pd.read_parquet(root / "a" / "laps.parquet"), pd.read_parquet(root / "b" / "laps.parquet"))
    pd.testing.assert_frame_equal(pd.read_parquet(root / "pa" / "stints.parquet"), pd.read_parquet(root / "pb" / "stints.parquet"))


def test_schema_rejects_an_unknown_class(source) -> None:
    races, weather, _ = source
    laps = build_interim_laps(races, weather, RACE_DATES)
    laps.loc[0, "CLASS"] = "LMP1"
    with pytest.raises(pandera.errors.SchemaError):
        INTERIM_LAPS.validate(laps)


def test_schema_rejects_a_duplicate_lap(source) -> None:
    races, weather, _ = source
    laps = build_interim_laps(races, weather, RACE_DATES)
    with pytest.raises(pandera.errors.SchemaError):
        INTERIM_LAPS.validate(pd.concat([laps, laps.iloc[[0]]], ignore_index=True))
