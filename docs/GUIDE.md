# Guide

How to run what exists so far, and how it works underneath.

## Running things

Rebuild every table from the raw files:

```bash
python -m endurance_strategy.pipeline
```

That writes `data/interim/laps.parquet`, `data/processed/stints.parquet` and `data/processed/pit_stops.parquet`. Query them straight from DuckDB:

```python
import duckdb
duckdb.sql("SELECT CLASS, COUNT(*) FROM 'data/interim/laps.parquet' GROUP BY 1")
```

```bash
cd endurance-pit-strategy-planner
source .venv/bin/activate
python -m pytest -q
```

Load a race, check it and add stints:

```python
from endurance_strategy.io.load import load_race_csv, load_corpus
from endurance_strategy.paths import race_path, WEC_DIR
from endurance_strategy.validation import quality
from endurance_strategy.reconstruct.stints import add_stint_columns

laps = load_race_csv(race_path("2025_LE_MANS"))
quality.find_lap_number_breaks(laps)

corpus = add_stint_columns(load_corpus(WEC_DIR))
```

`load_corpus` loads 2024 to 2026 by default. For quick poking around there's `notebooks/exploration/explore_quality.py` — open it in VS Code and hit "Run Cell".

## What's where

| File | What it does |
|---|---|
| `src/endurance_strategy/io/load.py` | Reads a race CSV and adds parsed columns in seconds next to the originals |
| `src/endurance_strategy/validation/quality.py` | Structural checks. Each returns the bad rows, not just true or false |
| `src/endurance_strategy/reconstruct/stints.py` | In-lap and out-lap flags, stint numbers |
| `src/endurance_strategy/io/weather.py` | Reads the weather CSVs |
| `src/endurance_strategy/io/download.py` | Downloads the weather for each race and records hashes |
| `src/endurance_strategy/reconstruct/race_clock.py` | UTC time for each lap |
| `src/endurance_strategy/features/weather.py` | Joins the latest weather reading to each lap |
| `src/endurance_strategy/reconstruct/race_order.py` | Position and gaps at each crossing, in DuckDB SQL |
| `src/endurance_strategy/validation/schema.py` | Pandera schema the lap table must pass before it's written |
| `src/endurance_strategy/pipeline.py` | The one command that builds everything |
| `src/endurance_strategy/features/clean_laps.py` | Flags for laps that shouldn't feed a pace model, plus a summary of what each rule removes |
| `src/endurance_strategy/paths.py` | Absolute paths, so things work from any folder |
| `tests/fixtures/synthetic_race.CSV` | A made-up race small enough to check by eye |

## The loader

The raw files have a few traps. There's a BOM at the start, and the first 15 headers begin with a space, so `df["DRIVER_NUMBER"]` silently finds nothing unless they're stripped. Durations come in two formats (`3:54.555` and `0:01:15.964`) — `parse_duration` splits on the colons and works from the right, so it doesn't need to know which one it has. Car numbers are read as strings, because `007` and `7` are different cars.

Nothing is renamed or dropped. The parsed columns are added alongside the originals with an `_S` suffix, so the raw values are always there to check against.

## The structural checks

All three work the same way: group the laps by car in lap order, then compare each lap with the one before it.

**A car is `event_key` plus `NUMBER`.** Car 7 races in every event, so the number alone would compare Fuji's lap 40 with Le Mans' lap 39. The driver isn't part of the key — a car's laps carry straight on through a driver change.

**Sorting happens inside the function.** `.diff()` compares against whatever row happens to be above, so it can't rely on the input already being sorted.

**Watch out for NaN.** `.diff()` gives NaN on each car's first lap. In Python `NaN != 1` is `True`, so a plain `step != 1` flags every first lap as a fault. The lap-number check adds `.notna()` to avoid that.

All three return zero across the corpus. To make sure that zero means something, I broke each check deliberately and re-ran the tests:

| What I broke | Tests that failed |
|---|---:|
| Removed the NaN guard | 6 |
| Removed the sort | 1 |
| Grouped by car and driver | 2 |
| Dropped `event_key` from the key | 2 |
| Used `< 0` instead of `<= 0` | 1 |

Every one got caught.

## Stints

In the source, `B` in `CROSSING_FINISH_LINE_IN_PIT` marks the in-lap and `PIT_TIME` sits on the out-lap after it (E-003 has the evidence). From there:

- `is_in_lap` is just the `B`, and `is_out_lap` is whether `PIT_TIME` has a value.
- `stint_number` is a running count of out-laps per car, plus one. The out-lap opens the new stint, so the in-lap stays as the last lap of the old one.
- A car starting from the pit lane has an out-lap on lap 1. That's skipped when counting, so it's still stint 1.
- `stint_lap` is `cumcount() + 1` within each car and stint.

The tests cover the awkward cases — a pit-lane start, a car retiring in the pits, two cars with the same number in different events, and shuffled input.

## Clean laps

`add_clean_lap_flags` runs after `add_stint_columns` and adds one column per reason a lap might be left out, plus `is_usable_for_pace_model` for laps with none of them. Nothing is deleted, so a different model can pick a different combination.

The slow-lap rule compares each lap with the median green, non-pit lap for its class at that race. Pit and caution laps are kept out of that median — otherwise a long safety car would drag it up and hide slow laps. `exclusion_summary` shows how many laps each rule catches, and how many only that rule catches.

## Weather and garage stops

The full chain, from raw files to flagged laps:

```python
from endurance_strategy.io.download import WEATHER_DIR
from endurance_strategy.io.weather import load_weather_corpus
from endurance_strategy.reconstruct.race_clock import add_lap_utc
from endurance_strategy.reconstruct.stints import add_garage_stop_flag
from endurance_strategy.features.weather import join_weather
from endurance_strategy.features.clean_laps import add_clean_lap_flags

laps = add_garage_stop_flag(add_stint_columns(load_corpus(WEC_DIR)))
laps = join_weather(add_lap_utc(laps), load_weather_corpus(WEATHER_DIR))
laps = add_clean_lap_flags(laps)
```

The lap's UTC time comes from `HOUR`, not `ELAPSED`. `ELAPSED` stops during a red flag, and at Spa 2024 that would have put the weather two hours out. `merge_asof` then picks the latest reading at or before each crossing, only within the same race.

## What's next

- Check race order against the official classifications.
- Start the traffic exposure work.
