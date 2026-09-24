# Project state

Where things are right now. Updated at the end of each working session.

*Last updated: 2026-09-24*

## Current stage

Layer 1, the data pipeline, is about half done. The 21-race corpus loads cleanly and passes the structural checks, and pit stops and stints are now rebuilt from it. There's no interim or processed layer yet, and nothing is modelled.

## Done

- Repo and project rules set up. CI workflow written, but it hasn't run yet because the repo isn't on GitHub.
- All 28 races from 2023 to 2026 downloaded, with a manifest of hashes. The main corpus is 2024 to 2026 — 21 races and 179,259 laps (D-010).
- `io/load.py` reads the race CSVs and handles the format quirks.
- `validation/quality.py` has three structural checks. All return zero across the corpus, and each has been proven to fire (E-002).
- `reconstruct/stints.py` flags in-laps and out-laps and numbers stints. The pit columns are fully explained (E-003, D-011): 10,577 stints, and all 3,478 driver changes land on out-laps.
- Weather downloaded for all 21 races and joined to every lap through each circuit's time zone (E-005, D-013).
- Garage visits separated from normal stops: 185 stops over 3× the race median.
- `features/clean_laps.py` flags laps unfit for pace modelling, rain included. 138,884 of 179,259 laps are usable (E-004, E-005).
- 55 tests, all running on synthetic data with no real data needed. One guards against CV files ever being committed.

## Next

1. **Layer 1 proper** — one command that runs raw to interim to processed in Parquet, queried with DuckDB and checked with Pandera.
2. **Race order and gaps** at each timing line. This is what the traffic work is built on.
3. **Drying track** — find a way to catch laps on a wet track after the rain sensor reads zero.

## Key facts

- The source is public and free to download, but it can't be redistributed. Nothing from it goes in Git.
- Every one of the 28 files has the same 29-column schema.
- Outside Le Mans, 2024 to 2026 is two-class (Hypercar and LMGT3). LMP2 only races at Le Mans.
- Only Le Mans (2025 and 2026) and COTA 2026 have the 15-point intra-lap timing.
- Weather is available every minute for every race. `ELAPSED` stops during red flags, so the weather join uses `HOUR`.
- The site's event selector sometimes returns the wrong event, so downloads must be verified.
- `B` in `CROSSING_FINISH_LINE_IN_PIT` is the in-lap, and `PIT_TIME` is on the out-lap.
- Environment: Python 3.13, with a project venv in `.venv/`. `uv` and the DuckDB CLI aren't installed; the DuckDB Python package will do.

## Open questions

- What the `IMPROVEMENT` and `S*_LARGE` columns mean.
- Where the 15 intermediate points are on track.
- What the `RAIN` scale means.
- Whether a separate race-control message file exists.

## Status by layer

| Component | Status |
|---|---|
| Loading | Built and tested |
| Structural checks | Built and run on the full corpus |
| Pits and stints | Built and run on the full corpus |
| Clean-lap flags | Built and run on the full corpus |
| Weather join and garage flag | Built and run on the full corpus |
| Interim / processed layers | Not started |
| Race order and gaps | Not started |
| Traffic, pace and pit-loss models | Not started |
| Simulator and optimiser | Not started |
| Regulations and LLM layer | Not started |
| CI | Written, not run yet |
