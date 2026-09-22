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
