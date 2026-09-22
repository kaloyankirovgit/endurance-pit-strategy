# data/

**Nothing in this directory is ever committed.** `.gitignore` excludes `data/**`.

FIA WEC timing data is owned by Al Kamel Systems S.L. and may not be
redistributed without permission. That applies to files derived from it too --
Parquet tables, DuckDB databases and aggregates are derivative works.

| Directory | Role | Rules |
|---|---|---|
| `raw/` | Faithful source material (bronze) | Never edited in place. Provenance recorded alongside: source URL, event, session, download timestamp, size, SHA-256. |
| `interim/` | Standardised and validated (silver) | Names normalised, times in seconds, categories normalised, invalid rows **flagged not deleted**, pit and stint boundaries identified. |
| `processed/` | Analytical marts (gold) | Task-specific tables built for a named consumer. |

Data flows one way. Committed synthetic fixtures live in `tests/fixtures/`, not
here -- see `docs/DECISIONS.md` D-003.

To obtain source data, see the data-sources note in `docs/research/data_sources.md`.
