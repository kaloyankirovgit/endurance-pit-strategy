# EXPERIMENT_LOG

A record of what was tried, what was found, and what it means. The project should accumulate a history of scientific decisions, not merely code commits.

**Log an experiment whenever a question is put to the data.** That includes exploratory checks, diagnostics and failed attempts. A negative or null result is logged with the same care as a positive one — it is often the more informative entry, and it is the entry that protects you from re-running the same dead end in three weeks.

Write the **Hypothesis** and **Validation design** sections *before* running the experiment. Filling them in afterwards turns an exploratory finding into a confirmatory-looking claim.

---

## Template

```
## E-NNN — Short title

EXPERIMENT ID:
DATE:
STATUS:            planned | running | complete | abandoned
QUESTION:          The specific question being asked of the data.
HYPOTHESIS:        What you expect, and what would count as being wrong.
DATASET:           Source files, events, sessions, pipeline version, commit hash.
POPULATION:        Which rows are in scope and which are excluded, with the reason
                   for each exclusion. State the units: races, circuits, cars,
                   drivers, stints, pit events, laps, sectors.
METHOD:            Estimator, model specification, software, seeds.
FEATURES:          Each feature labelled OBSERVED / RECONSTRUCTED / INFERRED /
                   ASSUMED / SIMULATED.
ASSUMPTIONS:       Everything the result depends on that the data do not establish.
VALIDATION DESIGN: Holdout structure (race-level, circuit-level, temporal), what
                   the tuning data were, what the evaluation data were, and how
                   leakage was prevented.
RESULT:            The numbers. No interpretation here.
UNCERTAINTY:       Intervals, their construction, and the clustering structure
                   they account for. Sensitivity to specification changes.
INTERPRETATION:    What this does and does not support. State the alternative
                   explanations that remain open.
DECISION / NEXT STEP:
```

---

## Standards for an entry

**Sample size is reported in the unit that matters.** "48,000 laps" is not a sample size for a traffic effect when those laps come from three races. Report races, circuits, cars, drivers, stints and pit events alongside lap and sector counts.

**Uncertainty accounts for clustering.** Laps within a stint, stints within a car, cars within a race are not independent. An interval built as though they were will be too narrow. Say which level of clustering the interval accounts for.

**Exclusions are listed with reasons.** In-laps, out-laps, FCY laps and laps with missing sectors will all be candidates for exclusion. Each exclusion is a modelling choice that can change the result — record it, and test the result's sensitivity to it.

**Specification changes are part of the result.** If an effect appears under one traffic threshold and vanishes under another, that instability *is* the finding.

**Tuning and evaluation data are named explicitly.** State which races each model component has seen. A result reported on races used for tuning is a fit statistic, not a generalisation claim.

**Label every quantity.** A feature that is INFERRED must not be described in the interpretation as though it were OBSERVED.

---

## Log

| ID | Date | Question | Status |
|---|---|---|---|
| E-001 | 2026-09-22 | What does the FIA WEC timing archive actually contain? | complete (descriptive) |
| E-002 | 2026-09-24 | Is the lap record structurally sound across the 21-race corpus? | complete (null result) |

---

## E-001 — What does the FIA WEC timing archive actually contain?

EXPERIMENT ID: E-001
DATE: 2026-09-22
STATUS: complete (descriptive); TASK 1 quality checks still outstanding
QUESTION: What data is accessible from the primary source, at what resolution, over what coverage — and does one race file contain the fields the project's modelling layers require?
HYPOTHESIS: `Strategy.md` assumed lap and 3-sector timing only, with weather "possibly if obtainable", and treated exact overtake localisation as impossible. Expected to confirm that picture.
DATASET: <https://fiawec.alkamelsystems.com/>, enumerated across all 15 season pages. Three files downloaded for the 2025 Le Mans race (`202506141600_Race`): `23_Analysis_Race_Hour 24.CSV`, `23_AnalysisEnduranceWithSections_Race_Hour 24.CSV`, `26_Weather_Race_Hour 24.CSV`. Hashes in `docs/research/data_sources.md`.
POPULATION: All 20,182 lap rows in the 2025 Le Mans race file. 62 cars, 186 drivers, 3 classes, 1 race, 1 circuit.
METHOD: Direct HTTP access; enumeration of season and event pages via the site's `?season=&evvent=` parameters; Python `csv` parsing and counting. No modelling.
FEATURES: All OBSERVED — no derived quantities computed.
ASSUMPTIONS: That the "Hour 24" file is race-wide cumulative rather than the final hour alone. Supported by its 20,182 rows against 62 cars (~325 laps each, consistent with a full 24-hour race), but not confirmed against an official lap chart.

RESULT:

- **Coverage:** 15 seasons (2011–2026), 121 events. Public access, no authentication, empty `robots.txt`.
- **Race-wide file exists** — a previously open question, now answered.
- **20,182 laps** in one race: Hypercar 21 cars / 7,710 laps, LMP2 17 / 5,779, LMGT3 24 / 6,693. 1,902 pit crossings.
- **Completeness is unusually high:** 0 missing lap times, 1 lap missing sector data out of 20,182.
- **Per-lap track status** in `FLAG_AT_FL`: GF 19,654 / SF 320 / FCY 159 / FF 49.
- **Per-minute weather** including track temperature and a rain flag — richer than `Strategy.md` anticipated.
- **15 intra-lap timing points** exist in `AnalysisEnduranceWithSections`, but only for Le Mans 2025, Le Mans 2026 and COTA 2026.

UNCERTAINTY: Schema verified on one file only. Consistency across 121 events and 15 seasons is unverified, and the 2011–2019 era predates the current class structure entirely. No uncertainty quantification applies — these are counts, not estimates.

INTERPRETATION:

The source is materially richer than the specification assumed, in two ways that matter.

**Weather is available at high resolution.** `Strategy.md` §17.3 listed track condition as a baseline feature "possibly if obtainable". It is obtainable at ~1-minute resolution including track temperature and rain. This is a genuine confounder for stint-degradation modelling that can now be controlled rather than acknowledged.

**Intra-lap resolution partially reopens D-004.** Fifteen segments per lap is roughly 5× finer than 3 sectors. It still does **not** observe overtakes — no segment boundary marks a passing event, and there is no ground-truth label — so the D-004 decision to model *inferred exposure* stands. But it substantially narrows where a lap-time loss occurred, which improves the chance the effect is identifiable at all. The limitation is availability: 3 race sessions, 2 circuits.

This creates the depth-versus-breadth trade-off recorded as D-009, which is unresolved and blocks the shape of Layer 2.

A caution on scale: 20,182 laps from one race is **one race**. For a traffic effect the effective sample size is closer to the number of independent encounters, and for generalisation it is the number of races. The large row count is not itself evidence of statistical power — see `.claude/rules/statistics.md`.

DECISION / NEXT STEP: Resolve D-009. Complete the outstanding TASK 1 quality checks. Revisit D-004's wording if the depth path is chosen.

---

## E-002 — Is the lap record structurally sound across the 21-race corpus?

EXPERIMENT ID: E-002
DATE: 2026-09-24
STATUS: complete — null result (no defects found)
QUESTION: Does the corpus contain duplicated lap rows, non-monotonic elapsed race time within a car, or breaks in the lap-number sequence? These three properties are assumed by race-order reconstruction, gap calculation and stint detection, none of which has been written yet.
HYPOTHESIS: Some defects expected, concentrated around retirements, red flags and cars rejoining from the garage. A lap-number gap in particular seemed likely wherever the timing system missed a crossing. Being wrong would mean either a genuinely clean source or checks that cannot fire.
DATASET: `data/raw/wec/*.CSV`, 21 files, seasons 2024–2026, loaded via `load_corpus`. Commit f228e27 plus the working-tree changes described below. Hashes in `data/raw/wec/_manifest.json`.
POPULATION: All 179,259 lap rows. 21 races, 8 circuits, 833 car-races. No exclusions — the checks run on the raw record, before any notion of a usable lap exists.
METHOD: Three deterministic checks in `src/endurance_strategy/validation/quality.py`. Duplicates via `duplicated(subset=["event_key","NUMBER","LAP_NUMBER"], keep=False)`. Elapsed and lap-number monotonicity via `sort_values` then `groupby(["event_key","NUMBER"]).diff()`. No randomness, no seeds.
FEATURES: `event_key` RECONSTRUCTED (from the file path). `NUMBER`, `LAP_NUMBER`, `ELAPSED` OBSERVED. `ELAPSED_S` RECONSTRUCTED (deterministic parse of `ELAPSED`).
ASSUMPTIONS: That the grouping key is right — that a car is identified by event plus `NUMBER`, and that a car's lap sequence is continuous across driver changes. Both are tested on the synthetic fixture, not established from documentation.
VALIDATION DESIGN: Not a generalisation claim, so no holdout applies. The validity question here is whether the checks can fail at all. Addressed by mutation testing: five deliberate defects introduced into the implementation, each confirmed to break the suite (6, 1, 2, 2 and 1 test failures respectively). Without that step a zero count is uninterpretable.

RESULT:

| Check | Violating rows |
|---|---:|
| Duplicate laps | 0 |
| Elapsed-time regressions | 0 |
| Lap-number breaks | 0 |

Out of 179,259 rows across 21 races.

UNCERTAINTY: None applicable — these are exhaustive deterministic counts over the full corpus, not estimates. The residual risk is not statistical but logical: that the checks encode the wrong definition of a defect. The 16 tests in `tests/test_quality.py` constrain that risk; they do not eliminate it.

INTERPRETATION:

A clean null result. The lap record is structurally sound on all three properties, which was not the expected outcome and is worth stating plainly rather than passing over.

This answers an open question carried since E-001: **`ELAPSED` is monotonic within a car**, across 21 races rather than the one race originally asked about.

What it does **not** establish:

- **Nothing about lap-time values.** A lap can be structurally perfect and semantically wrong. Implausible times, mis-parsed durations and the in-lap/out-lap question are all untouched by these checks.
- **Nothing about completeness.** A gap-free lap sequence does not mean every lap the car ran was recorded — only that what was recorded is internally consistent. If the source dropped a lap and renumbered, this is invisible to the check by construction.
- **Nothing about the pit data.** The 1,902 vs 1,896 `CROSSING_FINISH_LINE_IN_PIT` / `PIT_TIME` discrepancy from E-001 is unaffected and still open.

The practical consequence is that race-order reconstruction can be built directly on `ELAPSED_S` without a repair step, and stint detection can count laps within a stint without handling gaps. Both of those would otherwise have needed defensive logic written against defects that, it turns out, are not there.

One incidental finding, logged because it was silent: the loader was retaining an empty trailing column (`Unnamed: 29`) in every race loaded. The trailing-semicolon guard tested for a column named `""`, but pandas names it `Unnamed: 29`. Harmless so far, fixed at `src/endurance_strategy/io/load.py`, now pinned by a test.

DECISION / NEXT STEP: Proceed to the remaining TASK 1 items — the `PIT_TIME` discrepancy and a "usable clean lap" definition — then Layer 1 proper. These three checks become part of the data-contract suite run on every ingest.
