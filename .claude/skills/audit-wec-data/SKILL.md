---
name: audit-wec-data
description: Audit a WEC timing file before it is used - provenance, schema, measured counts, quality findings. Use when a new race file, event or season is obtained, or when a source's schema may have changed.
---

# Audit WEC data

Establish what a timing file actually contains before anything is built on it. The output is a set of measured facts that replace assumptions.

**Nothing in this workflow assumes column names.** Map actual source headers to semantic names after inspection, never before.

---

## 1. Provenance

Record, before parsing:

- source URL, event, session
- date accessed, filename, file size
- SHA-256 hash
- whether the file is race-wide or hourly/partial
- whether it is directly hosted by the official source

Write this to `docs/research/data_sources.md`. Confirm the file is in `data/raw/` and excluded by `.gitignore` — check with `git status --ignored` before going further.

## 2. Schema

Report: row count, column count, exact column names as they appear, dtypes after parsing, first and last five rows, missingness per column, unique counts for cars / drivers / classes / teams / manufacturers.

Watch for: multi-row headers, per-car section blocks rather than a flat table, encoding issues, separators that are not commas, and duration formats needing conversion.

## 3. Semantic mapping

For each field the project needs — car, driver, lap number, lap time, sectors 1–3, pit indicator, pit time, elapsed time, clock time, class, team, manufacturer, flag, speeds — record the actual source column, or `ABSENT`.

Do not guess a mapping from a plausible-looking name. Verify against the values: a column named `PIT` could be a boolean, a duration, or a lane time.

Update `docs/DATA_DICTIONARY.md` with what was verified. Anything unresolved stays `UNKNOWN — requires validation`.

## 4. Measured counts

| Class | Cars | Drivers | Raw rows | Laps | Pit-crossing rows | Usable clean laps |
|---|---:|---:|---:|---:|---:|---:|

Plus: total rows, total cars, rows and laps per car, pit events by class, percentage of rows with valid sector data, percentage with valid flag data.

State the criterion used for "usable clean lap" — it is a modelling choice, not an objective fact.

## 5. Replace estimates

Compare measured counts against the planning estimates in `Strategy.md` §8 and record the difference. The discrepancy is useful engineering evidence: it shows the project replaced assumptions with measurement.

Update `Strategy.md` §8 to mark the estimates superseded, and update `PROJECT_STATE.md` known facts.

## 6. Quality findings

- missingness patterns — is it random, or concentrated in particular cars or race phases?
- duplicate rows
- impossible lap times (negative, zero, implausibly fast or slow for the circuit)
- inconsistent class or team labels for the same car
- driver-number or driver-name changes mid-race
- elapsed-time discontinuities or non-monotonicity within a car
- lap-number sequence breaks
- pit-flag anomalies
- the full observed flag vocabulary

## 7. Fixture

Create a small **synthetic** fixture in `tests/fixtures/` matching the verified schema — not an extract of the real file. Small enough to verify by eye. Header comment marking it synthetic.

## 8. Record

- `docs/EXPERIMENT_LOG.md` — an entry with the measured counts and quality findings
- `docs/DATA_DICTIONARY.md` — verified mappings
- `docs/PROJECT_STATE.md` — known facts, open questions, next task
- `docs/DECISIONS.md` — any decision the audit forced

---

## Done when

Provenance recorded; schema documented; semantic mapping verified against values; counts measured; quality findings recorded; estimates replaced; raw file confirmed out of Git; synthetic fixture exists; data dictionary updated.

## Watch for

**Assuming a column means what its name suggests.** The `pit_crossing` and `pit_time` semantics are named open questions — resolve them against the data, not by inference from the name.

**Reporting row count as sample size.** Report races, cars, drivers, stints and pit events too.

**Silently dropping bad rows.** Flag them and record the counts.
