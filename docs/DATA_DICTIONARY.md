# Data dictionary

What each column means, and how sure I am about it. The schema is identical across all 28 race files from 2023 to 2026. Anything before 2023 hasn't been checked.

Each field has a label for where it comes from:

- **Observed** — straight from the source file.
- **Reconstructed** — calculated from observed data by a fixed rule.
- **Inferred** — estimated statistically, with uncertainty.
- **Assumed** — chosen because the data can't tell us.

## The race file

`23_Analysis_Race_Hour NN.CSV` — one row per lap per car, 29 columns. Semicolon-separated, UTF-8 with a BOM. The first 15 header names start with a space, and there's an empty column at the end from a trailing semicolon. The loader handles both.

### Who

| Column | Meaning | Notes |
|---|---|---|
| `NUMBER` | Car number | A string, not a number. `007` and `7` are different cars. |
| `DRIVER_NUMBER` | Which of the car's drivers (1, 2, 3…) | Changes only on out-laps (E-003). |
| `DRIVER_NAME` | e.g. `Harry TINCKNELL` | No driver ID exists, so the name is the only identifier. |
| `CLASS` | `HYPERCAR`, `LMGT3`, `LMP2` | LMP2 only appears at Le Mans from 2024. |
| `TEAM`, `MANUFACTURER` | Team and make | |
| `GROUP` | Always empty | Unknown purpose. |

### Timing

| Column | Meaning | Notes |
|---|---|---|
| `LAP_NUMBER` | Lap count for the car, from 1 | No gaps or repeats in the corpus (E-002). |
| `LAP_TIME` | Lap time, `m:ss.SSS` | No missing values at Le Mans 2025. |
| `S1`, `S2`, `S3` | Sector times, formatted | Use the `_SECONDS` versions instead. |
| `S1_SECONDS` … `S3_SECONDS` | Sector times in seconds | |
| `S1_LARGE` … `S3_LARGE` | Sector times in a longer format | How these differ from `S1` isn't known. |
| `ELAPSED` | Race time at the line, `h:mm:ss.SSS` | Always increases within a car (E-002). |
| `HOUR` | Local clock time at the line | Called `HOUR` but it's a full timestamp. |
| `KPH` | Average lap speed | |
| `TOP_SPEED` | Top speed on the lap | Where it's measured isn't documented. |
| `LAP_IMPROVEMENT`, `S1_IMPROVEMENT`… | Mostly `0`, sometimes `2` or `3` | Probably a best-lap marker. Not confirmed. |

### Pits and flags

| Column | Meaning | Notes |
|---|---|---|
| `CROSSING_FINISH_LINE_IN_PIT` | `B` on the **in-lap** — the lap ending in the pit lane | Verified across the corpus (E-003, D-011). |
| `PIT_TIME` | Time in the pit lane, on the **out-lap** | Includes the stop. Median 80 s, but some are hours of garage time. |
| `FLAG_AT_FL` | Track status at the line | `GF` green, `SF` safety car, `FCY` full-course yellow, `FF` finish, `RF` red. The meanings are my reading of the codes, not an official list. |

### Added by the loader

| Column | Meaning |
|---|---|
| `LAP_TIME_S`, `PIT_TIME_S`, `ELAPSED_S` | The duration columns in seconds |
| `S1_S`, `S2_S`, `S3_S` | Sector times in seconds |
| `KPH_N`, `TOP_SPEED_N` | Speeds as numbers |
| `event_key` | Which race, from the filename, e.g. `2025_LE_MANS` |
| `source_file` | The original filename |

A car is identified by `event_key` plus `NUMBER`.

## Built by the project

| Column | Type | Label | Meaning |
|---|---|---|---|
| `is_in_lap` | bool | Reconstructed | The lap ends in the pit lane. |
| `is_out_lap` | bool | Reconstructed | The lap starts from the pit lane. |
| `stint_number` | int | Reconstructed | 1, 2, 3… per car. A new stint starts on each out-lap, except a pit-lane start on lap 1. |
| `stint_lap` | int | Reconstructed | Lap within the stint, from 1. The in-lap is the last lap of its stint. |

| `is_first_lap` | bool | Reconstructed | The car's first lap. |
| `is_pit_lap` | bool | Reconstructed | An in-lap or out-lap. |
| `is_caution_lap` | bool | Reconstructed | Not green at the line. |
| `is_after_caution` | bool | Reconstructed | The lap after a non-green lap. |
| `is_missing_time` | bool | Reconstructed | Lap time or a sector is missing. |
| `is_slow_lap` | bool | Reconstructed | More than 7% slower than the class median at that race. The 7% is assumed (D-012). |
| `is_usable_for_pace_model` | bool | Reconstructed | None of the flags above (E-004). |

### Planned

| Column | Label | Meaning |
|---|---|---|
| `race_position` | Reconstructed | Order by laps completed, then crossing time. Only valid at the timing line. |
| `gap_ahead` | Reconstructed | Time to the car ahead at the line. |
| `is_candidate_traffic` | Inferred | Likely running in slower-class traffic. **Not an observed overtake** (D-004). |
| `lap_residual` | Inferred | Actual lap time minus expected clean pace. |
| `tyre_state`, `fuel_state` | Assumed | Not in the data at all (D-005). |

## Other files

**`23_AnalysisEnduranceWithSections_*`** — the same laps with 15 timing points each, for Le Mans (2025 and 2026) and COTA 2026 only. At Le Mans the point names look like track landmarks (`PORIN`/`POROUT` for the Porsche Curves, `FORDOUT` for the Ford chicanes), but I haven't found an official map of them.

**`26_Weather_*`** — one row a minute: air and track temperature, humidity, pressure, wind, rain. It's keyed on UTC time, while laps use local clock time, so the offset has to be worked out before joining the two.

## Still open

- What the `IMPROVEMENT` columns and `S*_LARGE` columns actually are.
- Where the 15 intermediate points are on track, and whether the codes are stable between circuits.
- The clock offset between lap `HOUR` and weather UTC time.
- Whether there's a separate race-control message file beyond `FLAG_AT_FL`.
