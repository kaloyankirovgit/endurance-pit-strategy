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

