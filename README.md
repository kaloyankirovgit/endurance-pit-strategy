# Endurance Racing Pit Strategy Planner

A decision-support system for multi-class endurance racing: turn real FIA WEC timing data into a validated race-state dataset, estimate the lap-time cost of multi-class traffic, calibrate a stochastic race simulator, optimise pit-stop timing under uncertainty, and explain the result against the official sporting regulations.

The question the system is built to answer:

> Given a target car, circuit, race duration and estimated race conditions, how should a team time its pit stops and stints once driver pace, stint degradation, pit losses, multi-class traffic and random race-control events are taken into account — and how confident should it be in that answer?

**Status: Layer 0 — project foundation. No data has been ingested and no model exists yet.**
See [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md) for what is actually complete.

---

## Intended system architecture

The diagram below is the **intended** end state. Nothing in it is implemented yet.

```text
                 ENDURANCE RACING
                        │
                        ↓
               REAL WEC DATA
                        │
                        ↓
                   ETL / QA
                        │
                        ↓
              STATISTICAL MODELS
                 ↙           ↘
          traffic            pace
                 ↘           ↙
                   SIMULATOR
                       │
                       ↓
                  OPTIMISER
                       │
                       ↓
                 STRATEGY RESULT
                       │
             ┌─────────┴─────────┐
             ↓                   ↓
      RAG / REGULATIONS      LLM AGENT
             │                   │
             └─────────┬─────────┘
                       ↓
              EXPLAINABLE OUTPUT
```

The LLM layer sits **around** the numerical core, not inside it. The strategy recommendation is computed by the simulator and optimiser; the language model retrieves regulations, calls the simulator as a tool, cites its sources and explains the assumptions. It does not compute the recommendation.

---

## Roadmap

Derived from the layer plan in [`Strategy.md`](Strategy.md). Each layer has a definition of done; nothing is marked complete without reproducible evidence.

| Layer | Scope | Status |
|---|---|---|
| **0 — Foundation** | Repository, working agreement, documentation system, provenance controls, test scaffolding | In progress |
| **1 — Data pipeline / ETL** | Obtain one full 2025 WEC race file, audit it, record provenance, build raw → interim → processed pipeline in Parquet/DuckDB with data-quality checks | Not started |
| **2 — Race order and traffic exposure** | Reconstruct on-track order and gaps, identify candidate multi-class exposure windows, model traffic-associated lap/sector time loss with uncertainty and race-level holdout | Not started |
| **3 — Pace, stint and pit models** | Driver / car / circuit pace decomposition, stint-age effects, pit-loss distributions, honest treatment of fuel–tyre confounding | Not started |
| **4 — Stochastic simulator** | Deterministic lap-discrete core, then lap-time noise, stint effects, pit losses, traffic, FCY / safety-car processes; validated against historical race distributions | Not started |
| **5 — Optimisation** | Feasibility / regulation filter, exhaustive pit-window search, strategy comparison with uncertainty and sensitivity analysis | Not started |
| **6 — RAG / LLM / tool calling** | Versioned WEC regulation corpus, retrieval with citations, simulator exposed as a tool, refusal when documents do not support a claim | Not started |
| **7 — Delivery** | Streamlit application, Docker, CI, public documentation | Not started |

Reinforcement learning, cloud deployment, cross-series (IMSA) validation and Le Mans Ultimate sensitivity experiments are explicit **stretch goals**, not part of the core plan.

---

## What this project deliberately does not claim

These constraints are design decisions, documented up front rather than discovered late:

- **It does not detect individual overtakes.** The primary source is lap and sector timing, not continuous positional data. The modelling target is *inferred multi-class traffic exposure* and the lap/sector time loss associated with it.
- **It does not separately measure fuel and tyre effects** unless a data source is found that identifies them. Both act through stint age, and the default model is an aggregate stint-age effect with fuel and tyre treated as labelled model parameters.
- **It does not treat a team's real pit strategy as ground truth.** Real teams act on telemetry and judgement the public data do not contain. Actual pit laps are descriptive context, not a target to match.
- **It does not treat lap count as sample size.** Laps are clustered within stints, cars, drivers, races and circuits; sample size is reported in races, circuits, cars, stints and pit events as well as laps.

---

## Repository layout

```text
CLAUDE.md                  Standing instructions for Claude Code sessions
Strategy.md                Full project specification, methodology and layer plan
docs/
  PROJECT_STATE.md         Current phase, completed work, next task — read this first
  DECISIONS.md             Architectural and scientific decision record
  EXPERIMENT_LOG.md        Experiments, hypotheses, results, interpretation
  DATA_DICTIONARY.md       Field semantics (stub until the first race file is audited)
  research/                Data sources, literature, regulations
  cv/                      Evidence ledger for CV claims
data/                      raw / interim / processed — contents never committed
src/endurance_strategy/    All production logic
tests/                     Unit, invariant and data-quality tests + synthetic fixtures
notebooks/                 exploration / modelling / validation — narrative only
reports/                   Generated figures and outputs
.claude/                   Project rules, skills and specialist review agents
```

---

## Data sources and licensing

The primary source is FIA WEC timing data published through Al Kamel Systems (<https://fiawec.alkamelsystems.com/>). **Al Kamel Systems S.L. asserts ownership of this data and does not permit redistribution without permission.**

Consequently:

- **No raw timing data, and no data derived from it, is committed to this repository.** `.gitignore` enforces this.
- Source files are obtained locally by the user and placed in `data/raw/`. The pipeline records source URL, event, session, download timestamp, file size and SHA-256 for every ingested file.
- Only small **synthetic** fixtures — generated by this project, resembling the schema but containing no real timing data — are committed, under `tests/fixtures/`.
- Reproduction instructions will be published here once the ingestion path is established, so a third party can obtain the data themselves and re-run the pipeline.

Secondary sources under consideration (Kaggle WEC lap data, IMSA, Le Mans Ultimate, iRacing) are assessed for schema, provenance and licence in [`docs/research/data_sources.md`](docs/research/data_sources.md) before any use.

This is an independent research and portfolio project. It is not affiliated with, endorsed by, or connected to the FIA, the ACO, the FIA World Endurance Championship or Al Kamel Systems.

---

## Reproducing the analysis

Not yet applicable — there is no pipeline to run. Setup, data-acquisition and execution instructions will be added as Layer 1 is built, and the intent is that one documented command takes locally supplied source files through to validated analytical tables.

---

## Methodology and evidence

Two conventions govern how results are reported in this repository:

1. **Every quantity is labelled** OBSERVED, RECONSTRUCTED, INFERRED, ASSUMED or SIMULATED, and categories are never silently converted into one another.
2. **Generalisation is assessed at race level**, not by randomly splitting lap rows, and results are reported with uncertainty and sensitivity analysis rather than as point estimates.

Decisions are recorded in [`docs/DECISIONS.md`](docs/DECISIONS.md); experiments, including those that fail, in [`docs/EXPERIMENT_LOG.md`](docs/EXPERIMENT_LOG.md). A result that shows an effect is not identifiable from the available data is a legitimate and reportable outcome.

---

## Licence

Code: to be decided before the repository is made public (see `docs/DECISIONS.md`). Source timing data and official regulation documents are **not** covered by this repository's licence and are not redistributed here.
