# DATA_DICTIONARY

**Schema verified against one file: 2025 Le Mans race, `23_Analysis_Race_Hour 24.CSV`, accessed 2026-09-22.**
Consistency across other events and seasons is **not** verified.

Rules for this file:

- Never invent a field definition. If the meaning is not established from the file or from documentation, write `UNKNOWN — requires validation`.
- A verified *source column name* is not a verified *meaning*. Several columns below have confirmed names and unconfirmed semantics.
- Every field carries a provenance category: **OBSERVED**, **RECONSTRUCTED**, **INFERRED**, **ASSUMED**.

---

## Source files inspected

| File | Event | Session | Accessed | SHA-256 | Rows | Cols |
|---|---|---|---|---|---:|---:|
| `23_Analysis_Race_Hour 24.CSV` | 2025 Le Mans | `202506141600_Race` | 2026-09-22 | `cae1d9af…` | 20,182 | 29 |
| `23_AnalysisEnduranceWithSections_Race_Hour 24.CSV` | 2025 Le Mans | `202506141600_Race` | 2026-09-22 | `8e13f35e…` | 20,182 | 59 |
| `26_Weather_Race_Hour 24.CSV` | 2025 Le Mans | `202506141600_Race` | 2026-09-22 | `006ac3c5…` | — | 9 |

**Format notes.** Semicolon-delimited, UTF-8 with BOM. The first 15 header names
carry a **leading space** (`" DRIVER_NUMBER"`); the remainder do not. Strip keys on
read or every lookup in that block silently returns nothing. Durations appear in
mixed formats: `3:54.555` for laps, `0:01:15.964` for `PIT_TIME`, bare seconds in
the `*_SECONDS` columns.

---

## Identity and metadata

Source column names below are **verified** against the 2025 Le Mans race file.

| Semantic field | Source column | Category | Meaning | Status |
|---|---|---|---|---|
| `event_id` | *(none)* | RECONSTRUCTED | Event identifier | Not a column — must be derived from the file path / download metadata |
| `session_id` | *(none)* | RECONSTRUCTED | Session identifier | Not a column — derive from path, e.g. `202506141600_Race` |
| `car_number` | `NUMBER` | OBSERVED | Car number. **Categorical** — values include `007`, so leading zeros are significant and it must never be read as an integer | Verified |
| `driver_number` | `DRIVER_NUMBER` | OBSERVED | Which driver in the crew (1, 2, 3…) — the key to driver changes | Verified name; numbering convention unconfirmed |
| `driver_name` | `DRIVER_NAME` | OBSERVED | e.g. `Harry TINCKNELL`. 186 distinct values | Verified. No stable driver ID exists — name is the only identifier, so normalisation is required |
| `class` | `CLASS` | OBSERVED | `HYPERCAR`, `LMP2`, `LMGT3` — exactly three values, no spelling variants in this file | Verified |
| `group` | `GROUP` | OBSERVED | Empty throughout this file | Verified empty — purpose unknown |
| `team` | `TEAM` | OBSERVED | e.g. `Aston Martin Thor Team` | Verified |
| `manufacturer` | `MANUFACTURER` | OBSERVED | e.g. `Aston Martin` | Verified |

---

## Timing

| Semantic field | Source column | Category | Meaning | Status |
|---|---|---|---|---|
| `lap_number` | `LAP_NUMBER` | OBSERVED | Lap index, appears 1-based | Verified name; reset behaviour unconfirmed |
| `lap_time` | `LAP_TIME` | OBSERVED | Format `m:ss.SSS`, e.g. `3:54.555`. **0 missing** in 20,182 rows | Verified |
| `sector_1..3` | `S1`, `S2`, `S3` | OBSERVED | Format `ss.SSS` or `m:ss.SSS`. 1 lap missing S1 and S2; 0 missing S3 | Verified — effectively complete |
| `sector_1..3_seconds` | `S1_SECONDS`, `S2_SECONDS`, `S3_SECONDS` | OBSERVED | **The same sectors already converted to decimal seconds.** Use these; do not re-parse the formatted columns | Verified |
| `sector_*_large` | `S1_LARGE`, `S2_LARGE`, `S3_LARGE` | OBSERVED | Sector times in a wider format (`0:51.908`) | Verified name; the difference from `S1` is not established |
| `elapsed_time` | `ELAPSED` | OBSERVED | Cumulative race time at the crossing, `h:mm:ss.SSS` | Verified name; monotonicity **not yet checked** |
| `clock_time` | `HOUR` | OBSERVED | Wall-clock time of day at the crossing, e.g. `16:03:54.555`. Note the column is named `HOUR` but holds a full timestamp | Verified |
| `average_speed` | `KPH` | OBSERVED | Average lap speed in km/h | Verified |
| `top_speed` | `TOP_SPEED` | OBSERVED | km/h. 35 rows missing | Verified name; measurement point undefined |
| `lap_improvement` | `LAP_IMPROVEMENT` | OBSERVED | Almost entirely `0`; 61 rows `2`, 1 row `3` | Verified values; **meaning unknown** — likely a personal/overall-best marker |

---

## Pit and flag

| Semantic field | Source column | Category | Meaning | Status |
|---|---|---|---|---|
| `pit_crossing` | `CROSSING_FINISH_LINE_IN_PIT` | OBSERVED | Blank, or `B`. 1,902 rows carry `B` | **Name and vocabulary verified; semantics still open.** The column name says the car crossed the finish line *in the pit lane*, which points to the out-lap rather than the in-lap — but this is inference, not established |
| `pit_time` | `PIT_TIME` | OBSERVED | Format `h:mm:ss.SSS`, e.g. `0:01:15.964`. Present on 1,896 rows | **Verified present; what it measures is still open** — stationary time, pit-lane transit, or an aggregate. Typical values near 75 s suggest more than stationary time alone. Do not model until settled |
| `flag` | `FLAG_AT_FL` | OBSERVED | Track status at the finish line for that lap. Full observed vocabulary: `GF` 19,654 / `SF` 320 / `FCY` 159 / `FF` 49 | Verified. `GF` green, `FCY` full-course yellow, `SF`/`FF` presumed safety-car and finish flags — **the expansions are inference, not confirmed** |

The 1,902 / 1,896 discrepancy between pit crossings and `PIT_TIME` values is unexplained and worth resolving — six crossings carry no pit time.

---

## Intra-lap intermediate points — `AnalysisEnduranceWithSections` only

The extended file adds **15 intermediate timing points per lap**, each as a
`_time` (segment duration) and `_elapsed` (cumulative from lap start) pair:

```
SCL2  Z4  IP1  Z12  SCLC  A7-1  IP2  A8-1  SCLB  PORIN  POROUT  PITREF  SCL1  FORDOUT  FL
```

`FL` closes the lap and its `_elapsed` equals the lap time, so the points partition
the lap. The names suggest physical locations at Le Mans (`PORIN` / `POROUT` for the
Porsche Curves, `FORDOUT` for the Ford chicanes, `PITREF` a pit reference point),
but **no official mapping of these codes to track positions has been obtained** —
treat the interpretation as unverified.

This raises resolution from 3 sectors to 15 segments, roughly a 5× improvement in
locating where lap time is lost. **Availability is the catch:** published only for
Le Mans 2025, and Le Mans and COTA in 2026. See `docs/DECISIONS.md` D-009.

---

## Weather — `26_Weather_*`

Separate file, joined on time rather than on lap.

| Column | Meaning |
|---|---|
| `TIME_UTC_SECONDS` | Unix timestamp — the join key |
| `TIME_UTC_STR` | Human-readable timestamp |
| `AIR_TEMP`, `TRACK_TEMP` | °C |
| `HUMIDITY`, `PRESSURE` | % and mbar |
| `WIND_SPEED`, `WIND_DIRECTION` | Speed and bearing |
| `RAIN` | Rain indicator, `0` in the opening rows |

Sampled approximately once per minute. Joining to laps requires aligning the lap's
`HOUR` (local wall clock) with `TIME_UTC_STR` — **the offset must be established,
not assumed.** `Strategy.md` lists weather as "possibly if obtainable"; it is
obtainable, at high resolution.

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
