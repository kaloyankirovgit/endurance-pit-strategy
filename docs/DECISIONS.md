# DECISIONS

Architectural and scientific decision record.

Record a decision here when it constrains later work, would be expensive to reverse, or affects how a result should be interpreted. Do **not** record trivial coding choices.

Template:

```
## D-NNN — Short title

DECISION ID:
DATE:
QUESTION:
OPTIONS CONSIDERED:
DECISION:
REASON:
EVIDENCE:
CONSEQUENCES:
REVISIT WHEN:
```

Decisions are append-only. If a decision is reversed, write a new entry that supersedes it and add a line to the original pointing forward.

---

## D-001 — Repository location and structure

DECISION ID: D-001
DATE: 2026-09-22
QUESTION: Where should the project live, and what top-level structure should it use?
OPTIONS CONSIDERED:
(a) Keep everything in `~/Downloads` alongside the existing strategy documents;
(b) `~/Projects/endurance-pit-strategy-planner`;
(c) `~/Documents/...` under iCloud sync.
DECISION: (b) — `~/Projects/endurance-pit-strategy-planner`, with the top-level layout specified in the bootstrap brief: `CLAUDE.md`, `Strategy.md`, `.claude/`, `docs/`, `data/`, `src/`, `tests/`, `notebooks/`, `reports/`.
REASON: `~/Downloads` is a volatile folder that gets cleared; iCloud sync can interfere with Git internals. A dedicated directory is the stable home a long-lived portfolio repository needs.
EVIDENCE: User choice during the bootstrap session.
CONSEQUENCES: `Strategy.md` is copied into the repository; the `~/Downloads` copy is now a stale duplicate and should not be edited. The repository is the single source of truth from here.
REVISIT WHEN: Never, unless the repository is relocated or a remote is added.

---

## D-002 — Data layer naming: raw / interim / processed

DECISION ID: D-002
DATE: 2026-09-22
QUESTION: `Strategy.md` §15 describes a bronze / silver / gold medallion architecture; the bootstrap brief specifies `data/raw/`, `data/interim/`, `data/processed/`. Which naming is used?
OPTIONS CONSIDERED:
(a) bronze / silver / gold, matching `Strategy.md` §15 and common data-engineering vocabulary;
(b) raw / interim / processed, matching the bootstrap brief and the widely used cookiecutter-data-science convention;
(c) both, with bronze/silver/gold as DuckDB schema names over raw/interim/processed directories.
DECISION: (b) for directories, with the medallion semantics preserved exactly. The mapping is: `raw` = bronze (faithful source, never edited in place), `interim` = silver (standardised, validated, invalid rows flagged not deleted), `processed` = gold (task-specific analytical marts).
REASON: One vocabulary avoids ambiguity about where a file belongs. The semantics of the medallion design — faithful source preservation, validation as a distinct stage, marts built for a task — are what matter, and they are retained in full. The directory names follow the brief.
EVIDENCE: Bootstrap brief §5; `Strategy.md` §15.
CONSEQUENCES: `Strategy.md` §15 and §12 should be amended to use the same names, or to state this mapping explicitly, so the two documents do not diverge. DuckDB schema names may still use `bronze`/`silver`/`gold` if that improves SQL readability — decided at Layer 1.
REVISIT WHEN: Layer 1, when the first DuckDB database is created and schema naming is settled.

---

## D-003 — Committed test fixtures live in `tests/fixtures/`

DECISION ID: D-003
DATE: 2026-09-22
QUESTION: `Strategy.md` §12 lists both `data/fixtures/` and `tests/fixtures/`. Where do committed synthetic fixtures live?
OPTIONS CONSIDERED:
(a) `data/fixtures/`, grouping all data together;
(b) `tests/fixtures/`, grouping fixtures with the tests that consume them;
(c) both, split by purpose.
DECISION: (b) — a single location, `tests/fixtures/`.
REASON: `data/**` is ignored wholesale by `.gitignore` to make committing real timing data difficult. Putting committed fixtures inside `data/` would require an exception in exactly the rule that protects the licensing constraint. Keeping fixtures under `tests/` means the data directory has one unambiguous rule: nothing in it is ever committed.
EVIDENCE: Licensing constraint in `Strategy.md` §6.1.
CONSEQUENCES: `Strategy.md` §12 should drop `data/fixtures/`. Every fixture must be synthetic and labelled as such in a header comment or accompanying README — a real timing extract must never be introduced under a `tests/` path to evade the data rules.
REVISIT WHEN: If a fixture is needed that is too large for Git, in which case a generator script is committed instead of the data.

---

## D-004 — Traffic is modelled as inferred exposure, not detected overtakes

DECISION ID: D-004
DATE: 2026-09-22
QUESTION: Should the traffic layer aim to detect individual overtaking events?
OPTIONS CONSIDERED:
(a) Build an overtake detector from lap and sector timing;
(b) Model inferred multi-class traffic *exposure* and the lap/sector time loss associated with it;
(c) Defer the traffic layer until positional data can be sourced.
DECISION: (b). The modelling target is inferred exposure and traffic-associated timing effects, at lap/sector resolution, with an explicit statement that the exact instant and location of each overtake is unobserved.
REASON: The primary source provides timing-line crossings and sector times, not continuous track position. An overtake detector built on that data would be an unfalsifiable claim: there is no ground-truth label to validate it against. Exposure-and-residual is a weaker claim that the data can actually support, and it is the quantity the simulator needs in any case.
EVIDENCE: `Strategy.md` §16 (critical limitation), §17.1, §17.6. Not yet confirmed against a real file — if the audit in TASK 1 reveals positional or marshalling-sector data, this decision is reopened.
CONSEQUENCES: No claim of overtake detection appears in the README, reports or CV. The traffic model reports an effect on lap/sector residuals with uncertainty, and reports honestly if the effect is not identifiable.
REVISIT WHEN: TASK 1 audit, if the source contains positional, marshalling-sector or GPS-derived fields; or if a secondary source provides validated overtake labels.

---

## D-005 — Fuel and tyre effects are not claimed as separately measured

DECISION ID: D-005
DATE: 2026-09-22
QUESTION: How are fuel burn and tyre degradation represented, given that neither is directly measured in public timing data?
OPTIONS CONSIDERED:
(a) Fit separate fuel and tyre terms and report them as estimated effects;
(b) Model an aggregate stint-age effect, with fuel and tyre as labelled model parameters inside a physically motivated parameterisation if needed;
(c) Source fuel/tyre telemetry from a simulator (Le Mans Ultimate) and treat it as ground truth.
DECISION: (b) as the default. Approach (a) is only permissible if a data source that identifies the components is found and documented. (c) may inform sensitivity experiments but is never treated as measurement of real-world behaviour.
REASON: Fuel mass and tyre degradation both act monotonically through stint age and are confounded in timing-only data. Reporting them separately would convert an ASSUMED parameter into an INFERRED measurement — exactly the category error the project's scientific rules forbid.
EVIDENCE: `Strategy.md` §18 (fuel/tyre confounding warning), §6.4.
CONSEQUENCES: The simulator's fuel and tyre parameters are labelled ASSUMED unless externally identified. Any report separates "stint-age effect (inferred from data)" from "fuel/tyre decomposition (model assumption)". Sensitivity analysis over these parameters becomes mandatory rather than optional.
REVISIT WHEN: A source with fuel flow, stint fuel allocation or tyre-set data is found and its provenance validated.

---

## D-006 — Regulation feasibility is a separate layer from the simulator

DECISION ID: D-006
DATE: 2026-09-22
QUESTION: Where do sporting-regulation constraints (driving-time limits, pit procedure, tyre and fuel rules) live?
OPTIONS CONSIDERED:
(a) Embedded as conditionals inside the simulator's state transitions;
(b) A separate feasibility layer consuming a versioned structured rules table, queried before simulation;
(c) Retrieved from regulation PDFs at simulation time by the RAG layer.
DECISION: (b). A feasibility function takes a candidate strategy and returns `(feasible, violations)`; the simulator and optimiser consume its verdict. Rules are stored in a versioned structured table with `season`, `event_scope`, `class`, `section`, `page`, `source_document`, `effective_from`/`effective_to`.
REASON: Three separate benefits. The optimiser never wastes computation on illegal strategies; regulations are season- and event-dependent so they must be versioned data rather than code constants; and the LLM layer can cite the exact rule that made a strategy infeasible, which is the strongest justification for having an LLM in the system at all. (c) is rejected because retrieval at simulation time is slow, non-deterministic and unauditable.
EVIDENCE: `Strategy.md` §20A.
CONSEQUENCES: Regulations must be retrieved and transcribed with page-level provenance before any constraint is encoded. No regulatory fact is hard-coded from memory — every row in the rules table cites a document and page.
REVISIT WHEN: Layer 5/6, if the rules table proves too rigid for event-specific bulletins.

---

## D-007 — Optimisation precedes reinforcement learning

DECISION ID: D-007
DATE: 2026-09-22
QUESTION: What search method should produce the strategy recommendation?
OPTIONS CONSIDERED:
(a) Reinforcement learning from the start, matching current race-strategy literature;
(b) Exhaustive / grid search over feasible pit windows, then dynamic programming and rolling-horizon re-optimisation, with RL as a stretch goal;
(c) Bayesian optimisation as the primary method, reusing the dissertation experience.
DECISION: (b). RL is not attempted until the simulator has passed validation against historical race distributions.
REASON: An RL agent trained on an unvalidated simulator learns the simulator's errors, and its failures are hard to attribute between the policy and the environment. An exhaustive search over a small, feasible pit-window space is transparent, testable, and gives a baseline against which any later method must prove itself. Bayesian optimisation is appropriate for continuous parameters later, but the initial strategy space is low-dimensional and discrete.
EVIDENCE: `Strategy.md` §20.2, §21.2. Carry-over principle from the BSE dissertation: separate parameter optimisation from policy evaluation.
CONSEQUENCES: Layer 5 delivers a searched optimum with uncertainty, not a learned policy. Parameter tuning and final evaluation use different races.
REVISIT WHEN: Layer 4 validation passes and the strategy space proves too large for exhaustive search.

---

## D-008 — The LLM explains; it does not compute

DECISION ID: D-008
DATE: 2026-09-22
QUESTION: What is the language model's responsibility boundary?
OPTIONS CONSIDERED:
(a) An agent that reasons about strategy in natural language;
(b) A retrieval and explanation layer that calls the simulator as a tool and reports its numerical output verbatim;
(c) No LLM layer at all.
DECISION: (b). The LLM may interpret user intent, select relevant regulations, choose simulator inputs from an approved schema, call the simulator, summarise its output and cite sources. It may not alter simulator outputs, invent numbers, or determine pit timing in prose.
REASON: The credibility of the whole project rests on numerical results being traceable to data and code. A model that can produce a strategy number in free text destroys that traceability, and the resulting system would be a chatbot with a racing theme rather than a decision-support system.
EVIDENCE: `Strategy.md` §5 RQ6, §30.6, §32.
CONSEQUENCES: Every numerical value in a generated answer must be traceable to a tool call. Retrieval is evaluated separately from generation. The system must refuse, rather than guess, when the retrieved documents do not support a claim.
REVISIT WHEN: Never for the core boundary. The tool schema itself is revisited whenever the simulator interface changes.

---

# Technology candidates

Classification as of 2026-09-22. This is a starting position, not a commitment. Move an item up a category only when a concrete need has appeared; record the move as a decision entry.

The governing principle: **prefer a small number of well-used technologies over a long list used superficially.** A recruiter reading the repository should see tools that were needed, not tools that were available.

## Required now

| Technology | Why |
|---|---|
| Python 3.11+ | Project language. Local environment is 3.13.3; confirm the dependency landscape supports it at Layer 1. |
| pandas | Initial parsing, exploration and transformation of timing files. |
| NumPy | Numerical foundation. |
| pytest | Tests are a stated expectation from Layer 0. |
| Git | Version control and the provenance record. |

## Probably useful later

| Technology | Trigger for adoption |
|---|---|
| PyArrow / Parquet | As soon as parsed data is written for reuse — Layer 1. Near-certain. |
| DuckDB | When analytical SQL over Parquet becomes clearer than pandas chains, and to demonstrate SQL competence. Layer 1–2. Note: CLI not currently installed; the Python package is sufficient. |
| statsmodels | Hierarchical / mixed-effects traffic and pace models. Layer 2–3. |
| SciPy | Distributions, bootstrap, statistical tests. Layer 2–3. |
| Matplotlib | Publication-style figures from Layer 1 onwards. |
| Pandera | Dataframe-level data contracts once the schema is known — cannot be written before the TASK 1 audit. |
| Streamlit | Layer 7, the first interactive application. |
| Docker | Layer 7, after the local pipeline is reproducible. |
| GitHub Actions | Already scaffolded; becomes real when a remote repository exists. |
| A vector store (FAISS or Chroma) | Layer 6. Start with the simplest retrieval that works — possibly no vector store at all for a corpus this small. |

## Optional

| Technology | Note |
|---|---|
| Polars | Only if data volume makes pandas genuinely slow. Unlikely at WEC data scale. |
| FastAPI | Only if an API abstraction materially improves the architecture — a Streamlit app alone may not justify it. |
| scikit-learn / XGBoost | Only as a comparator to a hierarchical baseline, and only if the baseline is established first. |
| NetworkX | Only if a graph representation solves a real problem the tabular form does not. |
| Ruff / Black | Cheap and useful; adopt when the codebase is large enough to benefit. |
| A licence for the repository | Decide before making the repository public. |

## Avoid unless evidence shows value

| Technology | Why |
|---|---|
| Dagster / Prefect | An orchestration framework over a three-step pipeline is a liability, not a demonstration. Adopt only with a real multi-step, scheduled pipeline. |
| Great Expectations | Pandera covers the need with far less machinery. |
| Reinforcement learning | See D-007. Stretch goal after simulator validation. |
| Deep learning of any kind | No identified problem in this project needs it. |
| Cloud deployment (Azure / AWS) | Only after local reproducibility is established, and only if it adds something a Docker image does not. |
| Kubernetes | No. |
| An agent framework (LangChain, LlamaIndex, etc.) | Direct tool-calling against a defined schema is more auditable and easier to explain in an interview. Revisit only if retrieval complexity genuinely grows. |

---

# Future automation and hooks

Deferred during bootstrap. Candidates, in priority order:

1. **Raw-data commit guard** — `PreToolUse` on Bash matching `git add` / `git commit`, blocking paths under `data/` and oversized files. This is the highest-value hook and should be implemented as soon as real data is on disk; `.gitignore` is the primary defence but a hook catches `git add -f`.
2. **Format and lint on write** — `PostToolUse` on Edit/Write to `*.py`. Blocked on adopting a formatter.
3. **Targeted test run** — `PostToolUse` on Edit/Write to `src/**`, running the affected test module. Blocked on having a meaningful suite.
4. **Data-contract gate on push** — `PreToolUse` on `git push`, refusing if contract tests fail. Blocked on contracts existing.
5. **Stale-state warning** — `Stop` hook warning when `PROJECT_STATE.md` has not been updated alongside substantive changes.

Adopting any of these is itself a decision entry.

---

## D-009 — Depth versus breadth in source coverage (OPEN — decision required)

DECISION ID: D-009
DATE: 2026-09-22
QUESTION: The Al Kamel archive exposes 121 events across 15 seasons at 3-sector resolution, but publishes 15-point intra-lap timing for only three race sessions (Le Mans 2025, Le Mans 2026, COTA 2026). Which does the project build on?
OPTIONS CONSIDERED:
(a) **Breadth** — many events at 3-sector resolution. Maximises races, circuits and pit events, so it maximises the independent units that matter for generalisation. Traffic localisation stays coarse.
(b) **Depth** — the micro-sector races only. ~5× finer localisation of where lap time is lost, which materially improves the chance that traffic exposure is identifiable at all. But only 2–3 races, and the circuits are not representative.
(c) **Both, in sequence** — establish the pipeline and pace models on breadth; use the micro-sector races as a higher-resolution sub-study for the traffic layer specifically.
DECISION: **Not yet made — Kaloyan decides.**
REASON: This is a genuine scientific trade-off, not a technical one. Breadth serves generalisation; depth serves identifiability. D-004 committed to inferred exposure rather than overtake detection *because* 3-sector resolution cannot localise an encounter — the micro-sector data partially reopens that, which is why the choice matters.
EVIDENCE: Availability verified per event on 2026-09-22; see `docs/research/data_sources.md`.
CONSEQUENCES: Under (b) or (c), D-004 should be revisited — 15 segments per lap is not overtake detection, but it is much closer to localising an encounter than 3 sectors. Under (c), the two strands must not be silently pooled: a traffic estimate from Le Mans micro-sectors is not transferable to a sprint circuit without an argument.
REVISIT WHEN: Now. This blocks the shape of Layer 2.
