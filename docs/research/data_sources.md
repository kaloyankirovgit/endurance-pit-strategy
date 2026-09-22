# Data sources

An assessment of every candidate data source: what it contains, whether it may be used, and where it sits in the evidence hierarchy.

**Nothing in this document has been verified against a downloaded file.** Every entry is an assessment recorded from the project specification and needs confirmation. Statuses are marked accordingly.

Evidence hierarchy for this project:

| Tier | Meaning |
|---|---|
| **Primary** | Authoritative, official, the basis for reported results |
| **Secondary** | Useful for extension, robustness or cross-checking; never the sole basis for a headline claim |
| **Controlled** | Synthetic or simulator-derived; used for sensitivity experiments, never as measurement of reality |
| **Rejected** | Assessed and excluded, with the reason recorded |

---

## PRIMARY — FIA WEC official timing (Al Kamel Systems)

**URL:** <https://fiawec.alkamelsystems.com/>

**What it provides:** Official timing products for FIA WEC events — analysis files and classifications by race hour. This is the authoritative source for lap and sector timing.

**Licensing — the binding constraint.** Al Kamel Systems S.L. asserts ownership of the timing data and warns against redistribution without permission. Therefore:

- raw timing files are never committed to this repository;
- no file derived from them is committed either;
- files are obtained locally by the user and placed in `data/raw/`;
- the README documents how a third party obtains them independently;
- the current site terms must be checked before building any automated downloader, and the outcome of that check recorded here.

**Provenance to record for every ingested file:** source URL, event, session, access date, filename, file size, SHA-256, whether the file is race-wide or hourly, and whether it is directly hosted by Al Kamel.

**Status: not yet accessed.** Open questions:

- [ ] Does the site expose one race-wide analysis file per event, or only hourly files?
- [ ] Is the CSV schema consistent across 2023–2025?
- [ ] Are official race-control / flag message files published alongside timing?
- [ ] What do the current terms of use say about automated downloading and local caching?

---

## SECONDARY — Kaggle FIA WEC lap data, 2012–2022

**Potential use:** historical extension beyond the modern regulation era, robustness checks, a longer time span for circuit-level effects.

**Assess before any use:**

- [ ] Exact schema — inspect the actual columns rather than the dataset description.
- [ ] Does it contain races only, or practice and qualifying too?
- [ ] Is coverage complete, or a subset of events?
- [ ] Licence and usage terms.
- [ ] Is original provenance maintained, or has the data been transformed by the uploader?
- [ ] Are timing definitions consistent with modern WEC files?

**Caution:** a Kaggle copy does not inherit the legal or semantic status of the original source. A re-upload may be transformed, incomplete or improperly licensed. The 2012–2022 window also spans major regulation changes (LMP1 to Hypercar, GTE to LMGT3), so pooling it with 2025 data requires an explicit argument, not convenience.

**Status: not assessed.**

---

## SECONDARY — IMSA data (`tobi/imsa_data`)

**Potential use:** cross-series transferability test. If traffic and race-state features estimated on WEC generalise to IMSA, that is a meaningfully stronger result than within-series validation alone.

**Explicitly not part of the MVP.** Consider only after Layer 2 produces a validated WEC traffic estimate worth testing for transfer.

**Assess before use:** schema, licence, completeness, and whether class structure and timing conventions are comparable enough for the comparison to mean anything.

**Status: not assessed.**

---

## CONTROLLED — Le Mans Ultimate

**Potential use:** a simulator can expose quantities the real timing data does not — fuel consumption, tyre temperature and wear, detailed telemetry, pit events under controlled conditions.

**The right use is sensitivity experiments, not measurement.** For example: "when fuel mass increases by X and tyre degradation takes shape Y, how far does the optimal pit window move?" This complements real data by probing model structure. It does not establish real-world parameter values.

**Assess before use:**

- [ ] Does the XML / telemetry output contain AI-car laps, or only the player's car? (Assume nothing here.)
- [ ] Can fuel, tyre and pit variables be extracted automatically?
- [ ] Are controlled runs reproducible from a fixed seed?
- [ ] Are the data formats stable enough to build a small experimental dataset on?

**Caution:** no sim-to-real claim from a small sample. Any LMU-derived quantity used in the project is labelled SIMULATED.

**Status: not assessed.**

---

## OPTIONAL — iRacing

**Potential use:** another controlled source with fuel and tyre state.

**Assess only if it adds information WEC data cannot provide**, and only after the primary pipeline works:

- [ ] Does the API expose fuel quantity and consumption?
- [ ] Does it expose tyre condition sufficiently?
- [ ] Authentication and rate limits.
- [ ] Redistribution and bulk-collection terms.

**Caution:** API access complexity is a known distraction risk. It is not on the critical path.

**Status: not assessed.**

---

## Supporting — FIA WEC regulations and official documents

**URL:** <https://www.fiawec.com/en/page/regulations/18>

**Use:** the retrieval corpus for Layer 6, and the source for the structured feasibility rules table (DECISIONS D-006). Covers sporting regulations, technical and BoP documents where relevant, and event bulletins that modify standard rules.

Tracked separately in [`regulations.md`](regulations.md), because these documents are versioned and their revision dates are part of the evidence.

**Status: not yet collected.**

---

## Supporting — 2025 Le Mans entry list

**URLs:**
- <https://www.fiawec.com/en/news/les-engages-des-24h-du-mans-2025/8230>
- <https://www.fiawec.com/en/news/full-entry-list-published-for-93rd-24-hours-of-le-mans/8320>

**Use:** an externally documented grid count for the 2025 24 Hours of Le Mans — 21 Hypercar, 17 LMP2, 24 LMGT3 — usable as a cross-check on the car counts derived from a timing file. A mismatch between entry list and timing file is itself informative (non-starters, withdrawals, retirements).

**Status: recorded from the specification; links not re-verified in this session.**

---

## Sources deliberately not used

- **General web scraping of results aggregators.** Provenance is unclear and timing definitions are inconsistent between sites.
- **LLM-generated or LLM-recalled regulatory or timing facts.** Every regulatory statement must trace to a retrieved document with a page reference. A language model's recall of a rule is not a source.
