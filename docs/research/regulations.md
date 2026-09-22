# Regulations

Tracking of official sporting, technical and race-control documents, and the structured constraints derived from them.

Two hard rules govern this file:

1. **No regulatory fact is recorded from memory.** Every constraint cites a document, a revision and a page. A language model's recollection of a rule is not a source, and neither is a forum post or a news article.
2. **Regulations are versioned data, not constants.** They are season- and event-dependent, and event bulletins modify standard rules mid-season. A constraint without an `effective_from` date and a source document is not usable.

**Nothing has been collected yet.** The document registry is empty.

---

## Why this matters to the project

A pit strategy is only meaningful if it is legal. The feasibility layer (DECISIONS D-006) takes a candidate strategy and returns `(feasible, violations)` before the simulator ever runs, so the optimiser does not waste computation on illegal strategies.

It also gives the LLM layer its strongest role: explaining *which rule* made a strategy infeasible, with a citation, while the simulator handles the arithmetic. That is a genuine use for retrieval, as opposed to a chatbot bolted onto a model.

---

## Document registry

| doc_id | Title | Season | Revision | Effective date | Scope | Source URL | Retrieved | SHA-256 |
|---|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — | — |

Primary source: <https://www.fiawec.com/en/page/regulations/18>

Document types to collect:

- FIA WEC Sporting Regulations (the main source of strategy constraints)
- Technical regulations, where they constrain fuel, tyres or pit procedure
- Balance of Performance documents, where they affect stint length or pace
- Event-specific bulletins and sporting notices that amend the standard rules
- Race-control documents, where they establish procedure under FCY and safety car

Regulation PDFs are **not committed** — `.gitignore` excludes `*.pdf`. They are stored locally with their provenance recorded in this registry, and the registry is what the repository publishes.

---

## Structured rules table — schema

The feasibility layer consumes rows of this shape. The table is populated only from retrieved document text.

| Column | Meaning |
|---|---|
| `rule_id` | Stable identifier for this project |
| `season` | Championship season the rule applies to |
| `event_scope` | `all`, or a specific event where a bulletin amends the standard rule |
| `class` | Hypercar / LMP2 / LMGT3, or `all` |
| `section` | Section number in the source document |
| `page` | Page number, for citation |
| `rule_type` | Category — see below |
| `parameter` | The constrained quantity |
| `value` | The constraint value |
| `unit` | Units of `value` |
| `effective_from` | Date the rule takes effect |
| `effective_to` | Date it ceases to apply, if known |
| `source_document` | `doc_id` from the registry above |

---

## Candidate constraints to encode

**Implement a constraint only once its exact wording has been retrieved from the applicable official document.** The list below is a list of *questions to ask the regulations*, not a list of rules. None of these is asserted to exist in the form described.

| rule_type | Question to put to the regulations | Status |
|---|---|---|
| `driving_time` | Are there minimum or maximum driving-time requirements per driver, per race or per stint? | UNKNOWN — requires retrieval |
| `driver_change` | What crew and procedural requirements apply to a driver change? | UNKNOWN — requires retrieval |
| `pit_procedure` | What constrains activity in the pit box — simultaneous operations, personnel limits, sequencing? | UNKNOWN — requires retrieval |
| `refuelling` | What constrains refuelling — rate, simultaneity with other work, minimum stop duration? | UNKNOWN — requires retrieval |
| `tyres` | Are there restrictions on tyre allocation, sets per race, or changes per stop? | UNKNOWN — requires retrieval |
| `mandatory_stops` | Are there mandatory stops or minimum stop counts for any class or event? | UNKNOWN — requires retrieval |
| `class_specific` | Which sporting constraints differ by class? | UNKNOWN — requires retrieval |
| `fcy_procedure` | What is permitted during FCY and safety-car periods, particularly regarding pit entry? | UNKNOWN — requires retrieval |
| `event_bulletin` | Which event bulletins amended the standard rules for the target event? | UNKNOWN — requires retrieval |

The FCY and pit-entry question matters more than it appears: the strategic value of pitting under a caution depends entirely on what the regulations permit at that moment, and getting it wrong would systematically bias the optimiser.

---

## Retrieval corpus notes

For Layer 6, each indexed chunk carries: `document_id`, `document_title`, `season`, `document_revision`, `effective_date`, `section`, `page`, `source_url`, `text`.

Two properties are required of the retrieval layer:

- **Every regulatory claim in a generated answer traces to a retrieved chunk.** No generic citation of "the sporting regulations" without an identifiable source.
- **The system refuses rather than guesses** when the retrieved documents do not support the claim being asked about.

Retrieval accuracy is evaluated separately from generation quality. See `.claude/rules/rag.md`.
