# PROJECT_STATE

**Operational state of the project. Read this at the start of every substantive session.**
Keep it short. Update it at the end of every substantial milestone.

Last updated: 2026-09-22 (source access verified; schema audited)

---

## Current phase

**Layer 0 complete; Layer 1 partially begun.** Repository, working agreement and provenance controls exist. Source access is verified and one race's files are on disk with their schema audited. No pipeline, no models, no simulator.

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

---

## In progress

**TASK 1 — race file audit.** Substantially done for 2025 Le Mans; see Known facts.

Still outstanding within TASK 1:

- duplicate-row detection
- `ELAPSED` monotonicity check within each car
- lap-number sequence integrity check
- a definition of "usable clean lap", and the count under it
- a synthetic fixture in `tests/fixtures/` matching the verified schema
- resolving the 1,902 vs 1,896 pit-crossing / `PIT_TIME` discrepancy

---

## Next task

**Resolve D-009 (depth vs breadth), then finish the TASK 1 audit items above.**

D-009 comes first because it determines whether the ingestion pipeline targets one
circuit at high resolution or many events at 3-sector resolution — and that changes
what the parser, the schema contract and the Layer 2 traffic design must handle.

Then Layer 1 proper: parse to a standard schema, build raw → interim → processed,
write to Parquet, query through DuckDB, add data-quality checks and parser tests.

The `audit-wec-data` skill covers the remaining audit steps.

---

## Known facts

Facts directly established by evidence.

**Source access (verified 2026-09-22 by direct access):**

- The Al Kamel WEC timing site is **publicly accessible** — no login, no paywall, no access controls. `robots.txt` is present but empty, so no crawl restrictions are declared.
- The archive covers **15 seasons (2011–2026) and 121 events**. Navigation is by `?season=&evvent=` GET parameters; files are direct links.
- Race sessions publish a **race-wide cumulative** lap-by-lap CSV (`23_Analysis_*_Hour 24`), not only hourly files. This answers a previously open question.
- Per-minute **weather data** (air and track temperature, humidity, pressure, wind, rain) is published as a separate CSV for most recent events.
- **15-point intra-lap timing** (`23_AnalysisEnduranceWithSections_*`) exists for Le Mans 2025, Le Mans 2026 and COTA 2026 only. Every other event is 3-sector.

**2025 Le Mans race file (measured, `23_Analysis_Race_Hour 24.CSV`, 20,182 rows, 29 columns):**

| | Cars | Laps | Pit crossings |
|---|---:|---:|---:|
| Hypercar | 21 | 7,710 | 660 |
| LMP2 | 17 | 5,779 | 555 |
| LMGT3 | 24 | 6,693 | 687 |
| **Total** | **62** | **20,182** | **1,902** |

- 186 distinct drivers. No stable driver ID — `DRIVER_NAME` is the only identifier.
- Track status per lap in `FLAG_AT_FL`: GF 19,654 / SF 320 / FCY 159 / FF 49.
- Data completeness is high: 0 missing lap times, 1 lap missing sector times out of 20,182.
- **Cross-check passed:** the 21 / 17 / 24 class split matches the independently published entry list exactly.

**Licensing:** Al Kamel asserts ownership and prohibits **distribution and dissemination**. Local analysis is a separate matter; redistribution through the repo, a dataset host or a deployed app serving source rows is not permitted. `.gitignore` verified to exclude the downloaded files.

**Environment:** Python 3.13.3, Git 2.52.0. `uv` and the DuckDB CLI are not installed.

**Superseded:** the data-volume estimates in `Strategy.md` §8 are replaced for Le Mans 2025 by the measured counts above. The §8 estimate of "roughly 6k LMP2 Le Mans laps" against a measured 5,779 was close; the per-season figures remain unverified.

---

## Open questions

Not yet established. The full list lives in `Strategy.md` §26; these are the ones blocking near-term work.

- **Depth or breadth?** 121 events at 3-sector resolution, or the 3 race sessions with 15-point intra-lap timing? See DECISIONS D-009 — this blocks the shape of Layer 2 and is Kaloyan's call.
- What exactly does `CROSSING_FINISH_LINE_IN_PIT = B` mark — in-lap, out-lap, or both?
- What does `PIT_TIME` measure, and why do 1,902 crossings yield only 1,896 values?
- Is the `23_Analysis_*` schema identical across 2011–2026? Only 2025 Le Mans verified.
- Is `ELAPSED` monotonic within a car across the full race?
- Where are the 15 intermediate timing points physically, and are the codes stable across circuits?
- What is the clock offset between lap `HOUR` (local) and weather `TIME_UTC_STR`?
- Are there separate race-control / flag message files beyond `FLAG_AT_FL`?

---

## Current blockers

- **D-009 is unresolved.** The depth-versus-breadth choice determines what the ingestion pipeline targets, so Layer 1's scope depends on it.

The previous blockers are cleared: source data is obtained (2025 Le Mans race, weather and micro-sector files are in `data/raw/`), and access terms have been checked.

---

## Validation status

| Component | Status |
|---|---|
| Data ingestion | Not built |
| Data-quality checks | Not built |
| Race-order reconstruction | Not built |
| Traffic exposure model | Not built |
| Pace / stint model | Not built |
| Pit-loss model | Not built |
| Simulator | Not built |
| Optimiser | Not built |
| RAG / retrieval | Not built |
| Application | Not built |
| Test suite | Scaffolding only — three smoke tests, no substantive coverage |
| CI | Workflow file exists but has never run; no remote repository yet |

Nothing has been validated, because nothing has been built.

---

## CV status

Which project capabilities are currently defensible. Full ledger: `docs/cv/CV_EVIDENCE.md`.

**Currently defensible on a CV from this project: nothing.**

The project has a repository structure and a documented methodology. That is not yet a CV claim — a structure with no pipeline, no data and no results supports no bullet. The earliest realistic CV-worthy milestone is the completion of Layer 1 (a reproducible, tested ETL pipeline over real timing data with provenance controls).

The WEC project entry on the end-goal CV draft, and the associated target skills, are **TARGET** status. Do not present them as achievements.
