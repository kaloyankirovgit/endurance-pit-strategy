# Decisions

The choices that shape the rest of the project, and why I made them. If one gets reversed, it stays here with a note pointing to whatever replaced it.

---

## D-001: Where the project lives

*2026-09-22*

In `~/Projects/endurance-pit-strategy-planner` rather than Downloads or an iCloud folder. Downloads gets cleared out, and iCloud sync doesn't get on well with Git.

## D-002: raw / interim / processed

*2026-09-22*

Data moves from `raw` to `interim` to `processed`. It's the same idea as the bronze/silver/gold layers people use in data engineering. The source is never touched, and every step after it is cleaner and built for something more specific. I went with the more common folder names so there's only one vocabulary.

## D-003: Test fixtures go in `tests/fixtures/`

*2026-09-22*

Everything under `data/` is git-ignored so real timing data can't slip into a commit. Putting fixtures in `data/fixtures/` would mean punching a hole in exactly that rule. So fixtures live with the tests instead, and they're always synthetic.

## D-004: Traffic is inferred exposure, not overtakes

*2026-09-22*

The timing data records when a car crosses a timing line, not where it is on track in between. An "overtake detector" built on that couldn't be checked against anything, because there's no ground truth. So the traffic model looks at when a car was likely running into slower traffic and how its lap times behaved, and says plainly that the exact pass isn't observed.

The 15-point Le Mans data (D-009) narrows *where* time was lost. It still doesn't see a pass, so this stands.

## D-005: Fuel and tyres aren't separated

*2026-09-22*

Fuel burning off makes a car faster through a stint, tyres wearing makes it slower, and both happen as the stint goes on. Timing data alone can't tell those two apart. So I model one combined stint-age effect from the data. If the simulator needs separate fuel and tyre terms, they're labelled as assumptions and I test how sensitive the answer is to them.

This only changes if I find a source that actually measures fuel or tyre state.

## D-006: Regulations are a separate check

*2026-09-22*

Legality gets checked before the simulator runs, by its own function that returns whether a strategy is allowed and which rules it breaks. The rules sit in a versioned table where every row cites a document and page. They change by season and sometimes by event, so they can't be hard-coded. This also gives the LLM layer a real job later on: pointing to the exact rule that ruled a strategy out.

## D-007: Plain search before reinforcement learning

*2026-09-22*

The first optimiser is an exhaustive search over legal pit windows. It's easy to test, and it gives a baseline anything fancier has to beat. RL only comes in once the simulator has been checked against real races. Otherwise it just learns the simulator's mistakes, and you can't tell which is to blame.

Tuning parameters and evaluating a policy are different jobs and need different data.

## D-008: The LLM explains, it doesn't compute

*2026-09-22*

The language model can read the regulations, pick simulator inputs from a fixed schema, call the simulator and explain what came back, with citations. It can't change the numbers or decide pit timing in prose. Every number in an answer has to trace back to a tool call or a document. Without that line it's a chatbot with a racing theme.

## D-009: Breadth first, with a Le Mans deep-dive

*2026-09-22*

The archive has 121 events at 3-sector resolution. Only Le Mans (2025 and 2026) and COTA 2026 have the finer 15-point timing.

Breadth helps generalisation because it means more races and more circuits. Depth helps with the traffic question, since finer timing makes it more likely the effect can be picked out at all. So I'm doing both: the pipeline and all the pace and pit modelling run across the full corpus, and the 15-point races become a separate traffic sub-study.

The two are never pooled into one number without an argument. A traffic effect found at Le Mans is a Le Mans result until something shows it transfers.

## D-010: The corpus is 2024 to 2026 (21 races)

*2026-09-22*

| Option | Races | Circuits | Laps |
|---|---:|---:|---:|
| 2023–2026, everything | 28 | 11 | 236,738 |
| **2024–2026** | **21** | **8** | **179,259** |
| Le Mans only | 4 | 1 | 70,968 |

2023 is effectively a different championship. Its third class is LMGTE Am rather than LMGT3, and LMP2 ran the whole season. Mixing it in would mean an era adjustment in every model for six extra races. A clean 21-race set is easier to defend.

It also splits neatly by time: **fit on 2024 (8 races), validate on 2025 (8), test on 2026 (5)**. The 2023 files stay on disk for a later robustness check.

One consequence: 18 of the 21 races are two-class (Hypercar and LMGT3), because LMP2 only races at Le Mans now. So I describe it as two-class wherever that's what the data is, and class-pair effects get estimated per pair.

## D-011: How pits and stints are read from the timing

*2026-09-24*

The source has no in-lap or out-lap column. Working from the whole corpus (E-003):

- `CROSSING_FINISH_LINE_IN_PIT = B` is the **in-lap**, the lap that ends in the pit lane.
- `PIT_TIME` is on the **out-lap**, the lap after. It's time in the pit lane including the stop, not just time stationary.
- A new stint starts on each out-lap. The in-lap is the last lap of its stint.
- A lap-1 `PIT_TIME` is a pit-lane start, which is still stint 1.

This lives in `src/endurance_strategy/reconstruct/stints.py` and is pinned by tests. A few `PIT_TIME` values run to hours because cars were parked in the garage, so pit loss and garage time will need separating before any pit-loss model.

## D-012: What counts as a clean lap

*2026-09-24*

A lap feeds the pace model only if it's green at the line, not the first lap, not an in-lap or out-lap, not the lap right after a caution, has all its times, and is within 7% of the median clean lap for its class at that race. The numbers are in E-004.

Laps are flagged, never deleted. Each rule has its own column, so any model can use a different combination and say which it used. The 7% is a judgement call. About 5% of the usable count moves between 3% and 15%, so results that depend on it get checked at other thresholds.

## D-013: Weather joining and garage visits

*2026-09-24*

Lap times get a UTC timestamp from `HOUR` (local wall clock), the race date and a per-circuit time zone, not from `ELAPSED`, which stops during red flags. Each lap takes the latest weather reading at or before it crossed the line, within five minutes. `RAIN` above 0 counts as wet, and wet laps are left out of the clean-lap set (so D-012 now has seven rules).

A stop is a garage visit if its `PIT_TIME` is over 3× the race median. The long stops under safety car stay as normal stops, because queueing at pit exit is part of what a stop costs. Evidence in E-005.

## D-014: One pipeline, validated on write

*2026-09-24*

`python -m endurance_strategy.pipeline` rebuilds everything from the raw files. The lap table is validated with a Pandera schema before it's written, so a bad row stops the run where it happens rather than three steps later. Race order uses DuckDB window functions, because ranking within a lap and looking back along the road reads more clearly in SQL than in pandas. Outputs are Parquet, and none of them are committed, since they're derived from the timing data.

---

## D-015: Race order is checked against the classification, and AI evidence comes before the traffic work

*2026-10-20*

Race order is compared with the official end-of-race classification car by car. A raw position match would undersell it, because one post-race penalty shifts every car it passes. So each car's laps and finishing time are compared instead, and each difference gets a label: time penalty, fewer official laps, or unexplained (E-007).

The work order after this changes. Hooks and evals for the review agents come next, then the regulation retrieval part of Layer 6, and only then the traffic baseline. Retrieval doesn't depend on the simulator, so only the order changes. The cost is that the first traffic result comes later.

---

## D-016: The no-data rule is enforced by hooks, not just written down

*2026-10-20*

The rule that nothing ignored gets committed used to live in `CLAUDE.md` and in a test. The instruction can be skipped, and the test only catches a mistake after it's committed. Now one script, `scripts/guard_commit.py`, blocks the commit itself, in two places:

- **As a Claude Code `PreToolUse` hook.** It runs before any Bash command Claude makes, and blocks a `git commit` (exit code 2) if an ignored file is staged or tracked, or if the commit tries to skip the git hook with `--no-verify`.
- **As the git `pre-commit` hook.** It runs on every commit made outside Claude, from the terminal or VS Code.

Both run the same check, `git ls-files --cached --ignored --exclude-standard`. Private paths sit in `.git/info/exclude`, so the guard covers them without the public repo naming them. Seven tests run it against a throwaway repo.

The first version matched the words "git commit" anywhere in a command, and it blocked a harmless command that only had the phrase in some text. It now matches only a real `git commit` at the start of a command, and a test pins that. Anyone cloning has to run `git config core.hooksPath .githooks` once to turn the git hook on.

---

## D-017: Review agents are evaluated with labelled cases and exact-match scoring

*2026-10-20*

The review agents are scored on synthetic write-ups with planted flaws and clean controls, run headless through `claude -p` with a fixed JSON schema for the answer. Scoring is an exact match against labels, with no second LLM acting as judge, so a score can be checked by reading the labels. Each case runs 3 times because the output varies between runs. The agent runs from an empty folder with no tools, so the project's own instructions can't leak in and make the eval easier than real use.

A case set that has been used to change an agent's prompt can't then be used to report the improved score. Prompt changes are tested on a fresh set (E-008).

---

## D-018: Regulation retrieval starts with BM25 and a season filter

*2026-10-23*

- **Text extraction:** `pypdf`, installed through the optional `rag` extra so CI doesn't need it. The regulations are bilingual, with French on the left and English on the right, so only text in the right half of each page is kept. Lines are rebuilt from the text positions.
- **Chunking:** one chunk per lowest-level numbered article, carrying its heading path and pages. Main articles must follow in order, and sub-headings must start at the column's edge, so numbers inside a sentence don't open a chunk.
- **Retrieval:** BM25, written in about 40 lines rather than pulled in as a library, with the usual k1 = 1.5 and b = 0.75 and no tuning. No embeddings and no vector store yet. The corpus is three documents, and keyword search is the baseline anything fancier has to beat.
- **Versions:** every chunk carries its season, and retrieval filters on the season being asked about. E-009 shows why: without the filter, the same article from the wrong season comes out on top for 30 of 82 questions.

---

## D-019: Regulation answers are routed, grounded and checked in code

*2026-10-23*

Every question goes through three steps, each one inspectable on its own:

- **Router:** an LLM call with a fixed list of routes (regulation lookup, simulation request, out of scope). Strategy questions are declined, because pit timing comes from the simulator, never from prose (`rag.md`).
- **Answerer:** the model sees only the retrieved extracts. It must cite chunk IDs with word-for-word quotes, or refuse and say what's missing.
- **Checker:** plain Python, no LLM. Every citation must be a retrieved chunk, every quote must appear in that chunk, and every number in the answer must appear in a cited extract (D-008). An answer that fails isn't shown.

The calls run headless through `claude -p` with a JSON schema, using the same helper as the reviewer eval (`src/endurance_strategy/llm.py`). The full trace (route, retrieved chunks, raw answer, check result) is logged for every question, so a wrong answer can be traced to retrieval or to generation.

---

## D-020: Embeddings stay a candidate, BM25 stays the default

*2026-10-23*

A small local embedding model (`BAAI/bge-small-en-v1.5` through `fastembed`) and a hybrid (reciprocal rank fusion of BM25 and embeddings) were compared with BM25 on the original questions and on 30 fresh ones written before any embedding ran (E-011). Both look better, but on the held-out set the gap is a few questions: at rank 1, embeddings won 4 and lost 1 against BM25. That's inside what 30 questions can resolve, so by the baseline rule BM25 stays the default. The hybrid never did worse than BM25 in the top 5 on either set (5 wins, 0 losses), which makes it the first thing to confirm on a larger question set.

---

## D-021: The car class is an explicit input, and retrieval ignores it

*2026-10-24*

The user picks the class (`Hypercar`, `LMGT3` or `LMP2`), the way a strategy tool's menu would, and the system doesn't guess it from the question. Retrieval stays class-blind, because a clause that names one class often applies to all of them, and adding the class to the query lost recall (E-012). The class goes to the answer prompt, which must use only that class's figures.

LMP2 is refused in code, not left to the model, because the corpus doesn't cover it. The WEC sporting regulations are written for Hypercar and LMGT3, and LMP2 races only at Le Mans under ACO regulations that aren't collected. If those are added later, the refusal is one set to change (`COVERED_CLASSES` in `rag/answer.py`).

---

## D-022: Traffic exposure is counted at the start of the lap, within the class pace gap

*2026-10-24*

For each lap, the exposure is the number of slower-class cars that crossed the line in the W seconds before the car began that lap, leaving out pit-lane crossings. W is the race's class pace gap, so those are the cars it should catch before the lap ends. Counting at the start matters. The end-of-lap gap is partly caused by being held up, so it would build the outcome into the exposure.

The comparison is within stint (one car, one driver, one set of tyres), with a straight-line trend in stint lap removed from both the lap time and the exposure. Removing it from the lap time alone hid about 10% of a known effect on synthetic data. Intervals resample whole races.

W comes from whole-race medians. That's fine for describing races, but a team doesn't have it at lap t, so the simulator needs a past-only version. The per-car figure depends on W (E-013), so results quote the W range or the one-car contrast, which barely moves with W.

---

## D-023: Traffic is estimated in both directions, and the simulator's window comes from past laps

*2026-10-24*

Multi-class traffic costs both cars, so both figures go forward: the faster car catching slower ones, and the slower car being caught (E-014). The window W is taken from laps finished before each lap began, which gives the same figures as the whole-race window, so the look-ahead in D-022 doesn't matter for the estimate. The count itself still uses crossings near the start of the lap, so the simulator will need its own version built from road gaps at the decision point.

A check on placebos: a count whose window depends on this lap's own time, such as the car's count two laps on, isn't a valid placebo. The far-window count is the one to use.

---

## D-024: Layer 2 closes with traffic figures per class pair, and Le Mans kept apart

*2026-10-24*

What goes forward to the simulator from Layer 2:

- **Two-class races (18):** the within-stint association per car for each direction. Hypercar with GT3 cars ahead is 0.37 s (0.33 to 0.41), and GT3 with Hypercars behind is 0.18 s (0.16 to 0.20), using the past-only window (E-013, E-014). The race bootstrap draws carry the parameter uncertainty.
- **Le Mans:** per-pair figures from 2025 and 2026 only (E-015). Two of the six pairs depend on the slow-lap rule, and 2024 is left out as wet and drying.

Each figure is labelled INFERRED, an association with a reconstructed count, never a cost per pass (D-004). They aren't pooled across Le Mans and the other races (D-009), because their windows differ.

Two gaps from E-015 get their own work, not more modelling here. Slow zones aren't in the flag column, and drying-track laps aren't flagged. Both bias which laps count as clean, at Le Mans most of all. A hierarchical traffic model is deferred until the simulator shows that the traffic term's uncertainty matters to a decision.

---

## D-025: Field-wide slow periods join the clean-lap rules

*2026-10-24*

A lap is left out of the clean set if its whole class ran more than 4% over that race's dry pace in the five minutes either side (`is_field_slow`, E-016). It catches drying track that the rain sensor misses, and slow zones and local yellows the flag column doesn't hold. It doesn't claim to know which. This is the eighth rule in D-012.

The 4% sits in a near-empty gap in the distribution, and it was chosen from that distribution, not from any model result. It removes 695 laps. Traffic figures from the 18 two-class races don't move. At Le Mans it fixes most of the loose-rule placebo failures from E-015.

---

## D-026: A live tool in Le Mans Ultimate is parked until after the optimiser

*2026-10-26*

Running the optimiser live inside Le Mans Ultimate is a possible later application, not part of the current plan. It comes only after Layers 3 to 5 are built and validated on real WEC data. If it happens, LMU data is game output, kept apart from the Al Kamel timing and never pooled with it, and parameters fitted on real races are ASSUMED in the game until re-estimated from LMU sessions. Until an LMU corpus is collected, questions about game behaviour are refusals or out of scope for the regulation assistant.

---

## D-027: Choosing a retriever gets a second test, on fresh questions, under a looser rule set after the first one failed

*2026-11-09*

E-017's result stands: the hybrid was not shown better than BM25 (5 wins to 1, p = 0.22), and BM25 stays the default until E-019 has run.

- **E-017 set the rule for choosing the default, and the hybrid failed it, so BM25 stayed.** After seeing that result I judged the rule too strict for a low-stakes choice. Given 6 disagreements, passing needed 6 to 0: a 12% chance if the hybrid truly wins 70% of disagreements, 33% at 83%, 53% at 90%. That judgement came after the failure, so this is a post-hoc change of threshold and carries that weakness.
- **"Not shown better" was never evidence for BM25.** It's a statement about the burden of proof. Only the vague set's 3 to 1 is fully untouched by the choice to run these tests.
- **This departs from the baseline rule in `scientific-method.md`, which would keep BM25.** It's a one-off exception, made after the result was known, and the rule itself is unchanged. The reason for the exception is cost. No parameters were fitted to this corpus. The configuration uses defaults that were never varied, so its sensitivity to them is UNKNOWN. The hybrid fuses BM25's ranking with the embedding ranking, and it can demote a BM25 hit (v23).
- **The cost, measured** (`scripts/measure_retrieval_cost.py`, one laptop, 40 questions): a median query of about 26 ms against 2 ms, and 2 s to load the model against 0.07 s for BM25. Latency is immaterial next to an LLM call. The real costs are 74 MB of `onnxruntime`, a 64 MB model fetched over the network on first use, 26 of 855 chunks truncated at the model's limit, and rerunning E-010, E-012 and E-018.
- **So the new rule is E-019, fixed before its questions exist.** E-017 itself says a future rule should be tested on a set that played no part in proposing it. The new rule is E-017's condition 1 on fresh data, with the significance leg dropped and a minimum number of disagreements added.
- **Pooling all three sets is not used as evidence.** It gives 8 wins to 1 (p = 0.04), but the original set is the one whose misses motivated trying embeddings, and E-017 fixed its pool without it.
- **Whichever way E-019 goes, the wording stays "not shown better".** A switch would rest on low cost and a favourable direction, never on a claim of superiority.

"Modern" isn't an argument in either direction. On the 6 sim-worded questions in E-017 the hybrid and BM25 each found 4 but not the same 4 (the hybrid gained v27 and lost v23), and embeddings alone found 3. So nothing yet shows that embeddings help that wording (n = 6, one slice of many, description only).

---

## D-028: The project is described as a DAG, and an orchestrator stays out

*2026-11-09*

`lineage.py` declares what each step reads and writes, and reads the import graph from the code. Tests hold both to the repo: no cycles, every named file and function exists, every listed library is imported by that step, and every Python file has a place. A diagram drawn by hand goes out of date, and this one fails CI first.

It's a description and doesn't execute anything. Layer 1 is close to a straight line that takes under 20 seconds, runs on one machine and has no schedule, so Airflow or Dagster would add a scheduler with nothing to schedule. The stdlib's `graphlib` does the cycle check. If the pipeline ever needs scheduling, retries or partial reruns, the declared steps are what would move over.

The same test enforces one rule that was only written down before: no numerical module may import the LLM layer (`rag.md`). The module list already includes `simulator` and `optimiser`, so the boundary holds from their first commit.

---

## D-029: The hybrid becomes the default retriever, once the answer eval has run on it

*2026-11-09 · from E-019*

E-019's rule was met: 5 questions differ at the top 5 and the hybrid wins 4 of them. So the hybrid replaces BM25 as the default. This is the outcome of a decision rule that was set after E-017 failed (D-027), and the sign test on the same comparison gives p = 0.375, so the wording stays "chosen by the rule, not shown better". On the 22 questions with a single gold article the split was 3 to 0, below the rule's gate of 4.

The switch isn't made until the answer eval has run on the fresh questions with the hybrid, because the answer figures so far were all measured on BM25. `fastembed` moves from the comparison only to the answering path at that point.

---

## D-030: New races come in by one command, and reported results stay on a fixed list

*2026-11-09*

`python scripts/ingest.py` finds race and free-practice files the public listing has and the disk doesn't, checks them, records their provenance and rebuilds the tables. A race that's still running is left out.

Every result reported up to E-019 used 21 races. They're now named in `CORPUS_V1`, and the traffic scripts filter to that list, so a new race can't quietly change a published number. After adding Fuji, Barcelona and Monza 2026, all 179,259 laps of those 21 races were identical to the earlier table.

The ingest writes 2026 into the tables but doesn't analyse it. 2026 stays sealed for Layer 3 (fit on 2024, check on 2025), and the three new races join the test.

---

## D-031: How Layer 3 is validated, agreed before anything is fitted

*2026-11-09 · design agreed, E-020 not yet written*

**Which data sees what:** fit on 2024, check on 2025, refit on 2024 and 2025, and only then open 2026 once. 2026 stays sealed until the simulator's final test.

**Rule changes that break the assumption that seasons are alike,** from comparing the regulations and not the 2026 results:

| Rule | Change | Consequence |
|---|---|---|
| LMGT3 dry tyres (6h / 8h / 10h) | 18 / 26 / 32 in 2024 and 2025, 24 / 32 / 40 in 2026 | 2026 LMGT3 is declared a known rule break and reported separately. If the model fails there, that's a finding, with no adjustment afterwards |
| Hypercar dry tyres | Unchanged | Expected to carry over |
| Virtual Safety Car | Absent in 2024, present from 2025 | Mainly Layer 4. The pit entry stays open under it |
| Maximum driving time | Penalty dropped after 2024 | Minor |
| Pit lane limit and stop procedure | 60 km/h throughout, procedure text nearly unchanged | Pit loss should carry over better |

Balance of Performance sets refuelling time per event and those documents aren't collected, so an unchanged rulebook doesn't prove conditions were the same. 2024 against 2025 is compared as a stability check on open data.

**2026 is reported in two groups, fixed in advance:** six races at circuits in the fit data (Imola, Spa, Le Mans, Sao Paulo, COTA, Fuji), and Barcelona and Monza as a new-circuit test. Barcelona isn't in 2024 or 2025 at all and the only Monza file is from 2023, so a per-circuit pit loss can't exist for them.

**Practice as a predictor of race pace.** Practice is known before the race, so it can't leak the result. E-020 compares three predictors of each race's clean pace, by class:

1. the same circuit's race pace the previous season, where there is one;
2. this weekend's practice plus a class offset learned from other races;
3. raw practice with no offset, as the baseline.

Offsets are learned on 2024 and each 2025 race is predicted all three ways. That's about 16 race-class comparisons (8 races, 2 main classes), enough to show a clear gap and not a small one. Barcelona and Monza only have the practice routes, so they test whether offsets carry to new circuits. What counts as a clean practice lap is fixed in E-020 before any result.

**To record in E-020:** while planning, 2026 median `PIT_TIME_S` and stop counts by class were printed. It's a small look at the sealed year.

**Before 2026 is opened:** check Monza's classification (12 of 27 finishing positions match on a file one day old, and 5 cars have time differences), and check whether the 2026 regulations were revised after the calendar changed (the corpus has `v1.2`).

**Before the simulator's final test:** the traffic result used all 18 non-Le Mans races including 2026, so it must be refitted on 2024 and 2025 or that test won't be clean.

---

## Tools

The rule of thumb is to use a few tools properly rather than a lot of them badly. A tool comes in when a real need shows up.

**In use:** Python, pandas, pytest, Git, GitHub Actions, Parquet (pyarrow), DuckDB, Pandera, pypdf (regulation text, D-018), fastembed (embedding comparison only, D-020).

**Coming when needed:** statsmodels and SciPy for the mixed-effects and bootstrap work, Matplotlib for figures, then Streamlit and Docker at the end.

**Only if something calls for it:** Polars, FastAPI, scikit-learn or XGBoost as a comparison to a simpler baseline, a vector store for retrieval, Ruff.

**Staying away from for now:** orchestration frameworks like Dagster or Prefect, Great Expectations (Pandera covers it), deep learning, cloud deployment, Kubernetes, and agent frameworks like LangChain. Direct tool calls against a fixed schema are easier to test and easier to explain.
