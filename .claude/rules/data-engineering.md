# Rule: data engineering

How data moves through this project.

---

## Layer separation

| Directory | Role | Rules |
|---|---|---|
| `data/raw/` | Faithful source material (bronze) | Never edited in place. Never "fixed". Preserved exactly as obtained, with provenance metadata alongside. |
| `data/interim/` | Standardised and validated (silver) | Column names normalised, times converted to seconds, categories normalised, invalid rows **flagged not deleted**, pit and stint boundaries identified. |
| `data/processed/` | Analytical marts (gold) | Task-specific tables built for a named consumer — a model, a figure, the simulator. |

Data flows one way. A processed table is never written back into interim, and interim is never written back into raw.

**Nothing under `data/` is ever committed.** See the licensing rule below.

---

## Provenance

Every ingested file records:

- source URL
- event and session
- download timestamp
- filename and file size
- SHA-256 hash
- whether the file is race-wide or partial (hourly)
- whether it is directly hosted by the official source
- parser version that read it

Provenance is part of the deliverable, not an afterthought. A result that cannot be traced back to a specific file with a specific hash is not reproducible, and reproducibility is one of the things this project exists to demonstrate.

Bronze records carry their source metadata as columns or in a sidecar manifest, so that a row in a processed table can be traced to the file it came from.

---

## Licensing — the hard constraint

FIA WEC timing data is owned by Al Kamel Systems S.L. and may not be redistributed without permission.

- **No raw timing data in Git.** Not compressed, not sampled, not "just a few rows".
- **No data derived from it in Git** — that includes Parquet files, DuckDB databases and aggregate tables, since these are derivative works.
- `.gitignore` excludes `data/**` wholesale plus tabular and PDF extensions repository-wide. **Do not weaken these patterns.** If a legitimate file is being blocked, the file is in the wrong place.
- Only small **synthetic** fixtures are committed, under `tests/fixtures/`, each labelled as synthetic in a header.
- The README documents how a third party obtains the source data themselves.
- Check the source's terms before building any automated downloader, and record the outcome in `docs/research/data_sources.md`.

If in doubt, the file stays local.

---

## Data contracts and schemas

Once the real schema is known (not before — a contract written against an assumed schema is worse than none):

- Define an explicit schema for every table crossing a layer boundary: column names, dtypes, nullability, allowed categorical values, value ranges.
- Validate on write, not on read. A bad row should fail where it was produced, not three transformations later.
- Contract violations fail loudly. Do not coerce, silently drop, or fill.
- Schema changes are versioned. A parser that no longer produces the contracted schema is a bug, not a new contract.

Pandera is the preferred tool. Great Expectations is not adopted — see `docs/DECISIONS.md`.

---

## Deterministic transformations

- The same input file produces the same output, byte for byte where practical.
- No dependence on wall-clock time, dictionary iteration order, filesystem ordering, or unseeded randomness.
- Any randomness is explicitly seeded and the seed recorded.
- Transformations are re-runnable from `data/raw/` without manual intervention — no notebook that must be executed in a particular order by hand.
- Target state: one documented command takes locally supplied source files through to validated analytical tables.

---

## Flag, do not delete

Invalid and suspicious rows are marked, never removed:

```
is_duplicate            is_invalid_laptime      is_pit_lap
is_in_lap               is_out_lap              is_flagged
is_missing_sector       is_candidate_traffic    is_usable_for_pace_model
```

Two reasons. First, the exclusion criteria are modelling decisions that will be revisited, and revisiting them is impossible if the rows are gone. Second, the *pattern* of invalid data is itself evidence — a car with systematically missing sector times is telling you something about the source.

Filtering happens at the point of analysis, using the flags, and the filter used is recorded with the result.

---

## Quality checks

Data-quality checks are tests in `tests/`, not one-off notebook cells. At minimum, per ingested file:

- row and column counts against expectation
- missingness per column
- duplicate detection
- impossible values (negative or zero durations, lap times outside a plausible band)
- monotonicity where expected (elapsed time within a car)
- lap-number sequence integrity
- referential consistency (every lap's car appears in the entry list)
- categorical vocabulary — unexpected class, flag or team labels
- distributional drift between events, once more than one is ingested

A quality check that has never failed on real data has not been tested. Verify each one fires on a deliberately corrupted fixture.

---

## Storage format

- Parquet for analytical data products: columnar, typed, compressed, and it preserves dtypes across sessions in a way CSV does not.
- DuckDB for analytical SQL over Parquet, particularly where window functions over lap sequences express the logic more clearly than pandas chains.
- Keep raw files in their source format. Converting raw to Parquet is a bronze-to-silver step, not an ingestion step.

---

## Notebooks versus the package

Notebooks are for narrative exploration and visualisation. Production logic lives in `src/endurance_strategy/`.

The moment a piece of notebook logic is used twice, or feeds a result that will be reported, it moves into the package and the notebook imports it. A notebook that defines the transformation used to produce a headline number is not reproducible infrastructure.
