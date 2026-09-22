# PROJECT_STATE

**Operational state of the project. Read this at the start of every substantive session.**
Keep it short. Update it at the end of every substantial milestone.

Last updated: 2026-09-22

---

## Current phase

**Layer 0 — project foundation.** Bootstrap session complete: repository architecture, working agreement, documentation system and provenance controls exist. No data, no models, no simulator.

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

Nothing. The bootstrap session is complete and the next task has not started.

---

## Next task

**TASK 1 — obtain and audit one full 2025 FIA WEC race timing file.**

This is a separate session. Definition of done:

- one complete 2025 race analysis file obtained locally (preferably the 24 Hours of Le Mans race analysis, otherwise the most complete race file the source exposes);
- provenance recorded: source URL, event, session, access date, filename, size, SHA-256, and whether the file is race-wide or hourly;
- schema documented: row and column counts, exact column names, dtypes, head and tail, missingness per column, unique cars / drivers / classes / teams;
- core column availability established (lap time, sector times, pit indicator, elapsed time, class, flag, and so on) — mapped from actual source names to semantic names, not assumed;
- measured counts per class: cars, drivers, rows, laps, pit-crossing rows, usable clean laps;
- data-quality findings recorded: duplicates, impossible lap times, elapsed-time discontinuities, lap-number anomalies, pit-flag anomalies, observed flag vocabulary;
- planning estimates in `Strategy.md` §8 replaced with measured counts, and the discrepancy recorded;
- `DATA_DICTIONARY.md` populated from what the file actually contains;
- raw file confirmed excluded from Git;
- a small synthetic fixture created in `tests/fixtures/` for parser tests.

Start by reading `Strategy.md` §13 and running the `audit-wec-data` skill.

---

## Known facts

Facts directly established by evidence.

- The project specification (`Strategy.md`) and the bootstrap brief exist and have been read in full.
- Al Kamel Systems S.L. asserts ownership of FIA WEC timing data and warns against redistribution without permission — therefore raw data must stay out of Git. *(Recorded in `Strategy.md` §6.1; re-verify the live site terms before building any automated downloader.)*
- The 2025 Le Mans entry list of 21 Hypercar / 17 LMP2 / 24 LMGT3 is externally documented. *(External documentation, not yet verified against a downloaded timing file.)*
- Local environment: Python 3.13.3 and Git 2.52.0 available; `uv` and the DuckDB CLI are not installed.

Everything else in `Strategy.md` §8 about data volumes — laps per season, pit stops per season, usable-car percentage — is a **planning estimate, not a fact**, and must be replaced by measured counts in TASK 1.

---

## Open questions

Not yet established. The full list lives in `Strategy.md` §26; these are the ones blocking near-term work.

- Does the Al Kamel site expose one race-wide analysis file per event, or only hourly files?
- Is the race-analysis CSV schema consistent across 2023–2025?
- What exactly does the pit-crossing flag mean, and what does the `pit time` field measure — stationary time, pit-lane time, or an aggregate?
- Are sector times populated for all laps or only selected laps?
- Are there official race-control / flag message files that can be paired with timing data?
- Does the site's current terms of use permit automated downloading and local caching?
- Which WEC season and event should be the primary target for Layer 1? (Provisionally 2025 Le Mans, pending file availability.)

---

## Current blockers

- **No source data has been obtained.** Everything downstream of Layer 1 is blocked until one race file is in `data/raw/`.
- The Al Kamel terms of use have not been checked in this session. Do this before writing any automated downloader; manual download is the safe default in the meantime.

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
| Test suite | Scaffolding only — one smoke test, no substantive coverage |
| CI | Workflow file exists but has never run; no remote repository yet |

Nothing has been validated, because nothing has been built.

---

## CV status

Which project capabilities are currently defensible. Full ledger: `docs/cv/CV_EVIDENCE.md`.

**Currently defensible on a CV from this project: nothing.**

The project has a repository structure and a documented methodology. That is not yet a CV claim — a structure with no pipeline, no data and no results supports no bullet. The earliest realistic CV-worthy milestone is the completion of Layer 1 (a reproducible, tested ETL pipeline over real timing data with provenance controls).

The WEC project entry on the end-goal CV draft, and the associated target skills, are **TARGET** status. Do not present them as achievements.
