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

No experiments yet. The project is at Layer 0; no data has been ingested.

The first entry will be **E-001**, arising from TASK 1: the audit of one full 2025 WEC race timing file. That entry is descriptive rather than inferential — its question is "what does the source actually contain?" — but it is logged here because its measured counts replace the planning estimates in `Strategy.md` §8, and the gap between estimate and measurement is itself evidence worth keeping.
