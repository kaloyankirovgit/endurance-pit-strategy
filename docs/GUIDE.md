# GUIDE

Plain explanation of what exists and how to run it.

---

## 1. Commands

```bash
cd ~/Projects/endurance-pit-strategy-planner
source .venv/bin/activate
```

Run the tests:

```bash
python -m pytest tests/ -q
```

Load one race and check it:

```bash
python -c "
from endurance_strategy.io.load import load_race_csv
from endurance_strategy.paths import race_path
from endurance_strategy.validation import quality
df = load_race_csv(race_path('2025_LE_MANS'))
print(len(df), 'laps')
print('dupes     ', len(quality.find_duplicate_laps(df)))
print('elapsed   ', len(quality.find_elapsed_time_regressions(df)))
print('lap breaks', len(quality.find_lap_number_breaks(df)))
"
```

Same across all 21 races — swap `load_race_csv(race_path(...))` for
`load_corpus(WEC_DIR)` and import `load_corpus` and `WEC_DIR`.

Explore interactively: open `notebooks/exploration/explore_quality.py` in
VS Code and click "Run Cell" above each `# %%`.

---

## 2. What each file does

| File | What it does |
|---|---|
| `src/endurance_strategy/paths.py` | Absolute paths. `race_path("2025_LE_MANS")` gives the CSV's location from anywhere. |
| `src/endurance_strategy/io/load.py` | Reads a race CSV into a dataframe. Handles the source's five format quirks. |
| `src/endurance_strategy/validation/quality.py` | Three checks for structural faults. Each returns the bad rows. |
| `tests/fixtures/synthetic_race.CSV` | Fake 3-car, 4-lap race. Small enough to read by eye. Safe to commit. |
| `tests/test_quality.py` | 16 tests. Breaks the fixture on purpose and checks each fault is caught. |
| `notebooks/exploration/explore_quality.py` | Scratch space. Loads real data. Not imported by anything. |

---

## 3. The data

One row = one lap by one car. 29 columns from the source.

The four that matter for the checks:

| Column | What it is |
|---|---|
| `event_key` | Which race. Added by the loader from the filename. |
| `NUMBER` | Car number. A **string** — `"007"` is not `7`. |
| `LAP_NUMBER` | Integer, starts at 1 for each car. |
| `ELAPSED_S` | Race time in seconds at that lap. Added by the loader. |

The loader adds `_S` columns (seconds) next to the original text columns:
`LAP_TIME_S`, `PIT_TIME_S`, `ELAPSED_S`, `S1_S`, `S2_S`, `S3_S`.

Full column list: `docs/DATA_DICTIONARY.md`.

---

## 4. How the three checks work

All three follow the same shape:

```
sort the rows  →  group by car  →  compare each row to the one before  →  keep the bad ones
```

**Why group by car.** Elapsed time only increases within one car. Lap numbers
restart at 1 for every car. Comparing across cars is meaningless.

**Why the car key is `event_key` + `NUMBER`.** Car `7` runs in all 21 races. Using
`NUMBER` alone would compare Fuji's lap 40 against Le Mans's lap 39.

**Why not `DRIVER_NUMBER`.** A car's laps continue through a driver change. Adding
the driver to the key would report a fault at every driver swap.

**Why sort inside the function.** `.diff()` compares against the previous row in
whatever order the frame happens to be in. It does not sort for you.

**The `NaN` catch.** `.diff()` gives `NaN` on each car's first lap — there is no
previous lap. In Python `NaN != 1` is `True`, so a plain `step != 1` flags every
car's lap 1 as a fault. `find_lap_number_breaks` excludes them with `.notna()`.
`find_elapsed_time_regressions` uses `step <= 0`, and `NaN <= 0` is `False`, so it
excludes them already.

---

## 5. Why the tests break things on purpose

All three checks return **zero** faults across 179,259 laps.

A zero can mean two things: the data is clean, or the check is broken and would
return zero no matter what. You cannot tell them apart by looking at the zero.

So each check is broken deliberately and the tests are re-run. If the tests still
pass, the check was never really testing anything.

Five versions were tried:

| Broken version | Tests that failed |
|---|---|
| Removed the `NaN` guard | 6 |
| Removed the sort | 1 |
| Grouped by car **and driver** | 2 |
| Dropped `event_key` from the key | 2 |
| Used `< 0` instead of `<= 0` | 1 |

All five were caught, so the zero is trustworthy.

To reproduce: edit `quality.py`, make one of those changes, run `pytest`, then undo it.

---

## 6. Current state

Done: loader, three structural checks, tests, fixture. Result logged as E-002 in
`docs/EXPERIMENT_LOG.md`.

Not done: `data/interim/`, `data/processed/`, Parquet, DuckDB, schema contracts,
any model, the simulator.

Still open in the data itself:

- What `CROSSING_FINISH_LINE_IN_PIT = B` marks (in-lap, out-lap, or both).
- What `PIT_TIME` measures, and why 1,902 pit crossings give only 1,896 values.
- What counts as a "usable clean lap".

The first two block stint detection, which blocks Layer 2.

---

## 7. Next steps

1. **Push to GitHub and get CI running.** The workflow file exists but has never
   run. The tests need no data, so they will pass on a runner.
2. **Settle the pit columns.** Inspect rows where `CROSSING_FINISH_LINE_IN_PIT`
   is `B`, compare lap times against the car's normal pace, and work out which
   lap the marker sits on. Record it in `DATA_DICTIONARY.md` and `DECISIONS.md`.
3. **Define a usable clean lap**, with counts and the effect of each exclusion.
4. **Layer 1** — raw → interim → processed, Parquet output, DuckDB queries,
   schema contracts.

---

## 8. The three things worth being able to explain

For interviews, since this is the part that is hard to fake:

1. **A zero from an untested check means nothing.** That is why the mutation
   testing in section 5 exists.
2. **The grouping key is a modelling decision.** `event_key` in, `DRIVER_NUMBER`
   out — each for a specific reason, each pinned by a test.
3. **`NaN != 1` is `True`.** It silently flags every car's first lap, and the
   result looks plausible enough that nobody would question it.
