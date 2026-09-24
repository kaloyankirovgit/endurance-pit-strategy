# Experiment log

Every time I ask the data a question, it goes here — including the checks that found nothing. A null result is still a result, and writing it down stops me running the same dead end twice.

Each entry says what I expected before looking and what I actually found — including what the result does *not* show.

| ID | Date | Question | Outcome |
|---|---|---|---|
| E-001 | 2026-09-22 | What's actually in the WEC timing archive? | Richer than expected |
| E-002 | 2026-09-24 | Is the lap record structurally sound? | Yes — zero faults |
| E-003 | 2026-09-24 | What do the pit columns mean, and can stints be rebuilt? | Fully explained |
| E-004 | 2026-09-24 | How many laps are clean enough for a pace model? | 139,283 (78%) |
| E-005 | 2026-09-24 | Can weather be joined to laps, and which stops are garage visits? | Yes — 138,884 clean laps once rain is out |
| E-006 | 2026-09-24 | Does the full pipeline run end to end, and does race order hold up? | Yes — 13 seconds, winners match |

---

## E-001 — What's actually in the WEC timing archive?

*2026-09-22 · descriptive*

**Expected:** lap and 3-sector timing, with no way of localising traffic within a lap. Weather only if I was lucky.

**Looked at:** the Al Kamel timing site across all 15 seasons, then every file for the 2025 Le Mans race in detail (20,182 laps from 62 cars).

**Found:**

- The archive is public — 121 events from 2011 to 2026, no login needed.
- Each race publishes a race-wide lap-by-lap file, not just hourly snapshots.
- The data is very complete. In 20,182 Le Mans laps there are no missing lap times, and only one lap is missing sector data.
- Every lap carries the track status at the line (green, safety car, full-course yellow and so on).
- **Weather is available every minute**, including track temperature and rain. I'd assumed it might not be.
- **Some races have 15 timing points per lap** instead of three. But only at Le Mans (2025 and 2026) and COTA 2026.

**What it doesn't show:** 20,182 laps from one race is still one race. For anything that has to generalise, the sample size is the number of races, not laps.

**Next:** decide between breadth and depth (D-009), then audit the rest of the modern era (D-010).

---

## E-002 — Is the lap record structurally sound?

*2026-09-24 · null result*

**Question:** before building anything on the lap data, is its basic structure sound? Race order and stint detection both quietly assume it is.

**Expected:** some faults, mostly around retirements and cars coming back out of the garage.

**Data:** all 21 races from 2024 to 2026 — 179,259 laps from 833 car entries. Nothing excluded.

**Method:** three checks in `validation/quality.py`. Each one groups the laps by car (event plus car number — car 7 races in every event) and compares every lap with the one before it.

**Found:**

| Check | Faulty rows |
|---|---:|
| Duplicate laps | 0 |
| Elapsed time going backwards | 0 |
| Gaps in lap numbers | 0 |

**Why I trust the zeros:** a check that can never fail also returns zero. So I broke each one on purpose — removing the sort or grouping by driver as well as car, for example — and in five out of five cases the tests caught it.

**What it doesn't show:** nothing about whether the lap times themselves make sense. A lap can be in the right place in the sequence and still have a bad value. It also can't spot a lap the timing system missed entirely if the numbering carried on as normal.

**Side finding:** the loader was keeping an empty trailing column in every race because of a trailing semicolon. Harmless, but it's fixed now and covered by a test.

**Next:** work out the pit columns, then define a usable clean lap.

---

## E-003 — What do the pit columns mean, and can stints be rebuilt?

*2026-09-24 · complete*

**Question:** the source has `CROSSING_FINISH_LINE_IN_PIT` (blank or `B`) and `PIT_TIME`, but nothing says which lap is the in-lap and which is the out-lap. At Le Mans 2025 there were 1,902 `B` laps but only 1,896 `PIT_TIME` values. Without sorting this out, stints can't be rebuilt, and without stints there's no degradation or pit-loss modelling.

**Expected:** `B` to mark the out-lap, going by the column name ("crossing the finish line in the pit").

**Found — the opposite:**

- **`B` is the in-lap.** Its final sector is slow because the car is heading into the pit lane.
- **`PIT_TIME` is on the next lap**, the out-lap. Across the whole corpus, a lap has `PIT_TIME` exactly when the lap before it was `B` — with two exceptions, both on lap 1.

I checked this by eye on several stops in the raw file as well as in code.

**The count gap is fully explained.** Across 21 races there are 9,813 `B` laps and 9,746 `PIT_TIME` values:

- 69 in-laps are a car's final lap — it pitted and never came back out;
- 2 cars have `PIT_TIME` on lap 1 because they started from the pit lane.

9,813 − 69 + 2 = 9,746. Nothing is left over.

**Stints:** with that settled, `reconstruct/stints.py` flags in-laps and out-laps and numbers each car's stints. Across the corpus that gives **10,577 stints** from 833 car entries. The median stint is 12 laps (middle half: 10 to 25), and every in-lap is the last lap of its stint.

**A useful cross-check:** there are 3,478 driver changes in the corpus, and **every one of them happens on an out-lap.** That's independent evidence that the pit reading is right — drivers can only swap in the pits.

**What `PIT_TIME` is:** the median is 80 seconds, with the middle half between 74 and 89. That's too long for time stationary alone, so it's time spent in the pit lane including the stop. But 94 values are over ten minutes, the longest around 17 hours. Those are cars sitting in the garage for repairs, not normal stops.

**What it doesn't show:** pit-lane time isn't pit loss. Pit loss is how much time a stop costs compared with staying out, which needs the in-lap and out-lap compared against normal pace. Garage visits need separating out first.

**Next:** define a usable clean lap, then the Layer 1 pipeline.

---

## E-004 — How many laps are clean enough for a pace model?

*2026-09-24 · complete*

**Question:** a pace model needs laps that show what the car can do on a normal green-flag lap. Which laps should be left out, and how much does the answer depend on where I draw the lines?

**Expected:** around 80% left, with pit laps and caution laps doing most of the removing.

**The rules** (`features/clean_laps.py`, D-012). A lap is left out if it's:

- the car's first lap — standing start, cold tyres, a pack of cars;
- an in-lap or out-lap;
- run under anything other than green at the line;
- the lap straight after a caution — the flag is read at the line, so a lap that went green halfway round still shows as green;
- missing its lap time or a sector;
- more than 7% slower than the median clean lap for its class at that race.

**Found:** **139,283 of 179,259 laps (77.7%) are usable**, covering all 21 races and 832 of the 833 car entries.

| Rule | Laps caught | Laps caught by this rule alone |
|---|---:|---:|
| First lap | 833 | 406 |
| Pit lap | 19,382 | 6,351 |
| Caution | 11,861 | 889 |
| After caution | 11,146 | 123 |
| Missing time | 24 | 10 |
| Slow lap (>7%) | 32,013 | 6,501 |

Most rules overlap a lot. The slow-lap rule catches the most, but four in five of those laps would go anyway for another reason.

**How much the threshold matters:**

| Slow-lap threshold | Usable laps |
|---|---:|
| 3% | 135,306 |
| 5% | 138,390 |
| **7%** | **139,283** |
| 10% | 140,944 |
| 15% | 142,889 |

Going from 3% to 15% changes the count by about 5%. So the choice matters, but not dramatically.

**It varies a lot by race.** São Paulo 2026 keeps 94% of its laps. Le Mans 2024 keeps only 43%, and COTA 2025 only 51% — both lost a large share to caution periods.

**What it doesn't show:**

- **Rain isn't handled yet.** A wet lap under green passes every rule unless it's slow against the race median, and in a mostly wet race the median is wet too. That needs the weather join.
- **The reference uses the whole race.** Fine for cleaning historical data, but it can't be used for a decision during a race — that would be using the future.
- **7% is my choice**, not something measured. Anything built on these laps should be re-run at a couple of other thresholds.
- **Traffic laps are mostly still in.** That's on purpose — traffic is what the next layer measures, so it can't be filtered out here. Only the very worst cases get caught by the slow-lap rule.

**Next:** separate garage visits from normal stops, then build the interim layer with these flags in it.

---

## E-005 — Can weather be joined to laps, and which stops are garage visits?

*2026-09-24 · complete*

**Question:** two gaps left by E-003 and E-004. The clean-lap rules couldn't see rain, and `PIT_TIME` mixed normal stops with cars parked in the garage for repairs.

### Weather

The weather files use UTC. The laps use local wall-clock time (`HOUR`) plus race time (`ELAPSED`). I expected to line them up with `ELAPSED` from the scheduled start in the session folder name. Two races showed that was wrong:

- **Spa 2024** — `HOUR` minus `ELAPSED` jumps by nearly two hours partway through. `ELAPSED` stops during a red flag, and the wall clock doesn't. The weather file runs about two hours past the `ELAPSED`-based finish, which fits.
- **COTA 2025** — the folder says 13:30, but every lap puts the start at 13:00. The weather file agrees with 13:00.

So each lap's UTC time comes from `HOUR`, the race date and the circuit's time zone (`reconstruct/race_clock.py`), with a day added once a race passes midnight. Then `merge_asof` gives each lap the latest reading at or before it crossed the line, within five minutes.

**Found:** all 179,259 laps got a reading. For every race, the weather file starts within about three minutes of the race start, which is also a check that each weather file belongs to the right race.

Rain shows up in three races only:

| Race | Laps with rain |
|---|---:|
| COTA 2025 | 875 |
| Le Mans 2024 | 760 |
| Imola 2024 | 40 |

`RAIN` is mostly 0 or 1, but at Le Mans 2024 it goes up to 9. I'm treating anything above 0 as rain. What the numbers mean isn't documented.

### Garage visits

There's no clean break in the pit-time distribution, so I looked at it relative to each race's median stop:

| Stop longer than | Stops |
|---|---:|
| 2× median | 404 |
| **3× median** | **185** |
| 4× median | 133 |
| 6× median | 107 |

Most stops at 2–3× the median happen under safety car (182 of 219) — that looks like queueing at pit exit behind the safety car, which is a real race cost, not a repair. Above 3× it's mostly green flag. So a **garage visit is a stop over 3× the race median** (about four minutes). That gives 185 stops across 19 races, 86 hours of garage time in total, with a median of 11 minutes.

### Clean laps with rain added

Wet laps are now a clean-lap rule, and they're kept out of the slow-lap reference too.

- **138,884 of 179,259 laps are usable (77.5%)**, down from 139,283.
- 1,675 laps are wet, but only 340 of those weren't already excluded for another reason. Most rain came with safety cars or slow laps anyway.
- **COTA 2025 is now the weakest race at 41% usable**, then Le Mans 2024 at 43%.

**What it doesn't show:**

- **A track stays wet after the rain stops.** `RAIN` is a sensor reading, so drying laps pass as dry unless they're slow. Track temperature or lap times might pick that up later.
- **The time zones are my lookup**, not from the source. They're checked indirectly by the weather lining up with every race.
- **The 3× garage cut-off is a choice.** A pit-loss model should be checked at 2× and 4× as well.
- **Only rain is used so far.** Track temperature is joined to every lap, but no rule uses it yet.

**Next:** the interim layer in Parquet, with all these flags in it.

---

## E-006 — Does the full pipeline run end to end, and does race order hold up?

*2026-09-24 · complete*

**Question:** can one command take the raw race and weather files to validated tables, and is the race order it rebuilds believable?

**Method:** `python -m endurance_strategy.pipeline`. It chains everything so far, adds race order and gaps in DuckDB SQL, checks the result against a Pandera schema, then writes Parquet.

**Found:**

| Table | Rows |
|---|---:|
| `interim/laps.parquet` | 179,259 |
| `processed/stints.parquet` | 10,577 |
| `processed/pit_stops.parquet` | 9,746 |

It runs in about 13 seconds on a laptop. On the synthetic fixture, two runs give identical output, and a test pins that.

The schema check earned its place straight away. `RAIN` was coming through as whole numbers in races with no missing readings and as decimals otherwise, and the check failed on it before anything was written.

**Race order:** position at each crossing ranks the cars that completed that lap by when they did it, so a lapped car sits behind. For each lap I also keep the gap to the car ahead in the race, and the gap to whichever car crossed the line just before on the road, along with its class. The road gap is what the traffic work will use.

As a first check, the car in P1 on the final lap at Le Mans 2024 is #50 Ferrari AF Corse, and at Le Mans 2025 it's #83 AF Corse — both the actual winners.

A first descriptive look: on clean laps, the median road gap at the line is about two seconds, and roughly half of clean laps cross within two seconds of another car. Traffic is everywhere, not an occasional thing. This is a description only, not a traffic effect.

**What it doesn't show:**

- **Order is only known at the line.** Between crossings there's no position data, so a pass mid-lap is invisible until the next crossing.
- **It isn't checked against the official classifications yet.** Two known winners matching is a sanity check, not validation. The `03_Classification` files would do it properly.

**Next:** validate race order against the official classifications, then start on traffic exposure.
