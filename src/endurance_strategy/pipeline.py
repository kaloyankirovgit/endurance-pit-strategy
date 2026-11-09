from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from endurance_strategy.features.clean_laps import add_clean_lap_flags
from endurance_strategy.features.weather import join_weather
from endurance_strategy.io.download import PRACTICE_DIR, WEATHER_DIR
from endurance_strategy.io.load import load_corpus, load_race_csv
from endurance_strategy.io.weather import load_weather_corpus
from endurance_strategy.paths import INTERIM_DIR, PROCESSED_DIR, WEC_DIR
from endurance_strategy.reconstruct.race_clock import add_lap_utc
from endurance_strategy.reconstruct.race_order import add_race_order
from endurance_strategy.reconstruct.stints import add_garage_stop_flag, add_stint_columns
from endurance_strategy.validation.schema import INTERIM_LAPS

STINTS_SQL = """
SELECT
    event_key, NUMBER, CLASS, stint_number,
    arg_min(DRIVER_NAME, LAP_NUMBER) AS driver,
    MIN(LAP_NUMBER) AS first_lap,
    MAX(LAP_NUMBER) AS last_lap,
    COUNT(*) AS laps,
    SUM(is_usable_for_pace_model::INTEGER) AS clean_laps,
    MEDIAN(LAP_TIME_S) FILTER (WHERE is_usable_for_pace_model) AS median_clean_lap_s,
    BOOL_OR(is_in_lap) AS ended_in_pit,
    BOOL_OR(is_garage_stop) AS started_from_garage
FROM laps
GROUP BY event_key, NUMBER, CLASS, stint_number
ORDER BY event_key, NUMBER, stint_number
"""

PIT_STOPS_SQL = """
WITH marked AS (
    SELECT
        *,
        DRIVER_NUMBER <> LAG(DRIVER_NUMBER) OVER (PARTITION BY event_key, NUMBER ORDER BY LAP_NUMBER) AS driver_changed
    FROM laps
)
SELECT
    event_key, NUMBER, CLASS, LAP_NUMBER AS out_lap, stint_number,
    PIT_TIME_S, is_garage_stop, FLAG_AT_FL, DRIVER_NAME AS driver_out,
    COALESCE(driver_changed, FALSE) AS driver_changed
FROM marked
WHERE is_out_lap
ORDER BY event_key, NUMBER, out_lap
"""


def build_interim_laps(race_dir: Path = WEC_DIR, weather_dir: Path = WEATHER_DIR,
                       race_dates: dict[str, date] | None = None) -> pd.DataFrame:
    laps = add_garage_stop_flag(add_stint_columns(load_corpus(race_dir)))
    laps = add_race_order(laps)
    laps = join_weather(add_lap_utc(laps, race_dates), load_weather_corpus(weather_dir))
    laps = add_clean_lap_flags(laps).reset_index(drop=True)
    return INTERIM_LAPS.validate(laps)


def build_practice_laps(practice_dir: Path = PRACTICE_DIR) -> pd.DataFrame:
    """Practice laps, one file per session, each named `<race event key>__FP<n>`. No clean-lap rule yet: that's E-020's."""
    frames = []
    for path in sorted(practice_dir.glob("*.CSV")):
        race_key, session = path.stem.split("__")
        session_laps = add_stint_columns(load_race_csv(path).assign(event_key=race_key))
        frames.append(session_laps.assign(session=session))
    return pd.concat(frames, ignore_index=True)


def build_processed(laps: pd.DataFrame) -> dict[str, pd.DataFrame]:
    con = duckdb.connect()
    con.register("laps", laps)
    tables = {"stints": con.execute(STINTS_SQL).df(), "pit_stops": con.execute(PIT_STOPS_SQL).df()}
    con.close()
    return tables


def run(race_dir: Path = WEC_DIR, weather_dir: Path = WEATHER_DIR, interim_dir: Path = INTERIM_DIR,
        processed_dir: Path = PROCESSED_DIR, race_dates: dict[str, date] | None = None,
        practice_dir: Path | None = None) -> dict[str, int]:
    """Raw race and weather CSVs to validated Parquet tables."""
    interim_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    laps = build_interim_laps(race_dir, weather_dir, race_dates)
    laps.to_parquet(interim_dir / "laps.parquet", index=False)

    counts = {"laps": len(laps)}
    for name, table in build_processed(laps).items():
        table.to_parquet(processed_dir / f"{name}.parquet", index=False)
        counts[name] = len(table)
    if practice_dir is not None and any(practice_dir.glob("*.CSV")):
        practice = build_practice_laps(practice_dir)
        practice.to_parquet(interim_dir / "practice_laps.parquet", index=False)
        counts["practice_laps"] = len(practice)
    return counts


if __name__ == "__main__":
    for name, rows in run(practice_dir=PRACTICE_DIR).items():
        print(f"{name:10s} {rows:>8,}")
