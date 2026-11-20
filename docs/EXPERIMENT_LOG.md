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

---

## E-017: Does the hybrid beat BM25 on vague, engineer-style questions?

*2026-10-26 · pre-registered before any retriever ran on these questions*

**Question:** E-011's questions were written after reading the clauses, which favours BM25. On questions written without the regulations to hand, does the hybrid (BM25 + embeddings, reciprocal rank fusion) retrieve the answering clause more often?

**Question set:** `questions_vague.json`. Kaloyan wrote 30 questions without reading the regulations. Claude labelled them from the 2026 clause text before any retriever was run on them:

- 18 answerable: 12 in real-world wording and 6 in sim-racing wording whose real-world rule is in the corpus;
- 6 that the corpus doesn't answer (pit windows, blue flags, track-limit warning counts, engine maps), kept for refusal tests;
- 6 about game behaviour or strategy, moved to `routing_vague.json` as routing cases.

**Decision rule, fixed before the run:**

- Primary measure: top-5 hit, question by question, hybrid against BM25, answerable questions only, season filter on.
- The hybrid becomes the default if both hold:
  1. on the vague set, it wins more questions than it loses;
  2. pooled over the held-out set (E-011) and the vague set, a two-sided exact sign test on the questions where they differ gives p < 0.05.
- Otherwise BM25 stays the default and the hybrid stays a candidate (D-020).
- Embeddings alone are reported but can't become the default on this run.
- Real and sim wording are reported separately, as description only.

**Labels:** drafted by Claude and not yet spot-checked by Kaloyan. Any label changed after the run is logged here, and the run repeated.

**Found** (run `20261026T125420Z`; the original and held-out rows reproduce E-011 exactly):

| Set | Retriever | recall@1 | recall@3 | recall@5 |
|---|---|---:|---:|---:|
| Vague (18) | BM25 | 4 | 9 | 9 |
| Vague (18) | Embeddings | 2 | 7 | 13 |
| Vague (18) | Hybrid | 7 | 9 | 11 |

| Hybrid against BM25, top 5 | Hybrid wins | BM25 wins |
|---|---:|---:|
| Vague | 3 | 1 |
| Held-out (E-011) | 2 | 0 |
| Pooled | 5 | 1 |

- **By the rule, BM25 stays the default.** Condition 1 holds (3 against 1). Condition 2 fails: 5 against 1 gives p = 0.22. That means the hybrid was not shown better, not that the two are equal. With 6 disagreements the test could only pass at 6 to 0.
- **BM25 found the clause in the top 5 for 9 of 18 vague questions, against 27 of 30 held-out.** The sets also differ in author, labeller, how many articles count as gold (6 of 18 vague questions have several, against none held-out) and topic: 12.2.2 is gold for 5 of 18. So the drop can't be put down to wording alone, and those 5 questions move together, so the effective n is below 18.
- **Embeddings alone hit more often at rank 5 (13 of 18) but less often at ranks 1 and 3** (2 and 7). All 5 of its wins over BM25 sit at ranks 3 to 5, and 3 of them have several gold articles. The 10-of-12 on real-wording questions is one of about 27 slices looked at after the results, so it's a question for a fresh set, not a finding.
- **Long chunks:** 12.2.2 is 727 tokens and the model reads the first 512. One embeddings miss (v23) has its answer past that limit; another (v07) does not, so dilution of a long chunk fits as well as truncation. Embedding the sub-clauses separately would test this without new questions.
- **Missed by all three:** v07 (tyres and fuel at once), v16 (track-limit warnings), v29 (out of fuel before pit entry).
- **Sensitivity:** with the two partial questions (v04, v16) counted as unanswerable, recall@5 is BM25 9, embeddings 12, hybrid 11 out of 16, and the hybrid's 3 against 1 is unchanged.

**What it doesn't show:**

- **Every label is provisional.** One labeller (Claude), not yet checked. Kaloyan's check happens after the results exist, so the rules for changing a label are fixed here first: a label changes only if the gold article doesn't answer the question or another article answers it better. He checks with the retriever ranks hidden. Results are reported before and after any change, under the same decision rule.
- **The pooled test includes the held-out 2 to 0, part of the pattern that suggested this test (D-020).** That tilts it towards a pass, and it still failed. A future rule should be tested on a set that played no part in proposing it.
- **18 answerable questions from one author.** One question moves recall@5 by about 6 points.

**Reproducing the test:** `sign_test` and `compare_hits` in `rag/evaluate.py` (unit-tested). The comparison script prints every pairing and the E-017 rule. The first p-values were worked out by hand, and the code reproduces them: 5 against 0 gives 0.0625 (E-011), and 5 against 1 gives 0.219.

**Label check (2026-10-26, after the run):** Kaloyan checked all 24 labels against the clause text with the retriever ranks hidden, and agreed with every one. v04 and v16 stay answerable but partial, as labelled. No label changed, so the results above stand without a rerun. He saw Claude's notes while checking, so this confirms the labels rather than being an independent second labelling.

**Reviewed by** the statistical-reviewer agent before reporting. It kept the decision and corrected the wording of the recall-drop and embedding claims, and the truncation explanation.

---

## E-018: Do the answers refuse what the regulations don't cover, on vague questions?

*2026-10-26 · complete*

**Question:** E-010's unanswerable questions were all sent away by the router, so the answerer's own refusal was never tested. On the E-017 vague set, which has real racing questions the regulations don't answer, does anything unsupported reach the user?

**Method:** `python scripts/run_answer_eval.py --questions questions_vague.json --routing routing_vague.json`. All 24 questions and the 6 routing cases, 3 runs each, through the router, BM25 retrieval (top 5), the answer prompt and the code checker. Key facts for 7 answerable questions were taken from the clause text before the run. Model: `claude-opus-5-5`. Run `20261026T135254Z`, 230 s.

**Found:**

- **In-scope refusal:** 5 of the 6 unanswerable questions reached the answer step (4 real-worded, 1 sim-worded), and the answerer declined every one. Each question ran 3 times with the same retrieval and the same outcome every time, so the effective n is 5, not 15. With 5 of 5, a one-sided 95% lower bound on the refusal rate is about 55%. The engine-map question (v19) was routed away all 3 times.
- **Not refusing everything:** of the 18 runs where retrieval found the answering clause (6 questions), 13 were answered citing it. This is the contrast that separates "refuses what it can't support" from "refuses everything". When retrieval missed, the answerer declined 25 of 26 runs that reached it. So the data can't tell refusing because the corpus lacks the rule apart from refusing because retrieval missed.
- **The checker's two rejections were false positives.** Both blocked answers were correct:
  - v12 derived "61 km/h" from the clause's round-up rule;
  - v10 named 14.6.5 only to say that the extracts didn't include it.
  
  The checker caught no fabricated number in this run.
- **Retrieval misses (12 questions, 36 runs):** 25 declined and 10 routed away, all sim-worded (v23, v26, v30, and v27 once). One answered from a nearby clause: v15 cited the VSC article (14.7.1), which has the same "car with an obvious problem" exception, and said the extracts didn't cover local yellows.
- **Shown answers:** Claude read all 16 (14 from 6 vague questions, 2 from routing case vr18), and none contradicted its cited clause.
- **Routing on the game and strategy questions:** 13 of 18 runs matched the label. The 5 that didn't went to regulation lookup:
  - vr05 (disconnected driver, 2 of 3), which has a real rule underneath (minimum driving time);
  - vr18 (curb exploit, 3 of 3), which answered or declined from 9.1.2 with a citation.
  
  The labels were Claude's and weren't checked, so they stay unchanged after the run, and 13 of 18 isn't a routing error rate.

**What it doesn't show:**

- **Refusal explanations are shown but not checked.** `check_answer` returns no problems for an unsupported answer, and `refusal_reason` goes to the user as written. Some refusals paraphrase clauses (v24 restates parts of 6.5.7), and those paraphrases are never verified. This is a gap in the guardrail, and the next fix for Layer 6.
- **Key facts are weak.** They were added in the same uncommitted change as the run, so "set before the run" can't be audited. Checks like "clos", "overtak" and "engine" plus "off" would pass many wrong answers. No wrong facts were set. Only 4 questions (10 runs) had a key-fact check that applied, and all 10 passed.
- **The system answered 14 of 54 answerable runs.** Refusal is the main way it stays correct here, and better retrieval would turn refusals into answers.
- **24 questions from one author.**

**Reviewed by** the statistical-reviewer agent. It corrected the effective n, retired a claim that the checker caught untraceable numbers (both rejections were false positives), and found that refusal text is never checked.

---

## E-019: On fresh questions, does the hybrid win more often than it loses against BM25?

*2026-11-09 · pre-registered and committed before any of its questions were written · run the same day*

**Question:** which retriever should be the default? E-017's rule was not met. This is a second test under a looser rule, chosen after that failure (D-027). It can't show the hybrid is better.

**Fixed before the questions exist:**

- **Retrievers:** BM25 and the hybrid as in E-011 and E-017: k1 = 1.5, b = 0.75, `BAAI/bge-small-en-v1.5` (which resolves to `Qdrant/bge-small-en-v1.5-onnx-Q`, snapshot `aa8f8b06`), reciprocal rank fusion with constant 60, depth 50 and equal weights, `fastembed` 0.9.0. Nothing tuned. The chunk file is SHA-256 `6e12122e`. The sub-clause embedding idea is not applied. The run first reproduces the E-017 rows, and stops if they differ.
- **Questions:** `evals/regulations/questions_fresh.json`, 50 written with the regulations closed: 25 in real race-engineer wording and 25 in sim-racer wording. At least half come from someone who hasn't seen this project, if that can be arranged. Otherwise a topic list is committed first. Near-duplicates of the 78 earlier answerable questions are rejected.
- **Labels:** the answering 2026 articles are drafted by Claude from the clause text, reading the regulations by section and not by running a retriever or keyword search, with the transcript saved. Kaloyan checks every label before any run, without Claude's notes. The questions and labels are committed before any run.
- **Frozen labels decide.** A later change needs E-017's grounds, is made with ranks hidden, and is reported only as sensitivity. Any gold article in the top 5 counts as a hit. Partial questions count as answerable, as in E-017.
- **Size:** at least 30 answerable questions, and at most 2 per gold article. If there are fewer, more are written before any run.
- **Primary measure:** top-5 hit, question by question, hybrid against BM25, answerable questions only, season filter on.

**Amendment, 2026-11-09, committed before any question was generated.** Kaloyan chose to have the questions written by a blind model instead of people, to get to Layer 3 sooner. It changes who writes the questions and nothing else in this entry:

- **Author:** the racer agent (`rag/racer_agent.py`), run headless from an empty folder with no tools and without user, project or MCP settings. A canary run with the same isolation is asked what it can see, and the script stops if it can quote the project.
- **Personas, replacing the real and sim split:** 4 people competing (2 real drivers, 2 sim racers), `wording: racer`, and 4 people watching, `wording: fan`. Each writes 10 questions in one independent run.
- **Selection, fixed by code:** within each group the questions are taken one per persona in turn, in the order written. A question with content-word Jaccard overlap of at least 0.6 with one of the 78 earlier answerable questions, or with one already kept, is dropped. The first 25 kept per group are the main set. Later ones are the reserve, and are used in the same order only to reach 30 answerable or to replace a question over the 2-per-article cap.
- **Every question it wrote is committed,** dropped ones included, in `evals/regulations/racer_agent/`.
- **Limits this adds:** a model isn't an outside person. It may know WEC rules from training, and all 80 questions come from one model, so the variety may be narrower than 8 people would give. The prompt steers it to questions about the rules, because a fan left alone asks mostly things the rulebook can't answer. The result says what this model's questions show, and doesn't stand in for real users.

**Question set as built, 2026-11-09 (run `20261109T204440Z`, labels drafted, not yet checked, no retriever run):**

- The agent wrote 80 questions. 3 were near-duplicates. Of the other 77, 43 were kept: 22 racer and 21 fan, 33 answerable and 10 not.
- **That's 43 questions, not the 50 planned.** The questions cluster on a few topics (driving time, pitting under yellow, tyres while refuelling), so the 2-per-article cap ran through the reserve. The size rule of at least 30 answerable is met, so no more were written.
- The amendment didn't say how the cap applies across the two groups. It was applied with racer and fan alternating by position, main set first, and a question is dropped if any of its gold articles is already at 2. This was chosen after the labels were drafted and before any retriever ran. Its effect is UNKNOWN: 4 of the 5 questions that differ touch an article at the cap, and losing 2 of them would have made the outcome inconclusive. The draft labels for all 77 candidates are in `evals/regulations/racer_agent/` so the cap can be re-applied, but only the 43 kept were checked by Kaloyan.
- Labels came from reading 6.2, 6.5, 7.2, 7.4, 9.1, 12, 13, 14 and 15.1 of the 2026 text in full, plus 1.4.1, 3.1.1, 4.1.3, 4.3.1, 4.3.2, 6.1, 6.3, 6.4.6, 6.6, 9.2.1 and Appendix 4 (1.4.1, 6.3.1 and 6.3.2 only to their first 1,800 characters). "Not answered" therefore means not in those parts. Appendix 4 lost its table's first column in extraction, so it couldn't be used as a source.
- **Label check:** Kaloyan confirmed on 2026-11-09 that he checked every label on the sheet and changed none. The sheet showed the question and the article text, without Claude's notes. The tick boxes on it were left blank, so the record of the check is that statement. The questions and labels were already committed (`4da29f0`).

**Rule:**

| Outcome | Decision |
|---|---|
| Fewer than 4 questions differ | Inconclusive. BM25 stays, and the hybrid stays a candidate |
| At least 4 differ and the hybrid wins more than it loses | The hybrid becomes the default |
| At least 4 differ and the hybrid doesn't win more | BM25 stays and this configuration is dropped. Any changed retriever is a new candidate needing new questions |

**What the rule can and can't do.** It's a decision rule, not a test of superiority. The number of disagreements is random, so the table gives the overall chance of adoption for 30 answerable questions, at the disagreement rates seen so far (12.5% pooled, 22% on the vague set):

| Hybrid's true share of disagreements won | 20% | 30% | 50% | 70% | 83% |
|---|---:|---:|---:|---:|---:|
| Adopted, 12.5% disagreement (under 4 differ: 47%) | 2% | 6% | 21% | 40% | 49% |
| Adopted, 22% disagreement (under 4 differ: 8%) | 2% | 9% | 39% | 75% | 88% |
| Net recall@5 change at 12.5% / 22%, points | −7.5 / −13 | −5 / −9 | 0 | +5 / +9 | +8 / +15 |

Under a flat prior updated on E-017's direction, adoption is about 35% to 76% across those rates and the 5-1 or 3-1 evidence. So the outcome isn't settled in advance, and at the lower rate it will often be inconclusive.

**Reported either way:** wins and losses at k = 1, 3 and 5, by question and by distinct article, recall@k for BM25, the hybrid and embeddings alone, and the exact sign-test p as description. Real and sim wording are shown separately, as description only. No result from this run is worded as "the hybrid is better".

**If the hybrid is adopted:** the BM25 answer figures (E-010, E-012, E-018) don't carry over. The answer eval runs first on the fresh set. Reruns on the E-017 vague set are partly in-sample for the retriever choice and are labelled that way.

**Known limits:**

- Kaloyan prefers the hybrid, knows BM25's misses, has seen E-017's questions and read the clause text for 24 labels on 2026-10-26. Wording overlap with the clause text is the thing that separates the retrievers, which is why outside authors matter here.
- The labels again come from Claude.
- "No keyword search while labelling" can only be checked from the saved transcript.
- Reviewed by the statistical-reviewer agent before being fixed. It rejected the first version of this rule (wins at least equal to losses, ties to the hybrid).

**Found** (run `20261109T210117Z`). The chunk hash, `fastembed` version and model snapshot were checked in code, and every question-level rank from the E-017 rerun (`20261026T144012Z`) reproduced.

| 33 answerable questions | recall@1 | recall@3 | recall@5 |
|---|---:|---:|---:|
| BM25 | 15 | 17 | 24 |
| Embeddings | 16 | 22 | 26 |
| Hybrid | 18 | 24 | 27 |

| Hybrid against BM25 | Hybrid wins | BM25 wins | Exact sign test p (description only) |
|---|---:|---:|---:|
| Top 1 | 6 | 3 | 0.51 |
| Top 3 | 8 | 1 | 0.039 |
| **Top 5 (the primary measure)** | **4** | **1** | **0.375** |

- **By the rule, the hybrid becomes the default.** 5 questions differ, which is at least 4, and the hybrid wins more than it loses. By distinct gold set the split is 6-3, 8-1 and 4-1 at k = 1, 3 and 5. By individual gold article named on those questions it is 9-3, 11-1 and 5-2.
- **That's a decision, not a finding that the hybrid is better.** The rule was chosen after E-017 failed, and 4 to 1 on 33 questions is compatible with no difference (p = 0.375). Recall@5 moved by 3 questions of 33.
- **The top-3 figure isn't a result to quote.** It's one of three cut-offs, it wasn't the primary measure, and p = 0.039 would not survive correction for looking at three.
- **By who is asking (description only):** racer 16 of 18 for the hybrid against 14 of 18 for BM25 (2 wins, 0 losses). Fan 11 of 15 against 10 of 15 (2 wins, 1 loss). Embeddings alone found 12 of 15 fan questions, one more than the hybrid. Neither subset can carry a claim.
- **The 5 questions that differ:** the hybrid hits f05 (13.2.3, rank 3), f15 (6.5.4, rank 4), f32 (12.3.1 only, rank 2) and f39 (6.4.6, rank 5). BM25 hits f04 (12.3.2 only, rank 5).
- **The result leans on the questions with several gold articles.** 11 of the 33 have several, and any one in the top 5 counts as a hit. On the 22 with a single gold article the split is 3 to 0, which the rule would call inconclusive. Requiring every gold article in the top 5 gives 6 to 0. So multi-gold labels don't favour the hybrid, but passing the 4-question gate depends on them.
- **What this doesn't show:** every question came from one model, and Claude drafted the labels. Kaloyan checked them without notes, but with BM25's misses in mind from earlier work. The hybrid contains BM25, so this measures what adding embeddings changes, and it says nothing about real users or sim-racing wording alone.
- **Not applied yet.** `rag/answer.py` and the answer eval still use BM25. As fixed above, the E-010, E-012 and E-018 figures don't carry over, and the answer eval runs on the fresh set before the switch is made.

---

## E-020: How does pace change with stint age, what does a routine stop cost, and what predicts a race's pace?

*Written 2026-11-09, committed 2026-11-10 · pre-registered, with the code that runs it, before any Layer 3 quantity was computed · run 2026-11-10*

**Questions:** (A) what range of stint ages can the data support, (B) how does lap time change with laps since the last stop, by class, (C) how much time does a routine green-flag stop cost, by class and circuit, and (D) does practice or last season's race predict a race's clean pace better? The design comes from D-031. This entry fixes the definitions and decision rules. The code is `models/pace.py` and `scripts/run_layer3.py`.

**Who sees what:**

| Data | Role |
|---|---|
| 2024, 7 races outside Le Mans | Fitting, including every offset, support limit and reference |
| 2025, 7 races outside Le Mans | Checked once, after the fit is frozen |
| 2024 and 2025 Le Mans | Described apart, with a within-race slope and stop percentiles for each, and never used to fit or tune anything, because 2024 is compromised (E-015) |
| 2024 and 2025 together | Refit after the check, to give the parameters the simulator uses. The age limits stay frozen on 2024, so no age untested on 2025 goes through. C isn't refitted, since a circuit then has two races |
| 2026, all 8 races | Sealed. The analysis loader raises an error on the 2026 season unless explicitly opened, and a test enforces it |

The runner has two stages. `--stage fit` reads 2024 only and writes the frozen parameters. `--stage check` refuses to run without that file. Neither overwrites its own output, so a rerun takes a deliberate amendment.

**What has already been seen.** This isn't a blind analysis:

- While planning, 2026 median `PIT_TIME_S` and stop counts by class were printed (D-031). That's a small look at the sealed year.
- 2024 and 2025 were seen in Layers 1 and 2: pit-column checks, per-event `PIT_TIME_S` medians, stint counts and clean-lap rates (E-003 to E-005). No stint-age effect, pit loss or practice comparison has been computed for any season.
- The traffic fits used within-stint trends from 2024, 2025 and 2026 only as nuisance terms, and those slopes were not reported.

**Outside evidence, read before this was fixed** (`docs/research/literature.md`). Excluding in-laps, out-laps and safety-car laps is common practice in the papers read, and they don't agree beyond that. Nothing read supports the 1.07 slow-lap ratio in particular, so it stays a choice (D-012) with the loose rule as its check. Three things changed this entry: a lap that is both an out-lap and an in-lap gets its own status (Fieni et al.), the warm-up lap is measured separately so the simulator can charge it (Santillana), and flagged-lap shares are reported by season, since a green-flag filter can remove more from one season than another (Joshi). Those searches found no open WEC study fitting stint age from timing data.

### What stint age measures

- **`stint_lap` is laps since the car last had a `PIT_TIME` entry (RECONSTRUCTED). It isn't tyre age, and refuelling isn't observed.** Teams carry tyres across stops, the timing doesn't record which stops changed them, and any `PIT_TIME` resets the count, including a penalty.
- **The fitted effect is one combined quantity (INFERRED):** fuel burn, tyre wear on an unknown mix of new and used tyres, and anything else that moves steadily with laps since a stop. Fuel and tyres are not separated (D-005), and no result is worded as tyre degradation.
- **A steady change in the track over the race can't be separated from stint age.** With one intercept per stint, age equals race time minus the stint's start time, so a linear race-time trend is not identified alongside it (the age-period-cohort problem). The track temperature check below is a partial control. A field-relative adjustment isn't used, because pit cycles are roughly synchronised and the field median would absorb part of the age effect.
- **What the fit is weighted towards.** Within-stint least squares weights a stint by its spread of ages, so long stints count for much more. The estimate is conditional on a stint having reached that age, and stint length is a choice teams make. The support rule limits extrapolation and doesn't remove that selection.
- **Caution laps count towards `stint_lap`** while adding far less fuel use and wear, and unevenly by race. The no-caution sensitivity below checks this.

### Part A: support, measured first

Laps are `is_usable_for_pace_model` (D-012, D-025), classes HYPERCAR and LMGT3, in stints with at least 5 such laps, not starting from a garage stop. Counts are reported by class and circuit in races, cars, drivers, stints and laps, with the share of laps excluded by each flag, per season.

**Support rule:** an age is supported for a class if at least 30 stints from at least 4 races have an analysis lap at that age in 2024. The limit is the highest age up to which every age from 3 is supported. Fits and scoring stop at it. The number of laps dropped by this rule is reported. Long ages come from cars that chose to run long, so the simulator can't extrapolate past the limit without saying so.

### Part B: the stint-age effect

All per class. The out-lap is excluded, so ages start at 2. **Stint lap 2 is treated as warm-up and left out of L, Q and C**, because one slow early lap tilts a straight line. It's reported as its own quantity: the median lap at age 2 minus the median at ages 3 to 7, per race, averaged equally over races.

| Name | Model | Role |
|---|---|---|
| F | No age effect | Null comparator |
| B | Median lap at each age minus the median at ages 3 to 7, per race, averaged equally over races, held flat past the support limit | Baseline, no stint intercepts |
| L | Within-stint least squares, lap time on age, ages 3 and above, one intercept per stint, fitted per race, then the equal-weight mean of the race slopes | **Primary** |
| Q | As L with age squared added | Is the shape curved |
| C | L, using the same circuit's 2024 race slope | Does the circuit matter. Partly a test of lap length, since slopes are in seconds |

- **Estimate:** seconds per lap of stint age, and the same slope as a percentage of that race's median clean lap, because races pool circuits of different lengths. Per class. Intervals are a 95% t-interval over the 7 race slopes and a percentile bootstrap of whole races (2,000 draws, seed 20261109). With 7 races the bootstrap runs narrow, so the t-interval is the headline, as in E-014.
- **Held-out test.** On 2025 stints with at least 10 analysis laps at age 3 or above, the first 5 of those laps are the anchor, for every model. Later laps up to the 2024 support limit are predicted: anchor mean, plus f(age), minus the mean of f over the anchor ages. The score is mean absolute error per race and class. Mean signed error is also reported, since strategy depends on accumulated time. The level comes from the stint's first laps and f from 2024 alone, but lap selection uses whole-race information (the slow-lap median and the field-slow window), and the 10-lap filter conditions on the future. So this test is retrospective and doesn't replay what was known at the time.
- **Decision ladder.** Models are compared with the current holder in a fixed order, for each class. A challenger takes over only if the t-interval (6 degrees of freedom) on the paired difference in race-level error excludes zero in its favour.
  1. F holds to start.
  2. B challenges the holder.
  3. L challenges the holder.
  4. Q and C each challenge L, and only if L holds. If both win, the one with lower mean error holds. If L doesn't hold, Q and C are shown as description only.

  That's up to 4 comparisons per class with no multiplicity adjustment, stated with the result.
- **If F holds,** the finding is that a stint-age effect was **not shown to be useful for prediction**, which doesn't mean the effect is zero. L's interval goes to the simulator as an ASSUMED sensitivity range. As a rough guide from a synthetic run with assumed noise (lap SD 0.6 s, autocorrelation 0.3, race-slope SD 0.01), L passes this rule 46% of the time at a true 0.02 s/lap and 97% at 0.04.
- **Coverage.** A 95% prediction interval for a new race's slope, 2024 mean ± t × SD × √(1 + 1/7), checked against 2025 race slopes, by class, in both units, with the interval's width alongside. Fewer than 6 of 7 inside for a class counts as under-coverage. That check can only detect a gross failure: with 7 races, 6 of 7 is expected about 96% of the time at true 95% and about 58% at true 80%.
- **Sensitivity (each one fixed now, each on 2024):** the loose slow-lap rule (1.25 × class median), because the standard rule may remove slow late-stint laps; including stint lap 2; dropping the last 2 analysis laps of a stint (possible saving before the stop); at least 10 analysis laps per stint; ages up to the class's 2024 median stint length (out-lap through in-lap, analysis stints only); stints with no caution lap (the finish flag, `FF`, doesn't count as one); within-stint track temperature added; the E-013 and E-014 traffic count added, with the window from 2024 only; another bootstrap seed.
- **What counts as unstable.** A sensitivity is unstable if its slope moves by more than the primary interval's half-width, or if the sign flips while the primary interval excludes zero. An unstable result is reported as the finding.

**Expected:** the sign is unknown, since fuel burn and wear pull in opposite directions. A negative slope isn't an error. Santillana reports that blended slopes are often negative in F1 and that an optimiser will exploit them to run impossibly long stints, so the simulator must respect the support limit.

### Part C: the routine green-flag stop

The unit is the pit event. `PIT_TIME_S` is read as time in the pit lane (the value is OBSERVED, its meaning INFERRED from its size in E-003, and no source names the timing lines). It isn't the time a stop costs.

- **Pit loss:** in-lap time + out-lap time − 2 × reference pace. The arithmetic is RECONSTRUCTED. The reference rule is ASSUMED. Reading the result as what the stop cost the car is INFERRED, because the laps the car would otherwise have driven aren't observed.
- **Reference:** the median over the same car's analysis laps from its last 5 before the in-lap, in the stint ending at the stop, and its first 5 at age 3 or above after the out-lap, in the stint starting at the stop, with at least 3 on each side. Using both sides balances old and new stint states. It uses laps after the stop, so it's a calibration quantity from past seasons and isn't available during a race. It includes normal traffic.
- **Eligible stops, called "routine green-flag stops":** in-lap and out-lap consecutive, neither of them also the other kind of pit lap, both showing `FLAG_AT_FL` = GF at the line (the flag is only read at the line), dry, not field-slow, not a garage stop. Each stop that isn't eligible is counted with its reason, because the side-count rule drops last stops and stops next to cautions.
- **Caution stops** are counted with their `PIT_TIME_S` and get no pit-loss figure, because the reference pace doesn't apply. A pit-lane start is counted as its own status.
- **Reported:** 10th, 50th and 90th percentiles of pit loss and `PIT_TIME_S`, by class and circuit, and split by whether the driver changed (RECONSTRUCTED). The median of pit loss minus `PIT_TIME_S` is given by class, as description. Empirical quantiles only, with no fitted distribution, because stop types can't be told apart and the distribution may be multi-modal. Per-circuit intervals resample cars within the race, so they show within-race uncertainty only. Class-level intervals resample races.
- **Held-out test.** Two predictors of each 2025 race-class median: the 2024 class median of race medians, and the same circuit's 2024 median. For each class, 7 race-level paired differences with 6 degrees of freedom. The per-circuit figure replaces the class figure only if the interval excludes zero in its favour.
- **Coverage.** The share of 2025 stops inside the same circuit's 2024 10th to 90th range, per race-class (nominal 80%), by class and split by driver change. It carries over for a class if the median race-class coverage is between 70% and 90%, and the number of race-classes outside that band is reported beside it. A race-class needs at least 5 stops in the 2024 range it's compared with, and the number skipped is reported. Stops within a race-class aren't independent, and the band is a judgement.

**Confounds, stated here too:** service content isn't observed (tyres or no tyres, refuel time). Balance of Performance sets refuelling time by event and those documents aren't collected, so a change between seasons can't be separated into BoP and team behaviour.

### Part D: what predicts a race's clean pace

- **Target (RECONSTRUCTED):** the class median of `is_usable_for_pace_model` laps in the race.
- **Clean practice lap, fixed now:** `FLAG_AT_FL` = GF, not an in-lap or out-lap, `stint_lap` at least 2, lap time and all three sectors present, and at most 1.07 times the median of green non-pit laps for that class and session.
- **Practice pace:** the class median over clean laps pooled across FP sessions, after dropping any session whose class median is more than 1.04 times the fastest session's. The ratio is the field-slow ratio from D-025, reused as a choice. It's there because no weather is joined to practice and a wet session would pass the per-session rule whole. Fuel loads and run plans in practice aren't observed.
- **Predictors:** P1, the same circuit's 2024 race target; P2, this weekend's practice pace × a class ratio (race target / practice pace) averaged over the 7 fit races; P3, raw practice pace.
- **Size:** 7 independent races with 2 classes each, plus 2025 Le Mans shown apart because P1 there rests on the compromised 2024 race. D-031's "about 16" counted race-classes and included Le Mans.
- **Decision rule.** A clear gap needs the t-interval over the 7 race-level paired differences in absolute error (the two classes averaged within a race) to exclude zero. Otherwise it's "no clear gap", which doesn't mean the two are equal. Comparisons: P2 vs P3, P2 vs P1, P1 vs P3, with no multiplicity adjustment. Each class is also shown alone. On 6 degrees of freedom, 80% power needs a mean difference of about 1.3 race standard deviations, so this can show a clear gap and not a small one.
- **Sensitivity:** practice pace from the fastest FP session only.

### Checks before any real data is fitted

- Synthetic stints with a known slope, race-to-race slope variation, a slow warm-up lap and stints ending at age-dependent lengths: L recovers the mean slope to within 0.005 s/lap and the t-interval's coverage over 500 synthetic datasets lies between 92% and 98%.
- Pit loss recovers a known injected loss to within 0.05 s.
- The bootstrap resamples whole races, shown by a test that fails under row resampling.
- The 2026 seal raises an error.
- If any of these fails, no real data is fitted until it's fixed.

### Changes after this point

Any change is a dated amendment to this entry saying what was known when it was made. The 2025 check is run once. If a model fails on 2025 it isn't adjusted and re-checked on 2025.

**Known limits:** one race per circuit per fit season, so a circuit effect and a one-off race are the same thing in 2024. Seven fit races means wide intervals. The races share cars, teams and circuits across seasons, and that isn't resampled. Deliberate fuel or tyre saving isn't visible in timing data and is tied to strategy, which is what's being modelled.

**Reviewed before being fixed.** The statistical-reviewer agent raised 14 objections to the first draft, and Kaloyan accepted all of them on 2026-11-09, including the decision ladder and the wet-session rule. The change to leave stint lap 2 out of L and the pit-loss reference came from working through that review, and wasn't checked by the reviewer separately. The code-reviewer agent then compared the code with this entry. Its findings were fixed or written in here before this was committed, except a missing 2024 stop count at a circuit, which stops the run with an error.

### Found (run 2026-11-10, after commit `f4d8ff4`, by `python scripts/run_layer3.py --stage fit`, then `check`, then `refit`, output in `reports/outputs/`, which stays local)

**Sample.** Fit, 2024: 7 races at 7 circuits, 254 car entries, 120 drivers, 1,845 stints, 41,501 analysis laps. Check, 2025: 7 races at 7 circuits, 249 car entries, 123 drivers, 1,737 stints, 37,467 analysis laps. The races are the independent unit, and there are 7 in each season. The caution flag covered more of 2025 (8.2% of Hypercar laps) than 2024 (4.4%), and the slow-lap flag more too (15.3% against 12.1%).

**Support (Part A).** Ages are supported up to 35 for Hypercars and 30 for LMGT3. The 2024 fit leaves out 717 and 214 laps past those limits, and 2025 scoring leaves out 881 and 392.

**Stint age (Part B): not shown to be useful for prediction.**

| | Hypercar | LMGT3 |
|---|---|---|
| 2024 slope, s per lap of stint age (t-interval over 7 races) | 0.018 (−0.016 to 0.051) | 0.044 (−0.005 to 0.093) |
| 2024 slope, % of the race's median clean lap | 0.015 (−0.014 to 0.045) | 0.035 (−0.003 to 0.074) |
| Range of the 7 race slopes, s per lap | −0.027 to 0.067 | −0.022 to 0.117 |
| 2025 slope, s per lap | −0.011 (−0.073 to 0.051) | −0.002 (−0.100 to 0.096) |
| Warm-up: stint lap 2 against ages 3 to 7, s | 0.35 | 0.09 |
| 2025 mean absolute error, F / B / L, s | 1.054 / 1.045 / 1.056 | 1.076 / 1.067 / 1.093 |
| B against F, s saved (interval) | 0.009 (−0.053 to 0.070) | 0.009 (−0.134 to 0.153) |
| L against F, s saved (interval) | −0.002 (−0.085 to 0.081) | −0.017 (−0.237 to 0.204) |
| **Holder after the ladder** | **F** | **F** |
| 2025 race slopes inside the 95% prediction interval (width) | 6 of 7 (0.189 s/lap) | 6 of 7 (0.276 s/lap) |

- These are within-stint associations with laps since a stop, combining fuel, tyres on an unknown mix of used and new sets, and anything else that moves with stint age. They aren't tyre degradation (D-005). Neither class's 2024 t-interval excludes zero. The LMGT3 bootstrap interval does (0.009 to 0.081), but with 7 races that one runs narrow, as registered.
- F holding means no model improved held-out error by more than the uncertainty on 7 races. It doesn't show the effect is zero. The synthetic power quoted above (46% at 0.02 s/lap, 97% at 0.04) assumed a race-slope SD of 0.01, far below the 0.036 and 0.053 measured here, so real power is lower and wasn't measured.
- The two coverage checks pass, but with intervals that wide a pass says little.
- All nine 2024 sensitivities were stable under the registered definition (largest move 0.0075 s/lap). None of them removes a steady track trend, which isn't identified alongside stint age.
- The 2025 slopes are pulled down by COTA 2025, the only race outside the prediction interval in each class. Without it (post hoc, 6 races) they are 0.013 (−0.010 to 0.036) for Hypercars and 0.036 (0.004 to 0.069) for LMGT3.
- **What goes to the simulator:** the holder is F, so no fitted age effect. L's range goes in as an ASSUMED sensitivity. From the registered refit on 14 races: Hypercar 0.003 (−0.028 to 0.034) s per lap and LMGT3 0.021 (−0.027 to 0.069). That range is for the mean slope only, and 14 races are 7 circuits twice (averaging by circuit first gives −0.039 to 0.046 and −0.042 to 0.084). For one new race, the 95% prediction interval is −0.117 to 0.124 for Hypercars and −0.166 to 0.208 for LMGT3. Its lower bound comes from the wet COTA 2025 race. Without that race (post hoc) the prediction intervals are −0.051 to 0.082 and −0.056 to 0.137.

**Routine green-flag stops (Part C).** 2024 stops: 665 eligible of 886 for Hypercars and 706 of 1,001 for LMGT3. 2025: 568 of 830 and 564 of 931. The remainder are listed by reason in the run output. Pit loss is INFERRED, with an ASSUMED reference rule.

| 2024, s | Hypercar | LMGT3 |
|---|---|---|
| Class median of race medians (interval over races) | 84.4 (76.3 to 87.6) | 81.9 (77.4 to 83.8) |
| Driver stays: 10th / 50th / 90th percentile | 57.1 / 77.0 / 93.0 | 35.6 / 75.4 / 90.6 |
| Driver changes: 10th / 50th / 90th percentile | 76.3 / 90.6 / 117.8 | 73.9 / 87.6 / 101.3 |

- The higher median with a driver change (13.7 s for Hypercars and 12.1 s for LMGT3, no interval) is an association: those stops differ in other ways too, and service content isn't observed.
- These stops are green at the line only. The upper tail is affected by long stops, set out below, so the 90th percentiles aren't a clean description of a green-flag stop. The share of stops at a caution was 9 to 17% by class and season.
- The same circuit's 2024 median did not beat the class-wide median on 2025 (Hypercar, 2.5 s better, interval −2.3 to 7.4; LMGT3, 0.8 s worse, interval −4.6 to 2.9), so the class figure stays by the rule (mean error, class figure against circuit figure: Hypercars 8.6 against 6.0 s, LMGT3 3.0 against 3.8 s). With one race per circuit per season and BoP changing by event, a single earlier race was not shown to help. That doesn't show circuits are alike. Without COTA 2025 (post hoc) the result is unchanged (1.6 s, interval −3.8 to 6.9; and −0.2 s, interval −4.5 to 4.1). The class-wide median also pools stops about 13 s apart by driver change, and the simulator's actions separate those.
- Class-wide error on individual 2025 races runs from 1.4 to 24.4 s for Hypercars and 0.3 to 6.4 s for LMGT3.
- **Coverage is mixed.** The median race-class had 80% of its 2025 stops inside the 2024 range for each class, which meets the registered 70 to 90% band, but 3 of 7 race-classes fell outside it in each class. Split by driver change it fails three times out of four: no driver change 67% for both classes, and driver change 66% for LMGT3 (85% for Hypercars). The range is a loose guide and not a calibrated distribution.
- Median pit loss minus `PIT_TIME_S` in 2025 is 4.8 s for Hypercars and 1.3 s for LMGT3, so pit-lane time is near the median cost, but not the same quantity and not at the tails.

**What predicts a race's clean pace (Part D): no clear gap on 7 races.** Comparing 2025 absolute error, seconds saved by the first-named predictor:

| Comparison | Mean | Interval over 7 races |
|---|---|---|
| Practice × class ratio against raw practice | 0.00 | −0.04 to 0.04 |
| Practice × class ratio against last season's race | 0.88 | −0.03 to 1.80 |
| Last season's race against raw practice | −0.88 | −1.78 to 0.01 |

- The practice routes have the lower error in the point estimate by about 0.9 s, with intervals that reach zero. This is "no clear gap" on 7 races, not evidence that they're equal.
- Taken alone, LMGT3 shows a gap for practice over last season's race (0.77 s, interval 0.02 to 1.53). Because the class ratio and raw practice are nearly equal, the matching figure for raw practice (0.79 s) is the same gap counted twice. It isn't robust: leaving out any one of 6 of the 7 races takes the interval across zero, such as without COTA 2025 (0.73 s, −0.20 to 1.66) or Spa (0.54 s, −0.08 to 1.16). Treat it as a weak lead from one class of two.
- With the fastest-session version, the class ratio does beat raw practice (0.39 s, interval 0.09 to 0.69), since the fastest session tends to run quicker than the race. That one is a sensitivity and doesn't replace the primary.
- Le Mans 2025, shown apart: P1 (from the compromised 2024 race) has errors of 2.3 s and 1.9 s for Hypercars and LMGT3, against 0.2 and 0.7 s for P2. One race per class.

**Le Mans, described only and not fitted.** Within-race slopes are negative: Hypercars −0.19 s per lap in 2024 and −0.11 in 2025, LMGT3 −0.14 and −0.07. Only stint ages from 3 up are used and no support limit applies. One race each, with 2024 compromised (E-015). For comparison, the 2024 seven-race mean is positive and the 2025 mean is near zero because of COTA. No explanation for the difference was tested. Routine stops at Le Mans, median and 10th to 90th percentile, in seconds: 2024 Hypercar 73.6 (67.5 to 115.6) and LMGT3 82.1 (70.0 to 111.3) with 169 and 172 stops; 2025 Hypercar 76.0 (70.3 to 103.6) and LMGT3 79.3 (70.3 to 103.2) with 516 and 509 stops.

### Added after the check (2026-11-10). These were chosen after seeing it and change no registered decision

Run with `--stage posthoc`.

- **COTA 2025 looks like a wet race the clean-lap rules didn't catch.** Wetness is INFERRED from the timing: `FLAG_AT_FL` is SF from lap 1 and RF first appears on lap 14. RAIN is above zero on 22% of Hypercar laps. 34% of Hypercar laps and 41% of LMGT3 laps pass the filters. The usable Hypercar median by hour runs from about 131 to 126 s, against about 115 s in the dry 2024 race, and every predictor is 13 to 15 s out there. A [RACER race report](https://racer.com/2025/09/07/no-6-porsche-wins-wet-and-wild-lone-star-le-mans-at-cota) is titled "wet and wild", and other reports describe rain and a red flag. I saw those as search results and couldn't open the page. The slow-lap reference is the race's own median, so in a mostly wet race wet pace counts as normal (the open reference issue from E-016). This is a known gap in D-012 and D-025 and it reached the fit.
- Without COTA 2025 the ladder is unchanged: F still holds in both classes (L saves 0.019 s for Hypercars, interval −0.062 to 0.100, and 0.055 s for LMGT3, interval −0.112 to 0.222, on 6 races). The Part D comparisons also show no clear gap.
- Without COTA 2025, the 13-race refit gives Hypercars 0.016 (−0.002 to 0.033) and LMGT3 0.041 (0.015 to 0.066) s per lap, so the LMGT3 interval excludes zero. This is one exclusion chosen after seeing the data, and it's reported as such. The registered 14-race figures stand.
- **139 of 2,503 eligible stops (5.6%, 2024 and 2025 pooled) cost over 60 s more than their pit-lane time.** 126 of those 139 have a caution-flag lap within two laps of the stop, against 92 of the other 2,364. One Spa 2025 in-lap took 319 s and still showed green at the line. A caution starting during the lap would look like this, but the timing can't confirm it, since the flag is only read at the line. Without them the median moves by up to 1.0 s and the 90th percentile drops by up to 13.4 s (pooled, Hypercar with driver change). The 60 s line was chosen after looking. So the medians are usable and the upper tail isn't a clean description of a stop that was green throughout.

**Reviewed before reporting.** The statistical-reviewer agent checked these results against the run output. It found four errors in the first draft and eight smaller problems. All were corrected. Every figure it asked for is computed in `--stage posthoc`, and it was recomputed from the code rather than copied, which corrected one reviewer figure (the first red-flag lap is 14). No registered decision changed.

---

## E-021: Does measuring a wet race against practice keep wet running out, and what changes when Layer 3 and traffic are rerun?

*Written 2026-11-10 · registered with its code (`b3fc570`) before the tables were rebuilt · run 2026-11-10*

**Why.** E-020 found that COTA 2025 was wet and got through the clean-lap rules. The slow-lap rule (D-012) and the field-slow rule (D-025) measure each lap against that race's own median. In a mostly wet race the median is a wet lap, so wet laps look normal.

The comparison with how the sport works (`docs/research/industry_practice.md`) points the same way: the ACO's 2017 BoP method skipped races run in abnormal weather. That supports keeping wet running out. It doesn't choose between flagging laps and dropping the race, which is Kaloyan's choice here (D-033).

### The rule (D-033)

- **When a race switches:** a race and class switch to the weekend's practice pace as their reference when the race as a whole ran slow. That means its dry median, trimmed at 1.07 the way practice laps are, is over 1.04 times practice pace. Practice must also have at least 8 cars and 100 clean laps in that class.
- **Otherwise nothing changes.** A race that doesn't switch keeps exactly its E-020 flags. Both the slow-lap and the field-slow rule use the switched reference.
- **Practice pace** is E-020's definition: clean practice laps, with sessions over 1.04 times the fastest session's median dropped as wet-looking.
- **Ratios unchanged:** 1.07 and 1.04. The switch threshold reuses 1.04 rather than adding a new number.
- **Why a switch and not "the faster of the two":** the first draft used the faster of the race median and practice pace. The review showed that practice is trimmed and so faster by construction, which would have tightened the rule in dry races. It could also hand the reference to one fast session. Under the switch, dry races are untouched.
- **The E-020 flags stay in the table** as `is_slow_lap_race_ref`, `is_field_slow_race_ref`, `field_pace_ratio_race_ref` and `is_usable_race_ref`, so every earlier result can be rerun with `apply_clean_rule(laps, "race")`.
- **Categories:** practice pace is RECONSTRUCTED from practice timing. Treating it as the dry reference is ASSUMED.

**Known before writing this.** E-020 Part D showed race target and raw practice within about 1 s in 13 of 14 race-classes in 2025, and about 13.6 s apart at COTA 2025. So COTA is expected to switch, and that check confirms it rather than testing it. Which other races switch hasn't been computed.

### Part 1: what the rule changes, measured first (`scripts/check_clean_rule.py`)

On 2024 and 2025 only. The rebuild computes 2026 flags too, but nothing from 2026 is read.

- **Per race and class:** whether it switched, the race-to-practice ratio, and the usable share under each rule. For switched race-classes, the same by race hour and by stint-age band.
- **Gates, in code. The run stops, and nothing is rerun until E-021 is amended, if:**
  1. the old flags don't reproduce E-020's analysis-lap counts outside Le Mans (41,501 in 2024 and 37,467 in 2025);
  2. COTA 2025 doesn't switch in both main classes;
  3. more than 4 other race-classes switch. The 4 is a judgement, and anything above it means the rule reaches beyond clearly wet races.

### Part 2: reruns, all labelled as reruns

2025 has already been seen, so none of these is a fresh test. The fresh test stays 2026, in the simulator's final test.

- **E-020 Parts A to C, rerun under the new rule** (`scripts/run_layer3.py --run e021`), with the same code and the same three stages.
- **E-020's decision stands.** F (no age effect) stays the simulator's default. If the rerun puts another model in charge, that model gets one test on 2026: the same ladder step, the rerun holder against F, with the same t-interval rule over the 2026 races outside Le Mans.
- **What the rerun replaces for the simulator (D-032):** the E-021 refit replaces the E-020 refit for the stint-age range, the age limits, the warm-up figures and the stop medians.
- **E-020 Part D isn't rerun, and the code skips it under this rule.** Its target, the race's clean pace, would be partly defined by practice pace, one of the predictors, so the comparison would be circular.
- **The traffic refit on 2024 and 2025** that D-031 requires before the simulator's final test (`scripts/run_traffic_refit.py`):
  - E-013's and E-014's primary specification unchanged, in both directions, with the race's class pace gap as the window and the past-only window, under both rules.
  - Added: an interval resampling circuits as well as races, because the 14 races are 7 circuits run twice. Also the loose slow-lap rule.
  - The past-only window doesn't depend on the clean-lap rule, so it's the cleaner comparison between the two rules.
  - The new-rule figures go to the simulator. E-013 and E-014 used 18 races including 2026, so their figures aren't directly comparable.
- **Reported with each:** sample sizes in races, cars, stints and laps, and intervals over races.

**Known limits:**
- A stricter slow-lap rule removes some slow laps that belong to a real effect, such as a hot afternoon, a heavy-fuel start, a Bronze driver's stint, or traffic. That pulls slopes towards zero. Under the switch, this applies only to races that switched.
- A race that's wet in practice and race isn't caught.
- Timing data doesn't record tyres, so a wet-tyre lap is inferred from its pace, never observed.

**Review before running.** The statistical-reviewer agent reviewed the first draft and its code, and raised 3 must-fix and 7 should-fix points plus a note.
- **Must-fix, all addressed:** practice and race references weren't measured the same way, one fast session could become the reference, and Part 1 had no code. The switch rule, the minimum practice size and `check_clean_rule.py` came from these.
- **Should-fix:** also addressed. The industry comparison was softened in three places, Part D is skipped in code, the race-reference copy of the field-slow ratio was added, circuit intervals and the loose rule went into the traffic refit, and the 2026 test for a different holder was written down.
- **Not reviewed again:** the switch rule itself.


### Found (run 2026-11-10, after commit `b3fc570`; tables rebuilt with `python -m endurance_strategy.pipeline`, then `scripts/check_clean_rule.py`, `scripts/run_layer3.py --run e021` for fit, check and refit, and `scripts/run_traffic_refit.py`; output in `reports/outputs/`, which stays local)

**Part 1: only COTA 2025 switched, and every gate passed.**

- **COTA 2025 switched** in both classes. Its trimmed dry median was 12.4% slower than practice for Hypercars and 9.9% for LMGT3.
- **Every other race-class sat between 0.991 and 1.007** of practice, including all three Le Mans 2024 classes. So their flags are unchanged and the 1.04 switch threshold was never close to the line.
- **The old flags reproduce E-020's analysis-lap counts exactly** (41,501 and 37,467).
- **At COTA 2025** the usable share fell from 37% to 0% of Hypercar laps and from 46% to 4% of LMGT3 laps.
  - For Hypercars the rule works like dropping the race.
  - For LMGT3 it keeps 53 laps, from 10 cars and 10 stints, all in hours 5 and 6 as the track dried. That matters below.
- **Le Mans 2024 doesn't switch.** Its problem in E-015 was mixed conditions within the race, which the field-slow rule is meant to handle (D-025). This rule doesn't change it.

**Part 2: reruns.** These aren't fresh tests.

- **The 2024 fit is identical to E-020's,** because no 2024 race switched: the same slopes, age limits (35 and 30) and warm-up figures.
- **The 2025 check:** 7 races, 225 car entries, 1,627 stints, 36,171 analysis laps. COTA 2025 has no Hypercar analysis laps, so the Hypercar check has 6 races. The LMGT3 ladder also uses 6 races, because the COTA stints are too short for the anchor test, while its 2025 slope uses 7.
  - F still holds in both classes. Hypercar L saves 0.019 s (interval −0.062 to 0.100, 6 races). LMGT3 L saves 0.055 s (−0.112 to 0.222, 6 races).
  - So E-020's decision stands, and no different holder needs testing on 2026.
- **Refit for the simulator** (14 races at 7 circuits; 39,639 Hypercar and 32,985 LMGT3 laps):

| Simulator input | Hypercar | LMGT3 |
|---|---|---|
| Stint-age slope, s per lap, t-interval over races | 0.016 (−0.002 to 0.033), 13 races | 0.026 (−0.014 to 0.065), 14 races |
| Same, averaged by circuit first (7) | 0.013 (−0.012 to 0.039) | 0.026 (−0.028 to 0.080) |
| Warm-up, stint lap 2 against ages 3 to 7, s | 0.34 (E-020 refit 0.21) | 0.19 (E-020 refit 0.14) |

  - **Hypercar:** the t-interval includes zero. The race bootstrap (0.001 to 0.031) excludes it. With 13 races at 7 circuits, neither settles it.
  - **LMGT3:** the 53 drying-track laps at COTA give a race slope of −0.164, the lowest of the 14. With equal race weights, that one race moves the mean from 0.041 (0.015 to 0.066) without it to 0.026, and takes the interval across zero. So whether the LMGT3 interval excludes zero depends on one 53-lap race.
  - **What goes to the simulator:** the registered 14-race range, as an ASSUMED sensitivity. It's the wider of the two and covers both means. These ranges are for the mean slope. A new race can sit well outside them.
  - **The warm-up figures changed more than either slope.** Only COTA 2025's flags changed, so both moves come from that one race. That shows how far one race can shift a figure that has no interval.
- **Routine stop medians** moved by at most 0.2 s (Hypercar 78.1 and 90.9 s, LMGT3 76.9 and 87.0 s, without and with a driver change, 2024 and 2025 pooled). The driver-change 90th percentiles fell by about 1.7 s.
- **Pit loss on 2025:** 6 races in each class, since COTA's stops lose their reference laps.
  - The same circuit's 2024 median still doesn't beat the class figure (Hypercar 1.6 s better, interval −3.8 to 6.9; LMGT3 0.2 s worse, interval −4.5 to 4.1).
  - Coverage meets the 70 to 90% band for the median race-class in both classes (80%), with 2 of 6 outside it.
  - The driver-change splits still fail in three of four cases.

**Traffic on 2024 and 2025 only (D-031):** seconds per other-class car, races in brackets after each figure. Intervals resample races, then circuits.

| | E-021 rule | E-020 rule | E-014 Part 3, same seasons, before D-025 |
|---|---|---|---|
| Hypercar behind LMGT3, race gap window | 0.353 (0.311 to 0.397; circuits 0.296 to 0.414), 13 | 0.356 (0.314 to 0.400), 14 | 0.36 (0.31 to 0.40), 14 |
| Hypercar, past-only window | 0.343 (0.301 to 0.386), 13 | 0.346, 14 | |
| LMGT3 ahead of Hypercar, race gap window | 0.173 (0.149 to 0.198; circuits 0.139 to 0.207), 13 | 0.175 (0.150 to 0.202), 14 | 0.18 (0.15 to 0.20), 14 |
| LMGT3, past-only window | 0.168 (0.143 to 0.194), 14 | 0.170, 14 | |

- **Sample** (Hypercar, race gap window, E-021 rule): 13 races, 238 car entries, 1,703 stints, 42,949 laps. The loose slow-lap rule moves each figure by under 0.005 s.
- **Why the race counts differ:** Hypercars lose COTA 2025 in both windows because none of their laps there are clean. LMGT3 loses it only in the race gap window, because that window needs the pace gap between the classes, and there's no clean Hypercar pace there.
- **What goes to the simulator:** these figures become its traffic inputs, in place of E-013's and E-014's 18-race figures, which included the 2026 test races.
- **Still associations with inferred exposure (D-004),** not a cost per overtake.

**Reviewed before reporting.** The statistical-reviewer agent checked this against the run output. It found two wrong figures (LMGT3 ladder races, and an hourly pace figure with no source) and a misreading of Part 1 for LMGT3, plus overclaims and missing sample sizes. All were corrected, and its figures were recomputed from the output before use.

---

## E-022: Does a lap-by-lap simulator built from Layer 3 add up to a real race, and what does it say about three simple strategies?

*Written 2026-11-13 · registered with its code (`f9d345e`) before it was run on real data · run 2026-11-16: the replay gate failed*

**What's built (D-034).** A simulator for one car, lap by lap, in `src/endurance_strategy/simulator/`.
- **A lap's time:** base pace, plus the stint-age effect (ASSUMED, flat by default), the warm-up lap, the expected traffic cost and noise. A stop adds its pit loss to the out-lap.
- **Caution laps:** a lap runs at the pace of the flag at its start, and caution laps use the class's caution-lap ratio. A stop is decided at pit entry, the end of the in-lap. It waits while a full-course yellow (FCY) has the pits closed (feasibility rule R5, ASSUMED from race reporting and article 12.2.1), and a stop made under a safety car (SC) costs an ASSUMED 30% of a green one.
- **Energy limit:** it counts green laps only, because caution laps use far less energy. One green lap over the limit can happen right after a deferred stop.
- **Stint-age effect:** flat by default (D-032), and never extrapolated past the supported ages (35 and 30 laps).
- **The race** ends at the first crossing after time.
- **Legality first:** every strategy passes a feasibility check citing its source (D-006). The rules are the energy-limit proxy (ASSUMED), GT3 minimum driving times (2025 Sporting Regulations, 13.2.3, p. 42) and the 45-minute points rule.
- **The randomness** is drawn up front from a separate stream for each source: lap noise from clean-lap residuals, pit-loss spread from real stops as a multiple of the median, SC and FCY episodes, and optionally a stint-age slope drawn once per race from D-032's range.
  - Every strategy run on a seed sees the same cautions, the same noise on lap n and the same draw for stop k.
  - Episodes start as a Poisson process in green time, matching a rate per green hour.
- **The simplified field:** traffic is an expected cost, not cars on track. So there are no positions, gaps or undercuts, and the simulator can't say where a car rejoins after a stop.

**Data:** 2024 and 2025, outside Le Mans (14 races, 7 circuits), with E-021's clean-lap rule. 2026 stays sealed for the final test. Every part is fitted on the same 14 races that Parts B and C check, so neither part is a held-out test.

### Part A: calibration (`--stage calibrate`)

- **Measured here:** per circuit and class, the race length, clean median pace, the traffic rate and the energy-limit proxy (95th percentile of caution-free completed stints, in laps). Per class, the caution-lap ratios, lap residuals and pit-loss samples (routine stops without the long ones, D-032). The SC and FCY episodes, rebuilt from line crossings across the field: runs under a caution flag closer than one green lap are merged, so an FCY that becomes a safety car is one episode, and the merged episode takes the type with more crossings. Rates are per green hour.
- **Taken from D-032:** the stint-age range, warm-up and traffic figures.
- **SC pit loss is ASSUMED, not measured.** Measured against the same car's SC laps, it comes out near zero with a spread of about ±50 s (72 Hypercar and 104 LMGT3 stops). That's too noisy to use. The 30% default comes from that near-zero centre and from an F1 simulator's calibrated 45% (Santillana), and it gets a sensitivity of 0% and 60% in Part D.
- **Already looked at:** that SC loss figure, the stint-length quantiles by class, the flag counts per race and the race lengths were printed while designing this.

### Part B: replay real races (`--stage replay`)

- **What:** every finished car of the two main classes without a garage stop, with at least 20 clean laps, from the 14 races. Its predicted race time for its observed laps is compared with its observed time.
- **Four nested models,** each adding one part: M0 is laps × the car's clean median. M1 adds caution laps. M2 adds one pit loss per stop. M3 splits the pit loss by driver change and adds the warm-up lap. Lap 1 and red-flag laps are taken as observed.
- **Same lap model as the simulator:** every model runs through the simulator's own `engine.lap_time`, with the observed flag on each lap and the in-lap's flag as the stop's flag at pit entry. So the gate tests the code Part D runs. A test replays a simulated car and gets zero error.
- **In-sample and retrospective:** the car's own clean pace and the flags it saw are inputs. So this checks that the parts add up to a race, not that the simulator predicts one.
- **Gate:** M3's median, over races, of each race's median absolute error must be at most 0.5% of race time (about 108 s in 6 hours, roughly one lap). If it isn't, the strategy comparison in Part D doesn't run and the model is fixed first.
- **Reported:** every model's figure, the worst race and the median signed error.

### Part C: are the random parts sensible? (`--stage sanity`)

- **Caution counts:** observed episodes per 6 hours, including races with none, against the simulator's own caution generator over 2,000 races, comparing means and variances. A larger observed variance means cautions cluster more than modelled.
- **One source at a time:** lap noise, then pit-loss spread, then cautions, then slope uncertainty, each added to the deterministic run of the Part D race. The laps completed are shown after each addition (simulation.md).

### Part D: three strategies on the same simulated races (`--stage compare`)

Runs only if Part B's gate passes.

- **The setup:** Spa, 6 hours, a Hypercar at the class's 2024 to 2025 median pace, 2,000 simulated races (seed 20261113). Every strategy runs on every race (common random numbers).
- **The strategies:**
  1. The fewest stops the energy limit allows, with drivers rotating every stop.
  2. One more stop.
  3. The fewest stops, with drivers double-stinting, so a driver change at every second stop.
- **Measure:** the difference in time to complete the lap that every simulated race reaches, against strategy 1, so no slow races drop out. Reported as the mean, the 5th to 95th percentile range and the share of races where it's faster.
- **The primary run** uses the flat stint-age default (D-032), with lap noise, pit spread and cautions on.
- **Sensitivity, fixed now:** no cautions, SC stop free (0%), SC stop costly (60%), the stint-age slope drawn per race from D-032's range, and the slope fixed at the top of its range (0.033 s per lap).
- **What it isn't:**
  - The output is SIMULATED, so it isn't a prediction of a real race or of what a team should do.
  - The 5th to 95th range is race-to-race randomness for a car with these parameters, not a confidence interval.
  - Strategy 3's advantage, if any, comes only from the lower pit loss without a driver change. That gap is an association that may really be tyre work (E-020, `industry_practice.md`).
  - Track position and traffic after a stop aren't modelled.

**Known limits:** one car, with no field. Caution starts are a constant-rate process, without circuit differences or clustering. The energy limit is a proxy in laps, not the BoP energy, which isn't collected. There's no fuel saving, no tyre choice and no retirements.

**Review before running.** The simulator-reviewer agent attacked the code and this plan with synthetic runs.
- **Must-fix, all fixed:** the replay didn't use the simulator's code, stops could be made into closed pits, and green laps could run past the energy limit.
- **Should-fix, fixed:**
  - Lap noise and pit draws drifted between strategies.
  - The caution generator under-counted against a rate per total time, and Part C didn't use it.
  - Line-crossing episodes split.
  - The slope draw was centred on zero.
  - The comparison dropped slow races.
  - Pit spread ignored a zero pit loss.
- **Notes, also addressed:** the FCY pit rule is now R5 in the feasibility table, a zero pace is rejected, and the stop search is capped.
- **Not fixed, and stated:** a stop decided on the final lap isn't charged, and R2 (GT3 driving times) is checked only when driver categories are given, which Part D's Hypercar doesn't need. The fixes weren't reviewed again.

### Found (run 2026-11-16, after commit `f9d345e`, `scripts/run_layer4.py` stages calibrate, replay and sanity; output in `reports/outputs/`, which stays local)

**The replay gate failed, twice, so Part D's strategy comparison wasn't run.**

**First run, as registered.** 332 cars from 12 races. Losail 2024 had no car meeting the filters, and COTA 2025 has no clean Hypercar laps.

| Model | Median over races of each race's median absolute error | Worst race | Median signed error |
|---|---|---|---|
| M0 laps × clean median | 7.61% | 13.12% | −7.22% |
| M1 + caution laps | 4.12% | 7.89% | −3.98% |
| M2 + one pit loss per stop | 1.62% | 5.02% | −1.52% |
| M3 + driver-change split and warm-up | 1.63% | 5.04% | −1.52% |

- **The model ran fast by about 493 s per car on average.** Broken down by lap type, the missing time came from:
  - restart laps after a caution, +40 s each (170 s per car);
  - pit laps, +11 s each (163 s);
  - slow laps such as mistakes and local yellows, +50 s each (79 s);
  - slow-zone periods across the field, +22 s each (58 s);
  - clean laps, +0.16 s each (28 s).
- **Medians understate a sum** when slow laps make the tail long. A routine stop's mean is 89.5 s against a median of 83.2 s.

**Amendment, 2026-11-16, after the first gate failure.** E-022 said the model is fixed before Part D, so these went in, each measured from the same 14 races:
- Expected values instead of medians for clean pace and pit loss.
- A restart-lap ratio: the green lap after a caution is 1.46 times the car's mean clean lap for Hypercars and 1.34 for LMGT3 (928 and 944 laps).
- An incident process for the other green laps the clean-lap rules exclude: 2.2% of Hypercar laps with a mean extra 29.7 s, and 4.3% of LMGT3 laps with 22.9 s.
- They're INFERRED, in-sample, and chosen after seeing the failure, so the rerun below is weaker evidence than the first run.

**Second run.**

| Model | Median over races | Worst race | Median signed error |
|---|---|---|---|
| M0 | 7.46% | 12.86% | −7.14% |
| M1 | 3.28% | 6.09% | −3.21% |
| M2 | 0.87% | 3.34% | −0.83% |
| M3 | **0.67%** | 2.81% | −0.16% |

- **The bias is nearly gone, but the gate (0.5%) still fails.**
- **What's left follows the cautions.** Races with many safety cars or full-course yellows come out too fast: Imola 2024 −2.8%, Spa 2025 −2.0%, Fuji 2025 −1.6%. Races with none come out too slow, about +0.65% at COTA 2024 and both São Paulos.
- One class-wide caution-lap ratio can't price how a caution plays out: queues forming, cars waved by, stops made under it. Pricing cautions by time instead of per lap is the next change. It needs its own registration, because these 14 races have now been used to choose the model.

**Part C: the random parts.**
- **Full-course yellows fit:** 2.97 per 6 hours observed (variance 2.63, 14 races) against 2.79 simulated (variance 2.54).
- **Safety cars don't.** The mean fits (5.74 observed, 5.45 simulated), but the observed variance is 30.8 against 4.6 simulated. 4 of 14 races had none and some had more than 10.
  - Safety cars cluster by race, plausibly through weather and the circuit, and a constant-rate process can't produce that.
  - So the simulator understates how different races can be, which matters most for strategies that bet on a safety car.
- **One source at a time** (Spa, Hypercar, 6 hours, 500 races each), as laps completed:

| Randomness added | Mean laps | 5th to 95th percentile |
|---|---|---|
| None (deterministic) | 162.0 | 162 |
| Lap noise | 162.3 | 161 to 163 |
| + Pit-loss spread | 162.3 | 161 to 163 |
| + Cautions | 150.0 | 142 to 156 |
| + Slope uncertainty | 149.9 | 143 to 156 |

  - Cautions dominate both the level and the spread. Lap noise and pit spread barely move a 6-hour total.

**What this means.**
- The deterministic simulator adds up to a real race to within 0.67% (median), but not within the registered 0.5%. Its errors are largest exactly where strategy is most interesting: races with safety cars.
- Its caution process gets the average right and the race-to-race spread wrong.
- Neither is ready to rank strategies, so no strategy result is reported.
- Next: time-based caution pricing, and a caution process with race-level variation, such as a rate drawn per race. Each gets a fresh registration, and the 2026 races stay the final test.

## E-023: Do time-priced cautions and a safety-car rate drawn per race close E-022's replay gap, and what do the three strategies then show?

*Written 2026-11-20 · registered with its code before it is run on real data*

**Why.** E-022's replay missed its 0.5% gate at 0.67%, and the error followed the cautions: races with many came out too fast, races with none too slow. Its safety cars also clustered by race far more than a constant rate allows (variance 30.8 against 4.6 per 6 hours). These are the two changes E-022 named, and nothing else is changed.

**Change 1: cautions priced by time (`CarParams.caution_progress`).**
- **Idea:** a car under a caution keeps a share of its green speed. Its full green lap (base, age, warm-up, traffic, noise) is covered at full speed outside an episode and at that share inside one. So a lap straddling a caution's start or end is only partly slowed, and the cost of a caution follows its length, not how many line crossings fall inside it. An incident (E-022's amendment) is added on top of a lap that starts green, like a pit loss.
- **Episodes** now run from the first to the last crossing under the caution across the field, so they are the period the line shows the caution. E-022 added one green lap after the last crossing. Without that tail, a stop or an FCY pit closure follows the real flag at the line.
- **Measured** per class and caution type, from 2024 and 2025 outside Le Mans, the way the engine applies it. For each car and episode: its last crossing at or before the start and its first at or after the end. Over that bracket it covered (laps) × (its mean clean lap) of green running. The bracket outside the episode is taken at full speed, and the rest of the work was done inside. The share is that work summed over the summed episode durations. The clean lap includes traffic, as the engine's full green lap does. Left out: lap 1, a bracket with a pit lap, a red flag or another episode in it, and a car with no crossing after the episode. 
- **Restart cost per episode (`CarParams.restart_extra_s`).** The lap that starts at the bracket's end, within one clean lap of the episode's end, green throughout and without a stop, is the field restarting. Its mean extra time over the car's clean lap is charged once per episode on the lap that starts within one green lap after the episode ends. Without it, the same caution time split into more episodes replays too fast, which is E-022's pattern (a synthetic case in the review: −45 s over 6 short safety cars against +2 s for one long one).
- **Replaces** the per-lap caution ratio and the restart-lap ratio from E-022's amendment, with a share and a restart cost fitted on the same brackets.
- **Synthetic check, fit then use:** a field at a known share (0.35 and 0.6) through three safety cars, the share fitted from rebuilt episodes, then every car's race rebuilt with it. The median error is under 0.1% of race time. A missing share, or one outside (0, 1], stops the run instead of meaning a free caution.
- **Replay (Part B):** M1 to M3 now run each car on the model's own clock through its race's rebuilt episodes, as the simulator does with drawn ones. A lap's flag and a stop's flag at pit entry come from those episodes at the predicted time. M0 keeps full speed under cautions. A test replays simulated cars with cautions and gets zero error. **This changes what the gate measures:** if the model's clock drifts, a real stop can fall just inside or outside a safety car and swing its price by about 50 s. E-022's replay used each lap's observed flag.
- **Kept:** the 30% SC pit loss (ASSUMED) and the FCY pit closure (R5). A pit loss is added after the lap's cover time, so it isn't itself slowed or sped by a caution.

**Change 2: each race draws its own caution rate (`Randomness.caution_rate_shape`).**
- **Idea:** a race's rate is the calibrated rate times a gamma multiplier with mean 1 and shape k, so counts per race have variance mu + mu²/k. Weather and circuit plausibly drive this, but neither is modelled, only the spread.
- **Estimated by simulated moments, rate and spread together,** per caution type. For each 1/k on a grid (0 to 6, step 0.2), the simulator's own generator, with the observed mix of race lengths, first has its rate rescaled until the mean count per race matches the observed one, and then runs 3,000 races. The 1/k whose variance of counts per 6 hours is closest to the observed one is kept, with its rate (seed 20261120).
  - Why jointly: a gamma multiplier alone lowers the mean count, because races that draw a high rate fill with cautions and run out of green time (the review measured 14 to 37% fewer).
  - A closed-form moment estimate was tried first and read low for the same reason.
  - **If the observed variance is beyond the top of the grid**, `out_of_reach` is set and the shortfall reported in Part C. It doesn't block the replay gate, which uses each race's own episodes, but Part D's spread of races is then understated and is reported as such.
  - The constant-rate sensitivity in Part D uses the original rate.
- **How loosely 14 races pin it down:** 200 sets of 14 races drawn at the fitted 1/k are refitted the same way, and their 5th to 95th percentile is reported next to the estimate. With that few races it will be wide.
- **Synthetic tests:** a known spread (1/k = 1 and 0) is recovered within 0.25 from 800 races, with the mean count kept within 6%, and an unreachable variance is flagged.

**Review before running.** The simulator-reviewer agent attacked the code and this plan with synthetic runs.
- **Must-fix, both fixed:** the caution share was fitted and applied in different units, reading high and making caution-heavy races too fast (0.2 to 0.4% of race time in its tests). The closed-form spread estimate read low.
- **Should-fix, fixed:** the green tail of an episode was priced as a caution for stops and FCY closure; a lap's green parts switched on and off with the flag at its start; a missing share silently meant a free caution. Clock drift is now stated above.
- **Checked and fine:** common random numbers between strategies hold with the per-race rate, and nothing reads 2026.
- **Second round, on the fixes:** the time pricing now replays an engine-generated field within about ±1 s over 6 hours, with traffic, noise and 1 to 8 episodes. It raised two more must-fix items, both fixed: the restart lap had no cost once the episode's tail was removed, and the gamma multiplier lowered the mean count with real episode lengths. Those last fixes weren't reviewed again.
- **Still open:** a class with safety-car shares but no usable FCY car-episodes stops the run (loud, not silent). With 14 races the spread's 90% refit range is wide (0.15 to 2.95 for a true 1/k of 1.25 in the review's check), which is why the range is reported.

**Same as E-022:** data (14 races, 2024 and 2025 outside Le Mans, 2026 sealed), the car filter, nested models M0 to M3, the gate, Part D's car, seed, 2,000 races and three strategies.

**Gate, unchanged:** M3's median over races of each race's median absolute error ≤ 0.5% of race time. If it fails, Part D doesn't run (enforced in `scripts/run_layer4.py`), the failure is reported, and no further amendment is made inside E-023.

**Also reported:**
- The Spearman correlation between each race's caution count and its M3 median signed error, over the races the replay covers (12 in E-022). It's descriptive. E-022's pattern would show as a negative value.
- Part C: simulated safety-car and FCY counts per 6 hours with the per-race rate and with a constant rate, against observed (mean, variance, share of races with none).
- Part D adds one sensitivity: a constant caution rate.

**What this can't show.**
- **This is the third look at these 14 races.** E-022 chose the model on them, and E-023's changes were chosen from E-022's errors. A pass says the parts add up to these races. It isn't a held-out test, and 2026 stays sealed for that (D-031).
- The caution share is an average over cars and episodes. Real cautions differ: queue position, wave-bys and closed pit lanes all vary by episode.
- The gamma spread reproduces how much races differ, not why. A strategy that bets on a safety car is judged against a fitted spread from 14 races. Circuit differences are folded into that spread, and safety cars and FCYs are drawn independently, though an FCY often turns into a safety car.
- The output of Part D is SIMULATED, not a prediction of a real race (E-022's limits all stand).

**Amendment 1, 2026-11-20, after the calibration stage and before the replay was run.**
- **What was seen:** the first calibration (commit `fd7661f`) gave Hypercars a safety-car share of 0.05 from only 46 car-episodes, against 0.53 for LMGT3. A car keeping 5% of its speed behind a safety car isn't plausible.
- **Cause, a reconstruction bug inherited from E-022:** safety-car episodes had a median length of 139 s, and 95% of brackets overlapped another episode. Behind a safety car the queue crosses the line within seconds and then the line stays empty for a whole slow lap. That gap is longer than one green lap, so E-022's merge rule (a gap under one median green lap) cut a safety car into one episode per lap.
- **Fix:** an episode now continues until racing resumes, meaning some car crosses the line green twice in a row before the next caution crossing. A synthetic test with a bunched 20-car queue checks it, and checks that a single restart lap doesn't split the episode.
- **What it puts in doubt in E-022:** Part C's safety-car counts and their clustering (5.74 per 6 hours, variance 30.8 against 4.6 simulated) were measured on split episodes. The clustering may be partly an artefact of the split, so E-022's Part C safety-car finding is superseded by this rerun.
- **Nothing else changes:** the gate, the data and Part D stay as registered. The first calibration's output is kept as `e023_calibrate_before_amendment1.json`, and the first calibration figures are recorded here: SF share 0.053 (Hypercar, 46) and 0.527 (LMGT3, 51); FCY 0.328 (674) and 0.389 (629); restart 1.44 and 1.34 s; SF fitted 1/k = 1.0 (refit range 0.2 to 3.4) with simulated variance 31.9 against observed 30.8; FCY 1/k = 0.

### Found (run 2026-11-20, after commits `fd7661f` and `896b4cf`; output in `reports/outputs/e023_*`, which stays local)

**The replay gate failed again, so Part D's strategy comparison wasn't run.** As registered, no further amendment is made inside E-023.

**Calibration, after amendment 1.**
- **Episodes:** 28 safety cars (2.0 per race, median 665 s) and 44 FCYs (median 164 s) over 14 races. E-022's split rule had found 87 "safety cars".
- **Share of green speed kept** (car-episodes): Hypercar 0.44 under a safety car (209) and 0.35 under an FCY (689); LMGT3 0.60 (213) and 0.41 (645).
- **Restart lap:** +1.40 s (Hypercar, 645 laps) and +1.78 s (LMGT3, 641).
- **Per-race safety-car rate:** fitted 1/k = 0.4, but 200 refits of 14 races span 0 to 1.6, and 34% land on zero. So 14 races can't tell this spread from a constant rate. FCYs show no extra spread (1/k = 0).

**Part B: replay** (332 cars, 12 races, as in E-022).

| Model | Median over races | Worst race | Median signed error |
|---|---|---|---|
| M0 laps × clean mean | 7.39% | 12.76% | −7.08% |
| M1 + cautions by time | 3.24% | 5.03% | −3.18% |
| M2 + one pit loss per stop | 0.96% | 2.42% | −0.82% |
| M3 + driver-change split, warm-up, incidents | **0.78%** | 1.95% | −0.22% |

- **Worse than E-022's 0.67% overall, though the worst race improved** from 2.81% to 1.95%.
- **The caution-heavy races improved most:** Imola 2024 went from −2.81% to −1.85%, Spa 2024 from −2.57% to −0.75% (1 car) and Fuji 2025 from −1.61% to −0.46%.
- **The races with few cautions got slower:** COTA 2024 went from +0.64% to +1.17% and São Paulo 2025 from +0.69% to +0.99%. Spa 2025 is still −1.95%.
- **The error still follows the cautions:** Spearman −0.55 between a race's caution count and its median signed error, over 12 races (descriptive).
- **Both classes are off by the same amount** (median signed −0.22% and −0.23%).

**Part C: the random parts.**

| Per 6 hours | Observed (14 races) | Simulated, rate per race | Simulated, constant rate |
|---|---|---|---|
| Safety cars, mean | 1.81 | 1.66 | 1.74 |
| Safety cars, variance | 2.17 | 2.21 | 1.55 |
| Safety cars, share of races with none | 29% | 25% | |
| FCYs, mean | 2.90 | 2.78 | 2.74 |
| FCYs, variance | 2.39 | 2.74 | 2.67 |

- **One source at a time** (Spa, Hypercar, 500 races): no randomness gives 162 laps; lap noise and pit spread give 161 to 163; cautions give 140 to 161 (mean 153.8); slope uncertainty adds nothing visible. Cautions still dominate.

**What this means.**
- **Time-priced cautions fixed the races they were aimed at, and the error moved to the races without cautions.** The low-caution races now run too slow by up to 1.2%. So something on the green side is now overcharged. The likeliest suspect is the incident charge (E-022's amendment): it is pooled over all races, and its slow-zone and local-yellow laps cluster around cautions, so races without cautions are charged incidents they didn't have. That is a hypothesis from the error pattern, not something this run tested.
- **E-022's safety-car clustering was mostly an artefact** of splitting episodes. With episodes rebuilt properly, safety-car counts vary only a little more than a constant rate gives, and 14 races can't separate the two.
- **No strategy result is reported.** The simulator now gets caution counts and their spread right, and prices caution time from data, but it still doesn't add up to real races within the registered 0.5%.
- **Next:** test the incident hypothesis in a fresh registration, for example an incident charge measured outside caution brackets or per race, with the same gate. The 14 races have now been used three times, so any further pass is weaker evidence, and 2026 stays sealed for the final test.

## E-024: Does tying incidents to cautions, and counting long stops in the pit loss, close the replay gap?

*Written 2026-11-20 · registered with its code before it is run*

**Why: a breakdown of E-023's M3 replay error by lap type.** This is exploratory and in-sample, on the same 14 races (script kept locally; per car, summed over its laps, median across cars).

| Lap type | Races with ≤ 4 cautions | Races with ≥ 5 cautions |
|---|---|---|
| Clean laps | +270 s (187 laps) | +454 s (164 laps) |
| Incident laps | −25 s (1.3 laps) | −111 s (6.7 laps) |
| Caution and restart laps | −66 s | −350 s |
| Pit laps | −7 s | −242 s |

- **Incidents cluster in caution-heavy races.** A car has 6.7 incident laps there against 1.3 in quiet races. E-022's incident charge is one pooled rate, spread as an expected value over every green lap (about 0.65 s a lap for Hypercars and 1.0 s for LMGT3). So quiet races are overcharged and busy ones undercharged.
- **Long stops are missing from the expected pit loss.** In-laps run 30 s too fast on average (median −5.6 s), from a tail of long stops that calibration leaves out (more than 60 s over the pit-lane time, D-032). E-020 found they sit near cautions.
- **Where the caution-heavy races lose most** (caution laps against clean laps) partly reflects the model's clock drifting from the real one, so the categories trade time with each other. Only the two causes above are acted on.

**Change 1: incident rate per race (`CarParams.incident_rate_per_caution_hour`).**
- The share of green laps with an incident is a + b × (caution episodes per green hour of that race), fitted per class across the 14 races by least squares weighted by green laps. Incident laps are defined exactly as in E-022's amendment, and restart laps are left out of the green laps, as there.
- The replay uses each race's rebuilt episodes. The simulator uses the race's drawn episodes, so its incidents follow its cautions. One function (`engine.race_incident_rate`) serves both. The rate is never negative.
- It's an association across races. Weather and the circuit plausibly drive both, and the model doesn't say which causes which.

- **Charged only on the laps the fit counts:** green throughout (no caution inside the lap), not lap 1, not an in-lap or out-lap, and not a restart lap. The stop is now decided before the lap's time is worked out, so an in-lap carries no incident.
- **The caution rate is capped** at the highest rate seen in the 14 races, so a simulated race with more cautions doesn't extrapolate the line.
- **Uncertainty on b:** a 90% interval from 2,000 resamples of whole races, and the share of resamples at or below zero.

**Long stops: reported, not gated (`M3_long`).** The review pointed out that a class-wide mean including long stops adds the same cost to every race, while the gap is in the busy ones. It would also charge every planned stop in Part D, which biases a comparison of stop counts. So the gated M3 keeps the routine pit loss, and a separate replay row, `M3_long`, shows M3 with the mean over all eligible stops, long ones included.

**Also fixed: random stop draws keep the deterministic mean.** A drawn stop was scaled by sample ÷ median, so its mean was about 6% above the deterministic stop cost the replay uses. It's now sample ÷ mean. This affects only Part D's random draws.

**Synthetic tests:**
- the rate rule is unchanged when b = 0 and is never negative;
- simulated incidents follow the drawn cautions (none at all when a = 0 and no cautions are drawn), and never land on lap 1, pit laps or laps with a caution;
- the fit recovers a known a and b across 12 synthetic races;
- fit then use: 30 races generated by the engine with known a and b, turned into timing rows, give a and b back.

**Review before running.** The simulator-reviewer agent found three must-fix problems, all addressed above:
- long stops spread evenly over races (moved to `M3_long`);
- the long-stop excess overlapped incidents on pit laps (gone with the move);
- incidents charged on laps the fit leaves out, about 14% of incident time in its probe.

It also asked for the interval on b, the cap, the fit-then-use test and the stop-draw mean, all done. The fixes weren't reviewed again.

**Same as E-023:** data, cars, episodes (with amendment 1), caution shares and restart cost, the per-race caution rate, models M0 to M3, the 0.5% gate on M3 and Part D. M3 now carries the driver-change split, warm-up, incidents and the restart cost together. Outputs go to `e024_*`.

**What this can't show.**
- **This is the fourth look at these 14 races,** and the changes were chosen from a breakdown of E-023's errors on them. A pass means the parts now add up to these races, which is a weaker claim with each look. The held-out test is 2026, sealed (D-031), and that's where the simulator is judged.
- b is fitted from 14 races, with caution counts from 0 to about 9.
- `M3_long` charges long stops as an average on every stop. In a real race they are rare, large and near cautions, so it's reported for size only.

### Found (run 2026-11-20, after commit `28b402b`; output in `reports/outputs/e024_*`, which stays local)

**The gate failed, and M3 got worse: 0.98% against E-023's 0.78%.** Part D wasn't run, and no amendment is made inside E-024.

**The incident link.**

| Class | a (no cautions) | b per caution per green hour | 90% interval for b | Races |
|---|---|---|---|---|
| Hypercar | −0.037 | 0.077 | 0.007 to 0.142 | 13 |
| LMGT3 | −0.105 | 0.183 | 0.010 to 0.390 | 14 |

- **Incidents do rise with a race's cautions:** b is above zero in nearly every race resample (0.15% at or below zero for Hypercars, none for LMGT3).
- **But a straight line is the wrong shape.** Its intercepts are negative, so races with few cautions get no incidents at all once the rate is floored at zero. Real quiet races still have some (1.3 incident laps per car).

**Replay** (332 cars, 12 races).

| Model | Median over races | Worst race | Median signed error |
|---|---|---|---|
| M3 (gated) | 0.98% | 2.44% | −0.82% |
| M3_long (long stops in the pit loss, not gated) | 0.79% | 2.12% | −0.52% |

- The model is now too fast overall: the incident charge fell too far.
- The error still follows the cautions: Spearman −0.57 over 12 races.
- Part C is as in E-023: cautions match in mean and spread.

**Exploratory, after the run: the cost of an extra stop.** Within each race, a car's M3 error was regressed on how many stops it made, each measured from its race's mean, so race-level errors such as cautions cancel. Each extra stop comes out **25 s too slow** in E-024 (90% interval 9 to 44 s, resampling 12 races) and 37 s in E-023 (21 to 55 s).
- The model overcharges the marginal stop. Cars that stop more may make cheaper stops (shorter work, stops under a caution, drive-throughs counted as stops), and the single mean stop cost doesn't see that.
- This matters more for strategy than the race-time gate does. A pit strategy is mostly a choice of how many stops and when, so a stop cost that's wrong at the margin would bias Part D directly, however well race time adds up.
- It's exploratory and in-sample. It was looked for after the result, and it isn't a registered finding.

**What this means.**
- Four looks at the same 14 races (E-022, its amendment, E-023, E-024) have each moved the error rather than removed it. Further fixes chosen from these races' errors would fit them, not validate anything.
- The gate on total race time isn't the right test of a strategy tool on its own. In Part D every strategy runs on the same simulated races, so errors common to all of them (most of the caution error) cancel. What doesn't cancel is how the simulator prices the things strategies differ in: an extra stop, a longer stint, a driver change.
- **Next (to decide, D-035):** validate those differences directly, starting with the marginal stop cost against within-race data like the check above, registered and with a gate of its own. Keep the race-time replay as a reported check rather than the only gate. The final test stays 2026, sealed.
