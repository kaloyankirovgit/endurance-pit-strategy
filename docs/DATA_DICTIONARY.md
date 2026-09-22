# DATA_DICTIONARY

**Status: stub. No source file has been inspected.**

Nothing in this document is a claim about what FIA WEC timing files contain. The semantic field names below are the *target* vocabulary the pipeline will use internally. The source columns that populate them are unknown until the TASK 1 audit.

Rules for this file:

- Never invent a field definition. If the meaning is not established from the file or from documentation, write `UNKNOWN — requires validation`.
- Do not fill in a "Likely source field" from memory or from another series' format. Fill it in from the actual header row of an inspected file.
- Every field carries a provenance category: **OBSERVED** (present in the source), **RECONSTRUCTED** (computed deterministically), **INFERRED** (estimated statistically), **ASSUMED** (chosen because the data do not identify it).
- When a field is populated, record the file it was verified against.

---

## Source files inspected

| File | Event | Session | Source URL | Accessed | SHA-256 | Rows | Cols |
|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — |

None yet.

---

## Identity and metadata

| Semantic field | Source column | Type | Category | Meaning | Required | Status |
|---|---|---|---|---|---|---|
| `event_id` | UNKNOWN | string | RECONSTRUCTED | Unique event identifier | Yes | Likely derived from file metadata rather than a column — requires validation |
| `session_id` | UNKNOWN | string | RECONSTRUCTED | Session identifier; must distinguish race from practice and qualifying | Yes | UNKNOWN — requires validation |
| `car_number` | UNKNOWN | string | OBSERVED | Car number. Treat as categorical, never arithmetic | Yes | UNKNOWN — requires validation |
| `driver_id` | UNKNOWN | string | OBSERVED | Stable driver identifier | Ideally | UNKNOWN — whether a stable ID exists, or only a name, requires validation |
| `driver_name` | UNKNOWN | string | OBSERVED | Human-readable driver name | Optional | UNKNOWN — requires validation |
| `class` | UNKNOWN | category | OBSERVED | Hypercar / LMP2 / LMGT3. Label vocabulary must be normalised | Yes | UNKNOWN — actual label spellings require validation |
| `team` | UNKNOWN | string | OBSERVED | Entered team | Ideally | UNKNOWN — requires validation |
| `manufacturer` | UNKNOWN | string | OBSERVED | Car manufacturer; useful as a hierarchical grouping level | Ideally | UNKNOWN — requires validation |

---

## Timing

| Semantic field | Source column | Type | Category | Meaning | Required | Status |
|---|---|---|---|---|---|---|
| `lap_number` | UNKNOWN | int | OBSERVED | Lap index. Numbering convention (0- or 1-based, reset behaviour) unverified | Yes | UNKNOWN — requires validation |
| `lap_time` | UNKNOWN | float (s) | OBSERVED | Lap duration. Source format (e.g. `m:ss.SSS`) and conversion unverified | Yes | UNKNOWN — requires validation |
| `sector_1` | UNKNOWN | float (s) | OBSERVED | Sector 1 duration | Ideally | UNKNOWN — including whether populated for all laps |
| `sector_2` | UNKNOWN | float (s) | OBSERVED | Sector 2 duration | Ideally | UNKNOWN — including whether populated for all laps |
| `sector_3` | UNKNOWN | float (s) | OBSERVED | Sector 3 duration | Ideally | UNKNOWN — including whether populated for all laps |
| `elapsed_time` | UNKNOWN | float (s) | OBSERVED | Elapsed race time at the observation. Key race-state variable | Yes | UNKNOWN — monotonicity and race-relative origin require validation |
| `clock_time` | UNKNOWN | timestamp | OBSERVED | Absolute session clock; useful for aligning race-control events | Optional | UNKNOWN — requires validation |
| `average_speed` | UNKNOWN | float | OBSERVED | Average lap speed | Optional | UNKNOWN — requires validation |
| `top_speed` | UNKNOWN | float | OBSERVED | Recorded top speed. Measurement point undefined | Optional | UNKNOWN — requires validation |

---

## Pit and flag

| Semantic field | Source column | Type | Category | Meaning | Required | Status |
|---|---|---|---|---|---|---|
| `pit_crossing` | UNKNOWN | bool/category | OBSERVED | Whether the lap is associated with a pit-lane crossing | Ideally | **UNKNOWN — exact semantics are a named open question.** Does it mark the in-lap, the out-lap, or both? |
| `pit_time` | UNKNOWN | float (s) | OBSERVED | A source-defined pit timing quantity | Ideally | **UNKNOWN — must establish whether this is stationary time, pit-lane transit time, or an aggregate.** Do not model until settled |
| `flag` | UNKNOWN | category | OBSERVED | Track or finish-line status | Ideally | UNKNOWN — the observed flag vocabulary must be enumerated from the file, not assumed |

---

## Derived fields

Produced by this project, not present in the source. These definitions are provisional and will be fixed once the source schema is known.

| Semantic field | Type | Category | Meaning | Status |
|---|---|---|---|---|
| `stint_id` | int | RECONSTRUCTED | Stint identifier, incrementing at pit and driver-change boundaries | Definition depends on unresolved `pit_crossing` semantics |
| `stint_lap` | int | RECONSTRUCTED | Lap index within the stint. Essential for degradation modelling | Depends on `stint_id` |
| `is_in_lap` | bool | RECONSTRUCTED | Lap ending in a pit entry | Depends on `pit_crossing` semantics |
| `is_out_lap` | bool | RECONSTRUCTED | Lap beginning with a pit exit | Depends on `pit_crossing` semantics |
| `is_duplicate` | bool | RECONSTRUCTED | Flagged duplicate row — flagged, never deleted | Criteria to be defined from observed duplicates |
| `is_invalid_laptime` | bool | RECONSTRUCTED | Lap time outside a plausible range | Thresholds to be set per circuit and class from data |
| `is_flagged` | bool | RECONSTRUCTED | Lap run under a non-green track status | Depends on flag vocabulary |
| `is_missing_sector` | bool | RECONSTRUCTED | One or more sector times absent | — |
| `is_usable_for_pace_model` | bool | RECONSTRUCTED | Passes the clean-pace filter | Filter definition is a modelling decision; record it in DECISIONS.md |
| `race_position` | int | RECONSTRUCTED | Order by completed laps, then crossing time within the lap group | Validate against official classifications |
| `gap_ahead` | float (s) | RECONSTRUCTED | Time gap to the car ahead at a timing-line crossing | Only defined at crossings — not continuous track position |
| `is_candidate_traffic` | bool | INFERRED | Candidate multi-class exposure window | **Never describe as an observed overtake.** See DECISIONS D-004 |
| `traffic_exposure` | float | INFERRED | Estimated exposure magnitude | Definition is a core modelling task; Kaloyan implements |
| `lap_residual` | float (s) | INFERRED | Observed minus expected clean pace | Depends on the baseline pace model; the core modelling target |
| `tyre_state` | float | ASSUMED | Modelled tyre condition | Not measured in public timing data. See DECISIONS D-005 |
| `fuel_state` | float | ASSUMED | Modelled fuel load | Not measured in public timing data. See DECISIONS D-005 |

---

## Open semantic questions

Carried from `Strategy.md` §26. Answering these is part of TASK 1.

- [ ] What exactly does the pit-crossing flag mean?
- [ ] What exactly does the `pit time` field measure?
- [ ] Are in-lap / out-lap flags explicit in the source, or must they be derived?
- [ ] How are driver changes represented?
- [ ] What flag values occur in race files, and how are they encoded?
- [ ] Is elapsed time monotonic and race-relative across the full event?
- [ ] Are sector times present for all laps or only selected ones?
- [ ] Is the schema consistent across 2023–2025 events?
