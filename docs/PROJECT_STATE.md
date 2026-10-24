# Project state

Where things are right now. Updated at the end of each working session.

*Last updated: 2026-10-24*

## Current stage

Layer 1 is done and the race order is now checked against the official classifications. The first traffic result is in (E-013). A commit guard now enforces the no-data rule (D-016). The statistical-reviewer agent has an eval (E-008), and regulation retrieval and grounded answers are built and measured, now with the car class as an input (E-009 to E-012). The next choice is between the remaining regulation checks and the traffic work.

## Done

- Repo and project rules set up. CI runs on GitHub Actions on every push.
- All 28 races from 2023 to 2026 downloaded, with a manifest of hashes. The main corpus is 2024 to 2026, with 21 races and 179,259 laps (D-010).
- `io/load.py` reads the race CSVs and handles the format quirks.
- `validation/quality.py` has three structural checks. All return zero across the corpus, and each has been proven to fire (E-002).
- `reconstruct/stints.py` flags in-laps and out-laps and numbers stints. The pit columns are fully explained (E-003, D-011): 10,577 stints, and all 3,478 driver changes land on out-laps.
- Weather downloaded for all 21 races and joined to every lap through each circuit's time zone (E-005, D-013).
- Garage visits separated from normal stops: 185 stops over 3× the race median.
- `features/clean_laps.py` flags laps unfit for pace modelling, rain included. 138,884 of 179,259 laps are usable (E-004, E-005).
- `pipeline.py` runs everything in about 13 seconds: raw CSVs to `interim/laps.parquet`, plus `processed/stints.parquet` and `processed/pit_stops.parquet`. Pandera validates the lap table on write (E-006, D-014).
- `reconstruct/race_order.py` adds position and gaps at each crossing in DuckDB SQL, including the road gap and class of the car ahead on track.
- Race order checked against the official `03_Classification` files for all 21 races. Lap counts match for 830 of 833 cars and finishing times to the millisecond for 782. The 51 differences fit post-race penalties (E-007).
- A commit guard blocks any commit that includes a git-ignored file, both as a Claude Code hook and as the git pre-commit hook (D-016).
- An eval for the `statistical-reviewer` agent: 16 synthetic cases, each run 3 times. It caught 11 of 12 planted flaws and raised no majority false alarm on the 4 controls. One control alarm turned out to be a real flaw in E-007, now corrected (E-008).
- The 2024 to 2026 sporting regulations are downloaded with hashes and split into 855 article-level chunks. Keyword retrieval (BM25) finds the right 2026 clause in the top 5 for 24 of 30 hand-written questions (E-009).
- Regulation answers are routed, grounded and checked in code (D-019). When retrieval finds the right clause, the answer cites it in 72 of 72 runs, and strategy questions are declined (E-010). Embeddings and a hybrid were compared with BM25 on a fresh question set, and the gap is too small to settle with 30 questions, so BM25 stays the default (E-011, D-020).
- Answers follow the car class the user picks (D-021). On 5 questions asked for each class, the chosen class's fact was present in 30 of 30 runs and the other class's showed up in 1 of 24 checked runs. LMP2 is refused, because the corpus covers only Hypercar and LMGT3 (E-012).
- First traffic result (E-013, D-022). Within the same stint, a Hypercar lap is 0.37 s longer (0.33 to 0.41, resampling 18 races) for each LMGT3 car close enough ahead at the start of the lap to be caught. It's an association with inferred exposure, and the per-car figure moves from 0.26 to 0.41 s with the window. Two placebos (cars too far ahead, and the car's own count two laps later) are null.
- 145 tests, all running on synthetic data with no real data needed. One fails if any git-ignored file is ever committed.

## Next

1. **Regulations, remaining checks**
   - In-scope refusal tests (questions the router passes but the regulations don't answer), a larger question set to settle BM25 against the hybrid, and a cleaner extraction of the tyre tables (6.5.3, 6.5.4).
2. **Traffic, second round (Layer 2)**
   - The other direction (LMGT3 cars being lapped), a held-out check (fit 2024 to 2025, test 2026), a past-only window for the simulator, and Le Mans with three classes as its own study.
3. **Drying track**
   - Find a way to catch laps on a wet track after the rain sensor reads zero.
4. **Reviewer eval, second round**
   - A fresh held-out case set before changing the agent prompt (it rated "measured overtakes" as minor), then the other three agents.

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
| Interim / processed layers | Built as one command, writing schema-checked Parquet |
| Race order and gaps | Built, and the final order checked against the official classifications (E-007) |
| Traffic, pace and pit-loss models | Traffic baseline built and reviewed (E-013); pace and pit loss not started |
| Simulator and optimiser | Not started |
| Regulations and LLM layer | Retrieval (E-009, E-011), grounded answers with a code checker (E-010) and class-aware answers (E-012) built and measured; no simulator tool yet |
| CI | Running on GitHub Actions, passing |
| Commit guard hooks | Built and tested (D-016) |
| Review-agent evals | statistical-reviewer evaluated, 16 cases × 3 runs (E-008) |
