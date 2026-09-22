# Data sources

An assessment of every candidate data source: what it contains, whether it may be used, and where it sits in the evidence hierarchy.

**The primary source has been accessed and measured (2026-09-22); every secondary source below is still an unverified assessment.** Statuses are marked per section.

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

**Access verified 2026-09-22.** Publicly accessible: no login, no paywall, no access
controls. `robots.txt` returns HTTP 200 and is empty (zero bytes), so no crawl
restrictions are declared. Navigation is server-rendered PHP driven by two GET
parameters:

```
https://fiawec.alkamelsystems.com/?season={NN_YYYY}&evvent={NN_EVENT NAME}
```

Each event page lists direct file links of the form:

```
Results/{NN_season}/{NN_EVENT}/{NNN_SERIES}/{YYYYMMDDHHMM_Session}/{NN_Hour NN}/{NN_DocType_Session_Hour NN}.CSV
```

### Archive scale (verified by enumerating all season pages)

| | |
|---|---|
| Seasons | 15 (2011 – 2026) |
| Events | 121 total |
| Per event | Test day, FP1–4, qualifying, hyperpole, warm-up, race — each with its own document set |
| Race session (2025 Le Mans) | 91 files, including 24 hourly classifications |

### Document types (CSV)

| File | Contents |
|---|---|
| `23_Analysis_*` | **Lap-by-lap timing.** 29 columns. The core dataset. |
| `23_AnalysisEnduranceWithSections_*` | Same, plus **15 intra-lap intermediate timing points**. 59 columns. See availability caveat below. |
| `26_Weather_*` | Per-minute air/track temperature, humidity, pressure, wind speed/direction, rain flag |
| `03_Classification_*` | Per-hour classification snapshots |

PDF-only products (not machine-readable without parsing): lap charts, pit-stop
summaries, leader sequence, best sectors, top speeds, grid.

### Micro-sector availability — important constraint

`AnalysisEnduranceWithSections` is **not** published for every event. Verified
per-event counts of race-session files:

| Season | Events with micro-sector race data |
|---|---|
| 2022, 2023, 2024 | none (Le Mans checked) |
| 2025 | Le Mans only |
| 2026 | Le Mans, Circuit of the Americas |

Every other event publishes only the 3-sector `23_Analysis_*` file. This creates a
real depth-versus-breadth trade-off for the traffic layer — see `docs/DECISIONS.md`.

### Measured content, 2025 Le Mans race (`23_Analysis_Race_Hour 24.CSV`)

Downloaded 2026-09-22. The "Hour 24" file is **race-wide and cumulative**, not a
single hour — it contains every lap of the race.

| Quantity | Measured |
|---|---:|
| Lap rows | 20,182 |
| Cars | 62 |
| Drivers | 186 |
| Pit-lane crossings (`CROSSING_FINISH_LINE_IN_PIT = B`) | 1,902 |
| Rows carrying `PIT_TIME` | 1,896 |
| Hypercar | 21 cars, 7,710 laps, 660 pit crossings |
| LMP2 | 17 cars, 5,779 laps, 555 pit crossings |
| LMGT3 | 24 cars, 6,693 laps, 687 pit crossings |
| Missing sector times | 1 lap (S1, S2); 0 (S3) |
| Missing lap time | 0 |

**Cross-check passed:** the 21 / 17 / 24 class split matches the externally
published 2025 Le Mans entry list exactly. Two independent sources agree, so the
class and car identification in the timing file is trustworthy.

Track status is present per lap in `FLAG_AT_FL`: GF 19,654 / SF 320 / FCY 159 /
FF 49. This is the field the FCY and safety-car processes in Layer 4 will be
estimated from.

### Licensing — unchanged and binding

The site states:

> "The data contained on this page is wholly owned by Al Kamel Systems S.L. Any
> attempt by 3rd parties to distribute and/or disseminate any data contained on
> this page without the previous express consent by Al Kamel Systems S.L. will
> lead to legal action taken by the company."

This restricts **distribution and dissemination**, which is precisely what
`.gitignore` prevents. Local download for personal analysis is a separate matter
from republishing. The constraint on this project is therefore unchanged:

- no raw timing data, and nothing derived from it, in Git;
- no redistribution through the repository, a dataset host, or a deployed app that
  serves the underlying rows;
- the README documents how a third party obtains the files themselves.

If the project is ever made public with a live demo, the demo must serve
model outputs, not source rows.

### Local files held

| File | Bytes | SHA-256 (first 16) |
|---|---:|---|
| `23_Analysis_Race_Hour 24.CSV` | 3,913,706 | `cae1d9af21d44d60` |
| `23_AnalysisEnduranceWithSections_Race_Hour 24.CSV` | 8,458,729 | `8e13f35e06788e7b` |
| `26_Weather_Race_Hour 24.CSV` | 88,829 | `006ac3c5d2de4c7d` |

Event: 2025 24 Heures du Mans. Session: `202506141600_Race`. Accessed 2026-09-22.
Confirmed excluded from Git via `git status --ignored`.

### Full audit of the modern era, 2023–2026 (28 races, all downloaded and parsed)

| Season | Event | Hours | Laps | Cars | Drivers | Pit events | Classes |
|---|---|---:|---:|---:|---:|---:|---|
| 2023 | Sebring | 8 | 7,417 | 36 | 104 | 310 | HC, LMP2, LMGTE Am |
| 2023 | Algarve | 6 | 7,596 | 37 | 110 | 233 | HC, LMP2, LMGTE Am |
| 2023 | Spa | 6 | 4,817 | 37 | 103 | 227 | HC, LMP2, LMGTE Am |
| 2023 | **Le Mans** | 24 | 15,030 | 62 | 177 | 1,396 | HC, LMP2, LMGTE Am, Innovative Car |
| 2023 | Monza | 6 | 6,390 | 36 | 104 | 258 | HC, LMP2, LMGTE Am |
| 2023 | Fuji | 6 | 7,774 | 36 | 108 | 225 | HC, LMP2, LMGTE Am |
| 2023 | Bahrain | 8 | 8,455 | 36 | 107 | 313 | HC, LMP2, LMGTE Am |
| 2024 | Losail | 10 | 11,211 | 37 | 111 | 421 | HC, LMGT3 |
| 2024 | Imola | 6 | 6,825 | 37 | 107 | 302 | HC, LMGT3 |
| 2024 | Spa | 6 | 4,410 | 37 | 98 | 209 | HC, LMGT3 |
| 2024 | **Le Mans** | 24 | 15,593 | 62 | 185 | 1,548 | HC, LMP2, LMGT3 |
| 2024 | São Paulo | 6 | 7,796 | 36 | 104 | 219 | HC, LMGT3 |
| 2024 | COTA | 6 | 5,675 | 36 | 103 | 221 | HC, LMGT3 |
| 2024 | Fuji | 6 | 7,042 | 36 | 106 | 251 | HC, LMGT3 |
| 2024 | Bahrain | 8 | 7,486 | 36 | 105 | 288 | HC, LMGT3 |
| 2025 | Losail | 10 | 9,696 | 36 | 103 | 373 | HC, LMGT3 |
| 2025 | Imola | 6 | 7,044 | 36 | 103 | 244 | HC, LMGT3 |
| 2025 | Spa | 6 | 4,630 | 36 | 96 | 261 | HC, LMGT3 |
| 2025 | **Le Mans** | 24 | 20,182 | 62 | 186 | 1,902 | HC, LMP2, LMGT3 |
| 2025 | São Paulo | 6 | 7,930 | 36 | 100 | 210 | HC, LMGT3 |
| 2025 | COTA | 6 | 3,964 | 36 | 102 | 182 | HC, LMGT3 |
| 2025 | Fuji | 6 | 6,683 | 36 | 102 | 220 | HC, LMGT3 |
| 2025 | Bahrain | 8 | 7,795 | 36 | 105 | 288 | HC, LMGT3 |
| 2026 | Imola | 6 | 6,758 | 35 | 97 | 221 | HC, LMGT3 |
| 2026 | Spa | 6 | 4,831 | 35 | 102 | 207 | HC, LMGT3 |
| 2026 | **Le Mans** | 24 | 20,163 | 62 | 185 | 1,849 | HC, LMP2, LMGT3 |
| 2026 | São Paulo | 6 | 8,015 | 35 | 102 | 188 | HC, LMGT3 |
| 2026 | COTA | 6 | 5,530 | 35 | 103 | 209 | HC, LMGT3 |

Fuji 2026 has not yet run. Support-series races (Porsche Carrera Cup, Lamborghini
Super Trofeo, F1 Academy, Michelin Le Mans Cup, Legends of Le Mans) are present in
the archive but excluded — this project covers the FIA WEC series only.

**Totals:** 28 races, 11 circuits, 236,738 laps, 12,775 pit events.
Track status across the archive: GF 221,287 / SF 12,112 / FCY 2,340 / FF 948 / RF 51.

### Schema consistency — resolved

**All 28 files share an identical 29-column schema.** This was an open question and
is now closed for 2023–2026: one parser handles the whole modern era, with no
per-season variants. Consistency before 2023 remains unverified.

### The class-structure finding — this constrains the project

The archive is **not** uniformly three-class. Counting by class structure:

| Structure | Races | Circuits | Laps | Pit events | Seasons |
|---|---:|---:|---:|---:|---|
| Hypercar + LMGT3 (two classes) | 18 | 8 | 123,321 | 4,514 | 2024–2026 |
| Hypercar + LMP2 + LMGTE Am | 6 | 6 | 42,449 | 1,566 | 2023 only |
| Hypercar + LMP2 + LMGT3 (Le Mans) | 4 | 1 | 70,968 | 6,695 | 2023–2026 |

Two consequences:

1. **LMP2 left the championship after 2023.** From 2024 it runs only at Le Mans.
   Every other 2024–2026 round is a *two-class* race.
2. **2023's third class is LMGTE Am, not LMGT3** — different cars, different
   performance envelope, different BoP. It is not interchangeable with LMGT3, so
   pooling 2023 with later seasons needs an explicit argument, not convenience.

So the genuinely three-class, structurally-consistent subset is **Le Mans 2024,
2025 and 2026 — three races at one circuit**. The project's "multi-class" framing
is, outside Le Mans, a two-class problem. This is not a flaw: Hypercar catching
LMGT3 is still a large closing-speed differential and the core traffic phenomenon.
But the wording in `Strategy.md` and any CV bullet must match what the data is.

### Candidate scope subsets

| Subset | Races | Circuits | Laps | Pit events | FCY laps | SC laps |
|---|---:|---:|---:|---:|---:|---:|
| 2023–2026, all | 28 | 11 | 236,738 | 12,775 | 2,340 | 12,112 |
| 2024–2026 (Hypercar/LMGT3 era) | 21 | 8 | 179,259 | 9,813 | 1,794 | 9,306 |
| Le Mans only | 4 | 1 | 70,968 | 6,695 | 554 | 4,859 |
| Le Mans 2024–26 (LMGT3 era) | 3 | 1 | 55,938 | 5,299 | 393 | 3,587 |

### A scraping hazard worth recording

The event-selector endpoint **intermittently returns a different event than the one
requested** — asking for Imola 2026 sometimes serves the Fuji 2026 page. Trusting
the response blindly would silently attribute one event's laps to another, which no
downstream data-quality check would catch.

Any downloader must verify that the returned page's `SELECTED` season and event
match the request, and that the file path contains the requested event folder,
retrying until they do. This is implemented in the fetch used for the audit above.

### Remaining open questions

- [x] ~~One race-wide file or only hourly?~~ **Race-wide.** The Hour 24 file is cumulative.
- [x] ~~Does the site permit access?~~ **Public, no restrictions declared.**
- [x] ~~Is the schema identical across seasons?~~ **Identical across all 28 races, 2023–2026.** Pre-2023 unverified.
- [ ] What exactly does `PIT_TIME` measure — stationary, lane transit, or aggregate?
- [ ] Are the 15 intermediate points at Le Mans physically located, and are their names stable?
- [ ] Are there separate race-control / flag message files beyond `FLAG_AT_FL`?

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
