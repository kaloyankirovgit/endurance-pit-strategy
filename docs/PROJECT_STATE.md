# PROJECT_STATE

**Operational state of the project. Read this at the start of every substantive session.**
Keep it short. Update it at the end of every substantial milestone.

Last updated: 2026-09-24 (TASK 1 structural quality checks complete)

---

## Current phase

**Layer 0 complete; Layer 1 partially begun.** Repository, working agreement and provenance controls exist. All 21 corpus races are on disk, a loader reads them, and the three structural quality checks pass across all 179,259 laps with a tested fixture behind them. No interim/processed layer yet, no models, no simulator.

---

## Completed

Verified completed work only.

- Repository structure created at `~/Projects/endurance-pit-strategy-planner` and initialised with Git.
- `Strategy.md` stored in the repository as the detailed project specification.
- `CLAUDE.md` written: working agreement, scientific categories, provenance rules, repository conventions, testing expectations.
- Documentation system created: `PROJECT_STATE.md`, `DECISIONS.md`, `EXPERIMENT_LOG.md`, `DATA_DICTIONARY.md` (stub), `research/` (data sources, literature, regulations), `cv/` (evidence ledger, bullets, skills ledger).
- `.claude/rules/` — six rule files: scientific method, data engineering, statistics, simulation, RAG, testing.
- `.claude/skills/` — five skills: audit-wec-data, statistical-review, validate-simulator, research-literature, cv-update.
- `.claude/agents/` — four specialist agents: data-auditor, statistical-reviewer, simulator-reviewer, code-reviewer.
- `.gitignore` excluding raw/derived data, PDFs, secrets, environments and caches.
- `README.md` with the intended architecture (explicitly labelled as intended, not implemented) and the layer roadmap.
- `pyproject.toml`, an importable `src/endurance_strategy` package, and a smoke test that runs under pytest.
- A minimal GitHub Actions workflow that installs the package and runs the test suite with no proprietary data.
- `endurance_strategy.io.load` — a loader for the 29-column race CSV handling the four source traps (BOM, leading-space headers, two duration formats, car number as string) plus the empty trailing column. Reads one race or the 21-race corpus.
- `endurance_strategy.paths` — absolute filesystem anchors, so a path works from any working directory.
- `endurance_strategy.validation.quality` — three structural checks: duplicate laps, `ELAPSED` regressions within a car, lap-number sequence breaks. Each returns violating rows rather than a boolean.
- `tests/fixtures/synthetic_race.CSV` — synthetic 3-car, 4-lap fixture matching the verified schema, including a driver change and a pit in-lap.
- `tests/test_quality.py` — 16 tests. Each check is proven to fire on a deliberate corruption; mutation testing confirmed five plausible implementation errors each break the suite.

---

## In progress

**TASK 1 — race file audit.** Structural checks now complete across the full corpus (E-002).

Still outstanding within TASK 1:

- a definition of "usable clean lap", and the count under it
- resolving the 1,902 vs 1,896 pit-crossing / `PIT_TIME` discrepancy
- what `CROSSING_FINISH_LINE_IN_PIT = B` actually marks (in-lap, out-lap, or both)
- value-level checks: implausible lap times, missing sectors, `KPH` consistency

---

## Next task

**Scope settled.** D-009: breadth as the spine, micro-sector depth as a traffic sub-study. D-010: primary corpus is **2024–2026, 21 races, 8 circuits, 179,259 laps, 9,813 pit events**, split fit-2024 / validate-2025 / test-2026.

All 28 files (2023–2026) are on disk at `data/raw/wec/` with a manifest. The 2023 races are held as an optional robustness extension, not part of the corpus.

Immediate sequence:

1. **Pit semantics** — settle what `CROSSING_FINISH_LINE_IN_PIT` and `PIT_TIME` measure, and the six-row discrepancy. This blocks stint detection, which blocks everything in Layer 2.
2. **"Usable clean lap"** — an explicit, tested definition with the count under it, and the sensitivity of that count to each exclusion.
3. **Layer 1 proper** — parser and schema contract over the 21-file corpus, raw → interim → processed, Parquet, DuckDB, data-quality tests. Claude writes the parser, contract and test scaffolding.
4. **Kaloyan implements** order reconstruction, gap calculation and stint-boundary detection, per the working agreement in `CLAUDE.md` §3.

**Terminology fix outstanding:** `Strategy.md` says "multi-class" throughout. In 18 of 21 corpus races the data is two-class (Hypercar + LMGT3). Wording in reports and CV bullets must match the data — see D-010.

---

---

## Known facts

Facts directly established by evidence.

**Source access (verified 2026-09-22 by direct access):**

- The Al Kamel WEC timing site is **publicly accessible** — no login, no paywall, no access controls. `robots.txt` is present but empty, so no crawl restrictions are declared.
- The archive covers **15 seasons (2011–2026) and 121 events**. Navigation is by `?season=&evvent=` GET parameters; files are direct links.
- Race sessions publish a **race-wide cumulative** lap-by-lap CSV (`23_Analysis_*_Hour 24`), not only hourly files. This answers a previously open question.
- Per-minute **weather data** (air and track temperature, humidity, pressure, wind, rain) is published as a separate CSV for most recent events.
- **15-point intra-lap timing** (`23_AnalysisEnduranceWithSections_*`) exists for Le Mans 2025, Le Mans 2026 and COTA 2026 only. Every other event is 3-sector.

**Modern-era archive audited (28 races, 2023–2026, all downloaded and parsed):**

| | Races | Circuits | Laps | Pit events |
|---|---:|---:|---:|---:|
| 2023–2026 all | 28 | 11 | 236,738 | 12,775 |
| 2024–2026 (Hypercar/LMGT3) | 21 | 8 | 179,259 | 9,813 |
| Le Mans only (3-class) | 4 | 1 | 70,968 | 6,695 |

- **Schema is identical across all 28 files (29 columns).** One parser covers 2023–2026; no per-season variants. Pre-2023 unverified.
- Track status across the archive: GF 221,287 / SF 12,112 / FCY 2,340 / FF 948 / RF 51 — ample for estimating race-control processes.
- Weather CSVs available for every one of the 28 races.

**Structural integrity of the lap record (measured 2026-09-24, E-002):** across all 21 corpus races and 179,259 laps — **0 duplicate laps, 0 elapsed-time regressions within a car, 0 lap-number sequence breaks**. `ELAPSED` is monotonic within a car, answering a question left open by E-001. The checks are mutation-tested, so the zeros are informative rather than vacuous. This is structural soundness only: it says nothing about whether lap-time *values* are plausible, and nothing about the open pit-data questions.

**Class structure is not uniform — this constrains the project:**

- **2024–2026 championship rounds are two-class** (Hypercar + LMGT3). LMP2 left the championship after 2023 and now runs only at Le Mans.
- **2023's third class is LMGTE Am, not LMGT3** — different cars and performance envelope, so pooling 2023 with later seasons requires an explicit argument.
- The structurally-consistent three-class subset is **Le Mans 2024–2026: three races at one circuit**.

Outside Le Mans this is a *two-class* traffic problem. Still a large closing-speed differential and still the core phenomenon — but `Strategy.md`'s "multi-class" wording and any CV bullet must match what the data actually is.

**2025 Le Mans detail (the file audited first):** 20,182 laps, 62 cars, 186 drivers, 1,902 pit crossings. Class split 21 Hypercar / 17 LMP2 / 24 LMGT3 matches the published entry list exactly.

**Scraping hazard:** the event-selector endpoint intermittently serves a *different* event than requested. Any downloader must verify the returned page's SELECTED season and event match the request. Recorded in `data_sources.md`.

**Licensing:** Al Kamel asserts ownership and prohibits **distribution and dissemination**. Local analysis is a separate matter; redistribution through the repo, a dataset host or a deployed app serving source rows is not permitted. `.gitignore` verified to exclude the downloaded files.

**Environment:** Python 3.13.3, Git 2.52.0. `uv` and the DuckDB CLI are not installed.

**Superseded:** the data-volume estimates in `Strategy.md` §8 are replaced for Le Mans 2025 by the measured counts above. The §8 estimate of "roughly 6k LMP2 Le Mans laps" against a measured 5,779 was close; the per-season figures remain unverified.

---

## Open questions

Not yet established. The full list lives in `Strategy.md` §26; these are the ones blocking near-term work.

- What exactly does `CROSSING_FINISH_LINE_IN_PIT = B` mark — in-lap, out-lap, or both?
- What does `PIT_TIME` measure, and why do 1,902 crossings yield only 1,896 values?
- Is the `23_Analysis_*` schema identical across 2011–2026? Only 2025 Le Mans verified.
- Where are the 15 intermediate timing points physically, and are the codes stable across circuits?
- What is the clock offset between lap `HOUR` (local) and weather `TIME_UTC_STR`?
- Are there separate race-control / flag message files beyond `FLAG_AT_FL`?

---

## Current blockers

None. Source access is verified, one race's files are on disk, and D-009 has settled Layer 1's scope.

---

## Validation status

| Component | Status |
|---|---|
| Data ingestion | Loader built and tested; no interim/processed layer yet |
| Data-quality checks | Three structural checks, 16 tests, mutation-verified. Value-level checks not built |
| Race-order reconstruction | Not built |
| Traffic exposure model | Not built |
| Pace / stint model | Not built |
| Pit-loss model | Not built |
| Simulator | Not built |
| Optimiser | Not built |
| RAG / retrieval | Not built |
| Application | Not built |
| Test suite | 19 tests. Substantive coverage of the loader and the three structural checks; nothing else |
| CI | Workflow file exists but has never run; no remote repository yet |

Nothing has been validated, because nothing has been built.

---

## CV status

Which project capabilities are currently defensible. Full ledger: `docs/cv/CV_EVIDENCE.md`.

**Currently defensible on a CV from this project: nothing.**

The project has a repository structure and a documented methodology. That is not yet a CV claim — a structure with no pipeline, no data and no results supports no bullet. The earliest realistic CV-worthy milestone is the completion of Layer 1 (a reproducible, tested ETL pipeline over real timing data with provenance controls).

The WEC project entry on the end-goal CV draft, and the associated target skills, are **TARGET** status. Do not present them as achievements.
