# Experiment log

Every time I ask the data a question, it goes here, including the checks that found nothing. A null result is still a result, and writing it down stops me running the same dead end twice.

Each entry says what I expected before looking and what I actually found, including what the result does *not* show.

| ID | Date | Question | Outcome |
|---|---|---|---|
| E-001 | 2026-09-22 | What's actually in the WEC timing archive? | Richer than expected |
| E-002 | 2026-09-24 | Is the lap record structurally sound? | Yes, zero faults |
| E-003 | 2026-09-24 | What do the pit columns mean, and can stints be rebuilt? | Fully explained |
| E-004 | 2026-09-24 | How many laps are clean enough for a pace model? | 139,283 (78%) |
| E-005 | 2026-09-24 | Can weather be joined to laps, and which stops are garage visits? | Yes, 138,884 clean laps once rain is out |
| E-006 | 2026-09-24 | Does the full pipeline run end to end, and does race order hold up? | Yes, 13 seconds and the winners match |

---

## E-001: What's actually in the WEC timing archive?

*2026-09-22 · descriptive*

**Expected:** lap and 3-sector timing, with no way of localising traffic within a lap. Weather only if I was lucky.

**Looked at:** the Al Kamel timing site across all 15 seasons, then every file for the 2025 Le Mans race in detail (20,182 laps from 62 cars).

**Found:**

- The archive is public, with 121 events from 2011 to 2026 and no login needed.
- Each race publishes a race-wide lap-by-lap file, not just hourly snapshots.
- The data is very complete. In 20,182 Le Mans laps there are no missing lap times, and only one lap is missing sector data.
- Every lap carries the track status at the line (green, safety car, full-course yellow and so on).
- **Weather is available every minute**, including track temperature and rain. I'd assumed it might not be.
- **Some races have 15 timing points per lap** instead of three. But only at Le Mans (2025 and 2026) and COTA 2026.

**What it doesn't show:** 20,182 laps from one race is still one race. For anything that has to generalise, the sample size is the number of races, not laps.

**Next:** decide between breadth and depth (D-009), then audit the rest of the modern era (D-010).

---

## E-002: Is the lap record structurally sound?

*2026-09-24 · null result*

**Question:** before building anything on the lap data, is its basic structure sound? Race order and stint detection both quietly assume it is.

**Expected:** some faults, mostly around retirements and cars coming back out of the garage.

**Data:** all 21 races from 2024 to 2026, which is 179,259 laps from 833 car entries. Nothing excluded.

**Method:** three checks in `validation/quality.py`. Each one groups the laps by car (event plus car number, since car 7 races in every event) and compares every lap with the one before it.

**Found:**

| Check | Faulty rows |
|---|---:|
| Duplicate laps | 0 |
| Elapsed time going backwards | 0 |
| Gaps in lap numbers | 0 |

**Why I trust the zeros:** a check that can never fail also returns zero. So I broke each one on purpose, for example by removing the sort or grouping by driver as well as car. In five out of five cases the tests caught it.

**What it doesn't show:** nothing about whether the lap times themselves make sense. A lap can be in the right place in the sequence and still have a bad value. It also can't spot a lap the timing system missed entirely if the numbering carried on as normal.

**Side finding:** the loader was keeping an empty trailing column in every race because of a trailing semicolon. Harmless, but it's fixed now and covered by a test.

**Next:** work out the pit columns, then define a usable clean lap.

---

## E-003: What do the pit columns mean, and can stints be rebuilt?

*2026-09-24 · complete*

**Question:** the source has `CROSSING_FINISH_LINE_IN_PIT` (blank or `B`) and `PIT_TIME`, but nothing says which lap is the in-lap and which is the out-lap. At Le Mans 2025 there were 1,902 `B` laps but only 1,896 `PIT_TIME` values. Without sorting this out, stints can't be rebuilt, and without stints there's no degradation or pit-loss modelling.

**Expected:** `B` to mark the out-lap, going by the column name ("crossing the finish line in the pit").

**Found the opposite:**

- **`B` is the in-lap.** Its final sector is slow because the car is heading into the pit lane.
- **`PIT_TIME` is on the next lap**, the out-lap. Across the whole corpus, a lap has `PIT_TIME` exactly when the lap before it was `B`
  - With two exceptions, both on lap 1.

I checked this by eye on several stops in the raw file as well as in code.

**The count gap is fully explained.** Across 21 races there are 9,813 `B` laps and 9,746 `PIT_TIME` values:

- 69 in-laps are a car's final lap, because it pitted and never came back out;
- 2 cars have `PIT_TIME` on lap 1 because they started from the pit lane.

9,813 − 69 + 2 = 9,746. Nothing is left over.

**Stints:** with that settled, `reconstruct/stints.py` flags in-laps and out-laps and numbers each car's stints. Across the corpus that gives **10,577 stints** from 833 car entries. The median stint is 12 laps (middle half: 10 to 25), and every in-lap is the last lap of its stint.

**A useful cross-check:** there are 3,478 driver changes in the corpus, and **every one of them happens on an out-lap.** That's independent evidence that the pit reading is right, since drivers can only swap in the pits.

**What `PIT_TIME` is:** the median is 80 seconds, with the middle half between 74 and 89. That's too long for time stationary alone, so it's time spent in the pit lane including the stop. But 94 values are over ten minutes, the longest around 17 hours. Those are cars sitting in the garage for repairs, not normal stops.

**What it doesn't show:** pit-lane time isn't pit loss. Pit loss is how much time a stop costs compared with staying out, which needs the in-lap and out-lap compared against normal pace. Garage visits need separating out first.

**Next:** define a usable clean lap, then the Layer 1 pipeline.

---

## E-004: How many laps are clean enough for a pace model?

*2026-09-24 · complete*

**Question:** a pace model needs laps that show what the car can do on a normal green-flag lap. Which laps should be left out, and how much does the answer depend on where I draw the lines?

**Expected:** around 80% left, with pit laps and caution laps doing most of the removing.

**The rules** (`features/clean_laps.py`, D-012). A lap is left out if it's:

- the car's first lap, with its standing start and cold tyres in a pack of cars;
- an in-lap or out-lap;
- run under anything other than green at the line;
- the lap straight after a caution, because the flag is read at the line, so a lap that went green halfway round still shows as green;
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

**It varies a lot by race.** São Paulo 2026 keeps 94% of its laps. Le Mans 2024 keeps only 43%, and COTA 2025 only 51%. Both lost a large share to caution periods.

**What it doesn't show:**

- **Rain isn't handled yet.** A wet lap under green passes every rule unless it's slow against the race median, and in a mostly wet race the median is wet too. That needs the weather join.
- **The reference uses the whole race.** Fine for cleaning historical data, but it can't be used for a decision during a race
  - That would be using the future.
- **7% is my choice**, not something measured. Anything built on these laps should be re-run at a couple of other thresholds.
- **Traffic laps are mostly still in.** That's on purpose
  - Traffic is what the next layer measures, so it can't be filtered out here. Only the very worst cases get caught by the slow-lap rule.

**Next:** separate garage visits from normal stops, then build the interim layer with these flags in it.

---

## E-005: Can weather be joined to laps, and which stops are garage visits?

*2026-09-24 · complete*

**Question:** two gaps left by E-003 and E-004. The clean-lap rules couldn't see rain, and `PIT_TIME` mixed normal stops with cars parked in the garage for repairs.

### Weather

The weather files use UTC. The laps use local wall-clock time (`HOUR`) plus race time (`ELAPSED`). I expected to line them up with `ELAPSED` from the scheduled start in the session folder name. Two races showed that was wrong:

- **Spa 2024**
  - `HOUR` minus `ELAPSED` jumps by nearly two hours partway through. `ELAPSED` stops during a red flag, and the wall clock doesn't. The weather file runs about two hours past the `ELAPSED`-based finish, which fits.
- **COTA 2025**
  - The folder says 13:30, but every lap puts the start at 13:00. The weather file agrees with 13:00.

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

Most stops at 2–3× the median happen under safety car (182 of 219). That looks like queueing at pit exit behind the safety car, which is a real race cost, not a repair. Above 3× it's mostly green flag. So a **garage visit is a stop over 3× the race median** (about four minutes). That gives 185 stops across 19 races, 86 hours of garage time in total, with a median of 11 minutes.

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

## E-006: Does the full pipeline run end to end, and does race order hold up?

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

As a first check, the car in P1 on the final lap at Le Mans 2024 is #50 Ferrari AF Corse, and at Le Mans 2025 it's #83 AF Corse. Both are the actual winners.

A first descriptive look: on clean laps, the median road gap at the line is about two seconds, and roughly half of clean laps cross within two seconds of another car. Traffic is everywhere, not an occasional thing. This is a description only, not a traffic effect.

**What it doesn't show:**

- **Order is only known at the line.** Between crossings there's no position data, so a pass mid-lap is invisible until the next crossing.
- **It isn't checked against the official classifications yet.** Two known winners matching is a sanity check, not validation. The `03_Classification` files would do it properly.

**Next:** validate race order against the official classifications, then start on traffic exposure.

---

## E-007: Does the rebuilt race order match the official classification?

*2026-10-20 · complete*

**Question:** for every car in the 21 races, does the order I rebuild from the lap timing agree with the official end-of-race classification?

**Method:** downloaded the final-hour `03_Classification` CSV for each race, with hashes in a manifest (`io/download.py`). For each car I take the laps and elapsed time at its last crossing and rank by laps, then time. `python -m endurance_strategy.validation.classification` compares that with the official file car by car. Six tests on a synthetic race cover the comparison, including a penalised car, a lap difference and a retired car with no position.

**Found:**

| Check | Result |
|---|---:|
| Cars in both sources | 833 of 833 |
| Lap count matches | 830 of 833 |
| Finishing time matches to the millisecond | 782 of 833 |
| Raw position matches, classified cars | 640 of 704 |

Every time difference has the official time longer than mine:

- **48 cars** are out by a whole number of seconds on the same lap count (5, 10, 45, 95 and so on). That pattern fits time penalties the stewards added to the result.
- **3 cars** are credited with one or two laps fewer than they crossed the line, which fits a lap penalty or a lap that wasn't counted.

> **Correction (2026-10-20, found by the reviewer eval in E-008).** This entry first reported that the order matched for all 654 classified cars with no time or lap difference. That check was circular. The official order is laps then time, so once a car's laps and time match, its order has to match, and the 654 of 654 couldn't have come out any other way. The evidence is the per-car match of laps and finishing time in the table above. The circular metric has been removed from the code.

The raw position misses all come from these cars. One penalised car drops down the order and pushes everyone it passes up by one place. At Bahrain 2024, car #51 alone accounts for 12 of them.

Two format quirks came up. The 2024 Spa file has a different column order and leaves retired cars without a position, so the reader picks columns by name. COTA 2026 names its file with a `_Final` suffix, so the downloader falls back to that name.

**What it doesn't show:**

- **The penalties are inferred, not confirmed.** Whole-second differences point to time penalties, but I haven't matched them against the stewards' decision documents.
- **It checks the final order only.** Position at earlier laps comes from the same SQL, but no official source gives the order lap by lap, so that isn't checked directly.
- **It isn't independent of the timing.** The classification comes from the same timing system, so this tests my rebuild logic, not whether the timing loops themselves are right.

**Next:** race order can now feed the traffic work. Penalties applied after the finish don't change what happened on track, so they don't affect the road gaps used for traffic exposure.

---

## E-008: Does the statistical-reviewer agent catch planted flaws?

*2026-10-20 · complete*

**Question:** the `statistical-reviewer` agent is meant to find the weaknesses in a result before it's reported. Does it find them, and does it leave sound work alone?

**Method:** 16 synthetic write-ups in this project's style (`evals/statistical_reviewer/`). 12 have one planted flaw each and 4 are controls with none. Each one was run 3 times through the agent headless (`claude -p`, model `claude-opus-5-5`), from an empty folder with no tools and a fixed JSON schema for the answer. Scoring is an exact match against hand-set labels, with no LLM judge. A flawed case counts as caught when the reviewer reports an accepted category at `major` or `critical`. A control counts as a false alarm on any `critical` weakness or a `not supported` verdict. Run `20261020T164733Z`.

**Found:**

| Measure | Result |
|---|---:|
| Flawed runs with the planted category reported at any severity | 36 of 36 |
| Flawed runs with it at major or critical | 33 of 36 |
| Flawed cases caught at major or critical (majority of 3 runs) | 11 of 12 |
| Control runs with a false alarm | 2 of 12 |
| Control cases with a false alarm (majority of 3 runs) | 0 of 4 |

- **The one miss** is the case that calls inferred exposures "measured overtakes". In all three runs the reviewer noticed the wording but rated it minor. It's the category this project cares about most, so this is a real gap in the agent.
- **The two control alarms were both fair once I read them:**
  - On the race-order control, the reviewer pointed out that the "order matches for all 654 unpenalised cars" check couldn't fail: official order is laps then time, so matching laps and times forces the order to match. That was a real flaw in E-007, which has been corrected.
  - On the stint-age control, it said the slope mixes stints with different compounds and fuel loads. That's a fair point, though "critical" overstates it.
- So the control set wasn't as clean as I'd labelled it. One of the four controls contained a genuine flaw, and it came from my own write-up.

**What it doesn't show:**

- **The same model family wrote the cases and reviews them**, so the planted flaws may be easier for it than flaws someone else would write. 11 of 12 may be generous.
- **12 flawed cases and 4 controls is small.** One case changes the catch rate by about 8 points.
- **Picking a category from a fixed list is stricter than a free-text review**, so some misses may be filing differences rather than blind spots.
- **This set can't be used to improve the agent.** If I change the agent's prompt to fix the overtake miss and rerun on these same cases, the score would be tuned on its own test set. An improved prompt needs a fresh set of cases.

**Next:** a held-out case set before any change to the agent prompt, then the same eval for the other review agents.

---

## E-009: Can keyword search find the right regulation clause?

*2026-10-23 · complete*

**Question:** given a question about the WEC rules, does a plain keyword retriever put the clause that answers it near the top? This measures retrieval only. No answer is generated yet.

**Method:**

- **Corpus:** the 2024, 2025 and 2026 sporting regulations (D-018), giving 855 chunks: 280 for 2024, 283 for 2025 and 292 for 2026. One chunk per lowest-level numbered article.
- **Retriever:** BM25 with textbook settings, filtered to the season of the question.
- **Questions** (`evals/regulations/questions.json`):
  - 30 answerable questions about the 2026 rules, each written in a race engineer's words rather than the regulation's, with the article or articles that answer it.
  - 6 questions the regulations can't answer, such as Balance of Performance figures, race results and lap records.
  - The answerable questions are also asked of 2024 and 2025 wherever an article with the same heading exists. That gives 52 more, with the answer mapped by heading rather than checked by hand.
- **Run:** `python scripts/run_retrieval_eval.py`.

**Found:**

| Setting | Questions | recall@1 | recall@3 | recall@5 |
|---|---:|---:|---:|---:|
| 2026, season filter | 30 | 15 | 20 | 24 |
| 2024 and 2025 versions, season filter | 52 | 30 | 39 | 46 |
| All seasons, no season filter | 82 | 15 | 44 | 49 |

- **Most misses are vocabulary.** The question says "top up fluids" and the rule says "replenishment". Likewise "stay seated" against "remain on board", "warm the tyres" against "heating", and "which rules win" against "take precedence". Keyword search can't bridge these, and it's the case for trying embeddings.
- **Versions matter in practice.** Without the season filter, the right article from the wrong season comes out on top for 30 of 82 questions, because the wording is often identical across years. Ranking can't tell the seasons apart, so the season has to be metadata.
- **A score cut-off can't do refusal.** The best score for an unanswerable question reached 18.0, above the median of 14.4 for answerable ones. Refusing when the documents don't cover a question will need a check at the answer stage, not a retrieval threshold.

**What it doesn't show:**

- **The questions are few and written by one author**, with the same model that built the system. 30 questions means one question moves recall by about 3 points.
- **The 2024 and 2025 answers were mapped by heading, not checked by hand.** If a clause kept its heading but changed its content, the label could be wrong.
- **Nothing here is tuned.** BM25 settings are the defaults. Any change made because of these misses would need a fresh question set to report on.
- **Tables are scrambled by the extraction**, so questions answered by a table (q22, tyre allocations) test the extraction as much as the retrieval.

**Next:** embeddings against this BM25 baseline on a fresh question set, then answer generation with citations and refusal tests.

---

## E-010: Do the regulation answers stay grounded, and does the system refuse when it should?

*2026-10-23 · complete*

**Question:** with BM25 retrieval underneath, does the answer step cite the right clause, keep the facts right, refuse when the extracts don't cover the question, and keep strategy questions out?

**Method:** the router, answerer and checker from D-019, run 3 times on each of the 36 questions from E-009 and 6 routing cases (3 strategy questions, 3 off-topic). The model was `claude-opus-5-5` through `claude -p`, and retrieval was the BM25 top 5 with the season filter. Scoring is against labels, with no LLM judge:

- does the answer cite an answering chunk?
- does it contain the key fact? (Set for 21 of the 30 answerable questions, such as "60" for the pit-lane limit.)
- does an unanswerable question get no answer?

Run `20261023T211614Z`.

**Found:**

| Measure | Result |
|---|---:|
| Routing cases sent the right way | 18 of 18 runs |
| Answerable runs answered and citing an answering chunk | 72 of 90 |
| ...of runs where retrieval found the answering chunk | 72 of 72 |
| Runs where retrieval missed: refused / answered anyway | 12 / 6 of 18 |
| Key fact present (after one label fix, see below) | 54 of 63 runs |
| Answers rejected by the checker | 0 of 78 |
| Unanswerable runs with nothing shown | 18 of 18 |

- **Every miss traces to retrieval.** When the right clause was retrieved, the answer cited it, passed the checker and, where a key fact was set, contained it. The 6 runs answered after a retrieval miss were honest partial answers. One said "Article 13.2.5 isn't in the extracts, so the actual penalties can't be stated."
- **One label was wrong.** q08's key fact accepted "closed" but not "closes", and the answer said "the pit lane entry closes". As first scored, the key fact was present in 51 of 63 runs. With the label fixed and the saved answers rescored, with no new model calls, it's 54 of 63. All 9 remaining misses are on three questions where retrieval missed.
- **The checker didn't fire in this run.** All 78 answers quoted their extracts word for word and kept their numbers traceable. It's tested on synthetic cases, and it caught its own bug in a smoke run (it rejected a correct answer over "2026", which was in the extract header but not the clause, now fixed).

**What it doesn't show:**

- **The unanswerable questions never reached the answerer.** The router sent all of them to "out of scope", because its instructions name Balance of Performance and results as out of scope. The answerer's own refusal was only tested on the 12 runs after a retrieval miss. In-scope questions that the regulations don't answer are needed to test refusal properly.
- **Key facts cover 21 questions and are short strings.** A wrong answer containing the right number would pass, and a right answer worded differently can fail, as q08 did.
- **The same model family helped write the questions and answers them.**
- **3 runs per question.** No run-to-run differences changed any question's outcome here, but that's a small sample of the variance.

---

## E-011: Do embeddings beat BM25 on a fresh question set?

*2026-10-23 · complete*

**Question:** E-009's misses were mostly vocabulary. Does an embedding model fix that, and does it hold on questions written after the decision to try it?

**Method:**

- **Retrievers:** BM25 (E-009), embeddings from `BAAI/bge-small-en-v1.5` run locally through `fastembed`, and a hybrid that fuses the two rankings (reciprocal rank fusion, constant 60). None were tuned.
- **Question sets:**
  - the 30 original questions;
  - 30 fresh ones in `questions_heldout.json` (plus 4 unanswerable), on different articles, written before any embedding was run.
- **Settings:** season filter on throughout. `python scripts/run_retrieval_comparison.py`.

**Found:**

| Set | Retriever | recall@1 | recall@3 | recall@5 |
|---|---|---:|---:|---:|
| Original (30) | BM25 | 15 | 20 | 24 |
| Original (30) | Embeddings | 22 | 27 | 27 |
| Original (30) | Hybrid | 18 | 25 | 27 |
| Held-out (30) | BM25 | 19 | 25 | 27 |
| Held-out (30) | Embeddings | 22 | 26 | 27 |
| Held-out (30) | Hybrid | 21 | 29 | 29 |

Question by question on the held-out set:

| Comparison | First wins | Second wins |
|---|---:|---:|
| Embeddings against BM25, rank 1 | 4 | 1 |
| Embeddings against BM25, top 5 | 2 | 2 |
| Hybrid against BM25, top 5 | 2 | 0 |

- **The big gain on the original set shrinks on the fresh set.** That's what a held-out set is for. The original questions were the ones whose misses motivated trying embeddings.
- **The hybrid never did worse than BM25 in the top 5**, across both sets: 5 wins and 0 losses. A sign test on 5 against 0 gives p ≈ 0.06, so it's suggestive and not established.
- **Embeddings fixed some vocabulary misses but not all.** "Stay seated" (q17), "warm the tyres" (q27) and "which rules win" (q23) went from outside the top 5 to rank 1. "Top up fluids" (q16) is still missed by every retriever.
- **They also lost questions BM25 got right:**
  - q15 and q10 on the original set;
  - h07 and h26 on the held-out set.

**What it doesn't show:**

- **30 questions per set can't separate retrievers that differ by a few questions.** By the baseline rule, BM25 stays the default (D-020).
- **The held-out questions were written after reading the clauses**, like the originals, so their wording may sit close to the regulation's. BM25 scored higher on them (19 against 15 at rank 1), which fits that.
- **26 of the 855 chunks run past the model's roughly 512-token limit** and are cut off when embedded. They include the long appendices.
- **One embedding model, untuned.** A larger model or one tuned for retrieval might do better, and that would be a separate comparison.


---

## E-012: Can answers follow the car class the user picks?

*2026-10-24 · complete*

**Question:** a strategy tool is used for one class at a time. If the user picks Hypercar or LMGT3, does the answer use that class's rules and figures, and is a class the corpus doesn't cover refused?

**Checked first: should retrieval filter by class?** I tagged each 2026 chunk by the classes its text names: 198 name none, 69 only Hypercar, 4 only LMGT3, 21 both.

- **A tag says which class a clause names, not which class it applies to.** 6.5.5 (at most 3 tyre sets at the front of the garage) applies to all competitors, but one sentence about Hypercar submissions tags it Hypercar-only. 4.1.4 (high-voltage safety) is the same. A class filter would hide these from an LMGT3 user.
- **Adding the class to the BM25 query costs recall and gains nothing.** On the original 30 questions recall@5 went from 24 to 23 with "Hypercar" added and to 22 with "LMGT3", losing q10 and q28. On the held-out 30 it stayed at 27.
- So retrieval stays class-blind. The class goes to the answer step only.

**Method:** the class is an explicit input (`Hypercar`, `LMGT3` or `LMP2`), as it would be in a menu, not read from the question. The answer prompt gets the class and is told to use only that class's figures. LMP2 is refused in code after routing, because the corpus is the WEC sporting regulations, which cover Hypercar and LMGT3 only (6.1.1). LMP2 races only at Le Mans, under ACO regulations that aren't collected.

The question set is `questions_class.json`: 5 questions asked once per class (10 runs where the right answer differs by class) plus 3 LMP2 questions. Each answerable question has a key fact for its class and, where it applies, "wrong facts" from the other class that must not appear in the answer. Numbers match as whole tokens, so "18" doesn't match inside "1812km". Run `20261023T233848Z`, 3 repeats, BM25 top 5 with the season filter. It took 97 seconds.

**Found:**

| Measure | Result |
|---|---:|
| Right clause in the top 3, class-blind retrieval | 10 of 10 questions |
| Answered and citing the right clause | 30 of 30 runs |
| Key fact for the chosen class present | 30 of 30 runs |
| Other class's fact shown, where checked | 1 of 24 runs |
| LMP2 routed to the regulations path, then refused in code | 9 of 9 runs |

- **The one flagged run was correct but broke the instruction.** For LMGT3 licences (c06) it said "at least Grade B" and added "Grade A is only required in the Hypercar category." That's true, but it states the other class's rule.
- **The prompt change didn't move the original set.** Rerun on `questions.json` with routing (`20261023T234349Z`, 301 seconds): 72 of 72 retrieval hits cited the right clause, key facts 54 of 63, routing 18 of 18, all as in E-010. After retrieval misses it refused 14 and gave partial answers 4 times (12 and 6 in E-010), which is within run-to-run variation at 18 runs.
- **A code review before this run found three grading faults, fixed first:** a refusal would have counted as a wrong-class answer, c09 had no wrong facts, so an answer reading the LMGT3 table could pass, and "18" matched inside "1812km". Rescoring the E-010 answers with the new matcher still gives 54 of 63.

**What it doesn't show:**

- **It tests reading the right row, not retrieval.** Every paired question had its clause in the top 3.
- **There's no comparator.** I didn't run the paired set without the class, so this doesn't show how often the model mixes classes when it isn't told one.
- **The LMP2 refusal is guaranteed by code.** What's measured is that the router sends those questions down the regulations path.
- **5 pairs from one author,** written after reading the clauses. 2 of the 5 read from the 6.5.4 tyre table, whose header comes out of the PDF scrambled. The answers still took the right row, but that's 2 questions on one table, and fixing the table extraction is a separate open job.
- **The game the strategy tool is aimed at may not follow the real regulations,** and nothing here tests that.

---

## E-013: Do Hypercar laps get slower with more GT3 cars to catch?

*2026-10-24 · complete. The plan was written before any lap-time outcome was computed, and the checks added afterwards are marked as such.*

**Question:** for a Hypercar, how does lap time change with the number of LMGT3 cars it is expected to catch during the lap? This is the first traffic result (Layer 2), and it is an association, not a per-overtake cost (D-004).

**Exposure (reconstructed from observed crossings, with a chosen window):** at the start of each Hypercar lap, count the LMGT3 cars that crossed the line in the previous W seconds, leaving out crossings made in the pit lane. Those cars are less than W seconds ahead on the road. W is the race's class pace gap (median usable LMGT3 lap minus median usable Hypercar lap, 9.4 to 16.0 s across the 18 races), so a car inside the window should be caught before the lap ends. The count is taken at the start of the lap because the end-of-lap gap is partly caused by being held up.

**Outcome and comparison:** lap time against the same car's own stint (one driver, one set of tyres), with a straight-line trend in stint lap removed from both the lap time and the exposure. That's a fixed-effects regression with one line per stint. Two numbers: seconds per car (count capped at 6), and each exposure level 1, 2, 3 and 4+ against 0.

**Data:** the 18 races outside Le Mans (two classes only). Hypercar laps that are green, dry, not a first, pit or post-caution lap, with no missing timing, in stints of at least 5 such laps.

**Intervals:** 95% percentile intervals from 2,000 bootstrap samples that draw whole races (seed 20261024). Races are the independent unit, so the interval is about the 18 races, not the laps.

**Fixed before looking:**
- Primary: W = race pace gap, the standard slow-lap rule (D-012), the linear stint trend.
- Sensitivity:
  - W fixed at 5, 10, 15 and 20 s;
  - the loose slow-lap rule (only laps over 1.25 times the class median dropped), because the standard rule removes some heavily delayed traffic laps and pulls the estimate towards zero;
  - stint mean instead of the stint line;
  - a race-by-race slope, to see whether one track drives the average.

**Expected:** a positive slope, on the order of a second per car. That's a guess, written down so the result can be compared with it, and it isn't a measurement.

**Checked first:** the estimator recovered a known 1.2 s cost per car on made-up data to within 0.05 s. A first version that removed the stint trend from lap time only, not from the exposure, came out 10% low (1.08 s). That bias was fixed before any real data was run.

**Found** (run `20261024T005439Z`, `python scripts/run_traffic_baseline.py`, output in `reports/outputs/`, which stays local). Sample: 18 races at 7 circuits, 323 Hypercar car entries, 83 drivers, 2,206 stints and 55,036 laps.

**Headline:** compared within the same stint, a Hypercar lap is longer by **0.37 s (0.33 to 0.41) for each LMGT3 car that crossed the line within the race's class pace gap ahead of it at the start of the lap**. Across window widths of 5 to 20 s the per-car figure runs from 0.41 to 0.26 s. That spread is bigger than the sampling interval, so the per-car number describes this exposure definition as much as traffic itself. Laps with exactly one such car against laps with none differ by 0.39 to 0.42 s at every window, which makes that the steadier number. All of these are associations with an inferred exposure. They are not a measured cost per overtake, and drivers pushing or saving, local yellows and Hypercar fights more than 2 s apart are not controlled.

| Exposure level against 0 cars (window = race pace gap) | Laps | Difference | 95% interval (races resampled) |
|---|---:|---:|---:|
| 0 cars (reference) | 17,751 | | |
| 1 car | 14,260 | 0.40 s | 0.35 to 0.45 |
| 2 cars | 10,765 | 0.73 s | 0.66 to 0.81 |
| 3 cars | 6,163 | 1.04 s | 0.94 to 1.14 |
| 4 or more (mean 5.2) | 6,097 | 1.76 s | 1.58 to 1.97 |
| Per car (count capped at 6) | 55,036 | 0.37 s | 0.33 to 0.41 |

- **The rise is close to straight.** The 4+ level averages 5.2 cars, and 1.76 / 5.2 is about 0.34 s per car.
- **Positive at all 18 races,** from 0.23 s (Fuji 2024) to 0.55 s (COTA 2025). Each race's window differs (9.4 to 16.0 s), so these per-car figures aren't on one scale. Spa has the widest window, which should lower its figure, yet it's near the top in all three years (0.49 to 0.54 s). Why is untested.
- **Against my guess:** I'd written down about a second per car. That guess was about the cost of a pass, which this design doesn't measure, so the two aren't directly comparable.
- **Planned sensitivity:**

| Variation | Per car | Interval | 1 car against 0 |
|---|---:|---:|---:|
| Window 5 s | 0.41 s | 0.38 to 0.46 | 0.39 s |
| Window 10 s | 0.37 s | 0.34 to 0.41 | 0.42 s |
| Window 15 s | 0.31 s | 0.27 to 0.35 | 0.42 s |
| Window 20 s | 0.26 s | 0.22 to 0.30 | 0.41 s |
| Loose slow-lap rule (55,640 laps) | 0.37 s | 0.33 to 0.41 | 0.41 s |
| Stint mean instead of a stint line | 0.36 s | 0.33 to 0.40 | 0.37 s |

- **Checks added after seeing the result** (not planned; now in the script and its output):
  - **Resampling the 7 circuits** instead of the races: 0.32 to 0.43 s per car.
  - **LMGT3 cars 2W to 3W ahead,** too far to catch this lap: 0.00 s (−0.01 to 0.01) alongside the main count, which stays 0.37 s. This null result is the cleanest check on race-phase or pack confounding.
  - **The car's own count two laps later:** 0.01 s (−0.00 to 0.02), with the main count still 0.37 s. *Amended after the E-014 review:* this isn't a clean placebo. Its window starts when lap t+1 ends, so this lap's own time moves it. The far-ahead count is the valid check.
  - **LMGT3 cars just behind at the start of the lap:** 0.11 s (0.09 to 0.14) on their own, and 0.04 s (0.03 to 0.06) alongside the main count. The statistical review found this count tracks the previous lap's exposure, so it most likely picks up traffic carried over from the end of the last lap, not confounding.
  - **Other Hypercars within 2 s ahead at the start of the lap** (40% of laps): 0.31 s each (0.28 to 0.35). With them in the model, the LMGT3 figure stays 0.36 s.
- **A statistical review** (the `statistical-reviewer` agent) tried and failed to show leakage from the lap's own outcome, a clock misalignment, faulty fixed effects or selection through pit stops. It found the window dependence and some wording that read as a per-car cost. Both are fixed above.

**What it doesn't show:**

- **No overtakes and no location.** "Expected to catch" is inferred from line crossings and the class pace gap. Some cars in the window won't be caught, and some caught from beyond it are counted as zero, which is why the per-car figure moves with the window. Where on the lap time is lost isn't observed.
- **Uncontrolled causes remain.** Drivers push or save for reasons tied to race position. The flag column only records the flag at the line, so local yellows are missed. Hypercar fights more than 2 s apart and a drying track aren't modelled.
- **The exclusions differ by exposure level.** In the review's count, laps with no cars to catch were more often slow (16% against about 11%), under caution or just after one. The loose-rule run limits the slow-lap part of this, but the caution exclusions are selective in a way not tested.
- **The intervals assume the 18 races are exchangeable.** They share 7 circuits and mostly the same cars and drivers, which the bootstrap doesn't resample. A t-interval on the 7 circuit means is wider (0.29 to 0.45), as reported by the review, but still well above zero.
- **The window uses whole-race medians,** including the Hypercar's own laps. That's harmless for a description, since it's constant within a race and fixed windows agree. A team doesn't have it at lap t, so it can't go into the simulator as it is.
- **Hypercars only, outside Le Mans,** and not yet tested on held-out races (fit 2024 to 2025, test 2026) as a simulator input would need.

---

## E-014: Does the traffic association hold the other way round, with a past-only window, and from one season to the next?

*2026-10-24 · complete. The plan was written before any of these outcomes was computed.*

Three questions that follow from E-013, all on the same 18 races outside Le Mans and with the same within-stint design (D-022).

**1. The other direction.** For an LMGT3 lap, count the Hypercars that cross the line in the W seconds *after* the GT3 begins its lap, leaving out pit-lane crossings. Those Hypercars are less than W behind on the road and should catch it before the lap ends. Same comparison, intervals and caps as E-013. Placebos, fixed now:
- Hypercars 2W to 3W behind, too far back to catch it this lap.
- Hypercars in the W seconds *ahead*, which have just lapped it.
- The car's own count two laps later.

*Expected:* positive, and smaller than the Hypercar figure per car. A GT3 being lapped mostly gives up the line for a moment. That's a guess, not a measurement.

**2. A past-only window.** E-013's W came from whole-race medians, which a team doesn't have at lap t. Here W at each lap is the gap between the class medians over usable laps that *ended before that lap began*. A lap gets no window until each class has at least 20 such laps. Rerun the Hypercar estimate and the GT3 estimate with it.

*Expected:* close to the whole-race figures, because class pace is fairly stable through a race.

**3. From 2024 to 2025 onto 2026.**
- Fit the per-car figure on the 14 races from 2024 and 2025, using the whole-race window as in E-013, then apply it unchanged to the 4 races from 2026 (COTA, Imola, São Paulo and Spa).
- Report the 2026 estimate on its own alongside the 2024 to 2025 one, and how much of the within-stint variance in 2026 lap times the 2024 to 2025 figure explains, against a zero-traffic baseline.
- Do it for both directions.

**This is not a clean holdout.** The 2026 races were already part of E-013, and I've seen the race-by-race slopes there. Nothing was tuned on them, since the design was fixed before E-013 ran, but the honest name for this is a check of stability over time. Four test races is also very few, so the 2026 figure gets race-by-race numbers, not just an interval.

**Found** (run `20261024T112047Z`, `python scripts/run_traffic_followup.py`, output in `reports/outputs/`, which stays local). As in E-013, every figure is a within-stint association with an inferred exposure, not a measured cost per pass. Drivers pushing or saving, local yellows and same-class fights aren't controlled. The intervals treat the 18 races as exchangeable, though they share 7 circuits and mostly the same cars.

**1. GT3 laps with Hypercars close behind.** 18 races, 322 LMGT3 car entries, 108 drivers, 2,300 stints and 46,442 laps. "Close behind" means within the race's pace gap W behind on the road at the start of the GT3's lap.

| Hypercars within W behind at lap start | Laps | Difference from 0 | 95% interval (races resampled) |
|---|---:|---:|---:|
| 0 (reference) | 13,528 | | |
| 1 | 10,809 | 0.20 s | 0.16 to 0.24 |
| 2 | 9,155 | 0.35 s | 0.30 to 0.41 |
| 3 | 5,996 | 0.48 s | 0.41 to 0.57 |
| 4 or more (mean 5.4) | 6,954 | 0.88 s | 0.77 to 1.00 |
| Per car (capped at 6) | 46,442 | 0.18 s | 0.16 to 0.20 |

- **Positive at all 18 races,** from 0.11 s (Fuji 2024) to 0.36 s (COTA 2025).
- **At a fixed window, it's about half the Hypercar figure** (a ratio of 0.47 to 0.57 across windows). Each figure on its own moves with the window: 0.23 s per car at 5 s down to 0.12 s at 20 s. The one-car contrast is 0.18 to 0.22 s across windows.
- **Can the lap's own outcome create this count?** Not directly. The Hypercars counted cross the line after the GT3 has started its lap, so nothing it does on that lap moves those crossings. An indirect route through earlier laps was checked by adding the previous lap's residual (added after the review): the figure stays 0.17 s (0.15 to 0.20) on the 43,232 laps that have one.
- **Placebo: Hypercars 2W to 3W behind,** too far back to arrive this lap. −0.01 s (−0.017 to −0.001), with the main figure at 0.18 s.
  - That's close to zero but not quite, and nothing here explains the small negative value. It doesn't show which way any bias in the main count runs.
  - The planned "own count two laps later" placebo turned out to be invalid, because its window depends on this lap's time. It's left out. It was nearly the same quantity anyway, correlating 0.83 with the far count.
- **Hypercars within W ahead at lap start** (just gone past): 0.02 s (0.01 to 0.03), a small carry-over like E-013's.
- **Other GT3 cars within 2 s ahead** (36% of laps), added after the review: 0.29 s each (0.26 to 0.33). With them in the model, the Hypercar figure stays 0.18 s.

**2. A past-only window.** At each lap, W comes from laps finished before it began, with at least 20 per class and no use of the slow-lap flag, which uses the whole race. Its median across laps is 12.3 s (interquartile range 10.6 to 13.4 s).

| Direction | Whole-race window | Past-only window | Laps with a past-only window |
|---|---:|---:|---:|
| Hypercar, GT3 cars ahead | 0.37 s (0.33 to 0.41) | 0.36 s (0.32 to 0.40) | 54,140 of 55,036 |
| GT3, Hypercars behind | 0.18 s (0.16 to 0.20) | 0.17 s (0.15 to 0.20) | 45,827 of 46,442 |

- **The whole-race window's look-ahead doesn't change the figure.** The two columns cover slightly different laps, because the past-only one drops the early ones.
- **Only the window is past-only.** The GT3 count uses crossings up to about 12 s into the lap, and the slow-lap rule and the stint line use later laps. The simulator will need gaps on the road at the decision point, not this feature as it stands.

**3. 2024 to 2025 against 2026** (14 races to fit, 4 to compare). Each 2026 interval is a t-interval over the four race slopes, because a bootstrap over 4 races has only 35 distinct samples and comes out too narrow (0.34 to 0.48 against the t-interval's 0.27 to 0.55, for Hypercars).

| Direction | Fitted on 2024 to 2025 | 2026 | 2026 race by race |
|---|---:|---:|---|
| Hypercar, GT3 cars ahead | 0.36 s (0.31 to 0.40) | 0.40 s (0.27 to 0.55) | COTA 0.39, Imola 0.38, São Paulo 0.33, Spa 0.54 |
| GT3, Hypercars behind | 0.18 s (0.15 to 0.20) | 0.19 s (0.12 to 0.27) | COTA 0.20, Imola 0.18, São Paulo 0.14, Spa 0.26 |

- **The 2026 slopes sit close to the 2024 to 2025 ones,** and the same holds with the past-only window (Hypercar 0.35 against 0.39) and with the loose slow-lap rule (0.36 against 0.39). Overlapping intervals aren't a test that the slopes are equal.
- **Within-stint variance accounted for depends heavily on the filter.** On 2026 Hypercar laps it's 42.5% with the standard slow-lap rule, 24.4% with the loose rule and 46.1% with the past-only window (17.6%, 7.6% and 19.5% for GT3). It barely changes for any slope near the best one, so it says nothing about transfer, and I don't use it as evidence for that.
- **A stability check at circuits already seen, not a holdout.**
  - The 2026 races were part of E-013.
  - Their window and slow-lap rule use 2026's own whole-race medians, so 2026 lap times shape the 2026 exposure. The past-only window avoids that and gives the same answer.
  - All four 2026 circuits appear in 2024 to 2025 too, with mostly the same cars and drivers. This shows the figure is steady over time at known tracks, not that it transfers to a new circuit.

**What it doesn't show:**

- **No passes, no location, no cause.** The same limits as E-013 apply.
- **The GT3 figure can't separate time lost to being passed from any change in driving with faster cars around.**
- **Still outside Le Mans, still not hierarchical.** The one valid GT3 placebo sits just below zero.

---

## E-015: At Le Mans, how does lap time move with each other class counted?

*2026-10-24 · complete. The plan was written before any outcome was computed.*

**Question:** Le Mans is the only three-class race (Hypercar, LMP2, LMGT3). LMP2 sits in the middle: it catches GT3 cars and is caught by Hypercars. For each class, how does lap time change with the count of each other class within that pair's window at the start of the lap?

**Exposure:** the same as D-022 and E-014, but one count per other class, each with its own window. The window for a pair of classes is that race's pace gap between them (median usable lap of the slower minus the faster):
- a slower class is counted ahead, within the pair's window;
- a faster class is counted behind, within it.

So a Hypercar lap gets an LMP2 count and a GT3 count, an LMP2 lap gets a GT3 count ahead and a Hypercar count behind, and a GT3 lap gets an LMP2 count and a Hypercar count, both behind.

**Comparison:** for each class, one within-stint fit with both counts at once (capped at 6), with the same lap filter and stint line as E-013. A placebo per pair, fixed now: the same class 2W to 3W away on the same side, fitted alongside.

**Data:** Le Mans 2024, 2025 and 2026. 2024 had rain and fewer usable laps.

**Uncertainty:** 3 races. A bootstrap over 3 races is meaningless, so I report each race's coefficients and a t-interval over the three (2 degrees of freedom, which makes it wide). Any figure from this is three observations.

**Expected (a guess):** every coefficient positive. The faster car loses more than the slower one in each pair, as in E-014. Per-car figures aren't comparable with the other 18 races, because the windows are about 10 to 29 s here against about 12 s there.

**Not in this entry:** the 15 intermediate timing points at Le Mans 2025 and 2026, which could locate traffic within a lap. That's a separate sub-study (D-009).

**Found** (run `20261024T114313Z`, `python scripts/run_traffic_le_mans.py`). Each figure is the within-stint lap-time increase associated with one more car counted, not a cost per pass. Intervals resample car entries (inside a race, or pooled across races). The planned t-interval over 3 races was dropped as a headline, because with 2 degrees of freedom it can come out narrower than a single race's own interval when three values happen to agree.

**The plan was incomplete, and fixing it changed the result.** E-013 checked a loose slow-lap rule, but this entry didn't plan that check until the statistical review ran it. It matters at Le Mans because of 2024:
- **52% of 2024 laps are flagged slow,** against 16 to 17% in 2025 and 2026.
- **The rain flag catches only 4.9% of 2024 laps.** Damp and drying running gets removed by cutting slow laps, which picks out the fastest half of the laps by their outcome.
- **17% of 2024 laps are under caution.**

So 2024 is reported separately, and the result rests on 2025 and 2026, two races. A second gap: **slow zones aren't in the flag column** (it only holds GF, SF, FCY and FF), so a Le Mans slow zone shows up as a green lap. The standard rule only removes slow zones that cost more than about 7% of a lap.

| Car | Count of | Window | Standard rule, 2025 and 2026 (pooled) | 2025 / 2026 | Loose rule, 2025 and 2026 |
|---|---|---:|---:|---|---:|
| Hypercar | LMP2 ahead | about 10 s | 0.28 s (0.25 to 0.32) | 0.31 / 0.26 | 0.26 s (0.19 to 0.33) |
| Hypercar | GT3 ahead | about 29 s | 0.35 s (0.34 to 0.37) | 0.33 / 0.37 | 0.37 s (0.33 to 0.41) |
| LMP2 | Hypercar behind | about 10 s | 0.22 s (0.19 to 0.26) | 0.23 / 0.21 | 0.14 s (0.05 to 0.22) |
| LMP2 | GT3 ahead | about 19 s | 0.42 s (0.40 to 0.43) | 0.40 / 0.43 | 0.43 s (0.35 to 0.51) |
| GT3 | LMP2 behind | about 19 s | 0.14 s (0.13 to 0.16) | 0.15 / 0.14 | 0.13 s (0.03 to 0.24) |
| GT3 | Hypercar behind | about 29 s | 0.08 s (0.06 to 0.09) | 0.07 / 0.09 | 0.07 s (0.01 to 0.13) |

- **Holds under both rules:**
  - Hypercar with GT3 ahead, at 0.35 to 0.37 s;
  - Hypercar with LMP2 ahead, at 0.26 to 0.28 s;
  - LMP2 with GT3 ahead, at 0.42 to 0.43 s;
  - GT3 with LMP2 behind, at 0.13 to 0.14 s, though wide under the loose rule.
- **Depends on the rule:** LMP2 with Hypercars behind falls from 0.22 to 0.14 s. GT3 with Hypercars behind is small either way (0.07 to 0.08 s).
- **The faster car's figure is larger in each pair, matching the guess written down in the plan.** It holds in every race and under both rules. The closest pair is Hypercar against LMP2: the paired difference across the three races is 0.06 s (0.01 to 0.10, from the review). That's an ordering, not a mechanism.
- **Placebos (the same class 2W to 3W away):**
  - **Standard rule:** all six pooled placebos are within ±0.02 s, and only one interval misses zero (Hypercar with far GT3 cars, −0.015 s).
  - **Loose rule:** most come out between −0.03 and −0.11 s, and three of the six intervals exclude zero.
  - So the extra slow laps the loose rule keeps bring in a pattern this design doesn't explain. Neither rule gives a clean answer for the figures that disagree.
- **2024 on its own** (standard rule) gives similar numbers: Hypercar 0.25 and 0.35 s, LMP2 0.20 and 0.51 s, GT3 0.13 and 0.00 s. Under the loose rule it swings to between −0.17 and +0.49 s, with intervals up to ±0.3 s.
- **Checks the review ran that changed nothing:** the previous lap's residual, same-class cars within 2 s, and overlap between a GT3 car's two "behind" counts. After detrending within the stint, those two counts correlate at −0.03.

**What it doesn't show:**

- **Two usable races.** Le Mans figures should be treated as two observations per pair, with 2024 as a warning about wet and drying running.
- **Not comparable with the other 18 races.** The windows here are 10 to 29 s, and E-014 showed the per-car figure falls as the window widens. So these numbers aren't set against the 0.37 and 0.18 s found elsewhere.
- **Slow zones and drying track aren't identified** in this data as processed, and they bias whichever laps are kept.
- **The review flagged two things not done here:** dropping more than one lap after a caution, which lowered 5 of 6 figures slightly in its check, and night against day, which gave 0.35 against 0.24 s for Hypercar with LMP2 ahead, again in its check.
- **The windows use whole-race medians**, as in E-013 (see E-014 for the past-only version). Every earlier limit still applies: no passes, no location, no cause, and driving choices aren't controlled.

---

## E-016: Can field-wide slow periods be caught when the rain sensor misses them?

*2026-10-24 · complete*

**Question:** E-015 found that half the 2024 Le Mans laps were flagged slow while the rain sensor read zero, and that Le Mans slow zones never appear in the flag column. Can timing data alone mark those periods, without saying what caused them?

**Looked at first:** Le Mans 2024 hour by hour, using green, non-pit laps. Whole hours (6, 8, 16, 17, 22 and 23) had the field's median lap 9 to 14% above the dry reference, with `RAIN` at 0 for almost all of them. The sensor caught part of hour 11 and part of hour 23.

**Method:** for each lap, `field_pace_ratio` is the median, over its class's green non-pit laps that ended within ±5 minutes, of lap time divided by the class's dry median at that race. NaN with fewer than 10 such laps. A lap is `is_field_slow` above 1.04. The flag joins the clean-lap rules (D-025).

**Found:**

| `field_pace_ratio` of green non-pit laps | Share |
|---|---:|
| Up to 1.01 | 88.5% |
| 1.01 to 1.02 | 6.8% |
| 1.02 to 1.03 | 0.7% |
| 1.03 to 1.05 | 0.4% |
| 1.05 to 1.10 | 1.5% |
| Over 1.10 | 2.1% |

- **The split is clean.** Almost nothing sits between 1.03 and 1.05, so the 1.04 cut-off is a choice inside a gap, not a fine-tuned threshold. It was set from this distribution, not from any traffic result.
- **Where it fires:**
  - **Imola 2024:** 16% of green laps, where the rain sensor caught 0.7%.
  - **Le Mans 2024:** 34%.
  - **COTA 2025:** 12%, where the rain sensor already caught most of it.
  - **Smaller pockets** of 1 to 2.5% at COTA 2026, Imola 2026 and Le Mans 2025 and 2026, which fit slow zones or local yellows.
- **It removes 695 laps from the clean set** (138,884 down to 138,189). Its 7,703 flagged laps were mostly already out through the slow-lap rule.
- **Effect on the traffic results** (rerun with the new rule):
  - **The 18 races barely move:** Hypercar 0.37 s (0.33 to 0.41) and GT3 0.18 s (0.16 to 0.20). The far-ahead placebo stays at 0.00 s.
  - **Le Mans, loose slow-lap rule, 2025 and 2026:** placebo intervals that miss zero drop from 3 of 6 to 1 of 6, now between −0.04 and +0.03 s. Most of E-015's loose-rule placebo failure came from these periods.
  - **LMP2 with Hypercars behind** moves from 0.14 to 0.16 s under the loose rule. That's still below the 0.22 s under the standard rule, so it stays the fragile pair.
  - The E-013 to E-015 entries keep the numbers from before this flag existed. Their runs are reproducible from the commits before D-025.

**What it doesn't show:**

- **It can't name the cause.** Drying track, slow zones, local yellows and fog all look the same here.
- **It misses slow zones that cost little.** One sector under a slow zone may not move the field's median lap by 4%.
- **It uses laps after the one being flagged,** so it's a cleaning rule for describing races, not something a team knows at lap t.
- **The slow-lap rule's reference is still the race median including these periods,** so at a race like Imola 2024 that reference is a little slow. Not changed here.
