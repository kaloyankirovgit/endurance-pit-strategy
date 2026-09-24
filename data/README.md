# data/

Nothing in here gets committed. The WEC timing data belongs to Al Kamel Systems and can't be redistributed, and that includes anything built from it, like Parquet tables or aggregates.

| Folder | What goes in it |
|---|---|
| `raw/` | Files exactly as downloaded, never edited. Each one's source and hash is recorded alongside it. |
| `interim/` | Cleaned and checked. Bad rows are flagged, not deleted. |
| `processed/` | Tables built for a specific model or figure. |

Data only moves forward through these. The synthetic test data lives in `tests/fixtures/` instead.

To get the source files, see the README.
