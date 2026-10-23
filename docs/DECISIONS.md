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

## Tools

The rule of thumb is to use a few tools properly rather than a lot of them badly. A tool comes in when a real need shows up.

**In use:** Python, pandas, pytest, Git, GitHub Actions, Parquet (pyarrow), DuckDB, Pandera, pypdf (regulation text, D-018), fastembed (embedding comparison only, D-020).

**Coming when needed:** statsmodels and SciPy for the mixed-effects and bootstrap work, Matplotlib for figures, then Streamlit and Docker at the end.

**Only if something calls for it:** Polars, FastAPI, scikit-learn or XGBoost as a comparison to a simpler baseline, a vector store for retrieval, Ruff.

**Staying away from for now:** orchestration frameworks like Dagster or Prefect, Great Expectations (Pandera covers it), deep learning, cloud deployment, Kubernetes, and agent frameworks like LangChain. Direct tool calls against a fixed schema are easier to test and easier to explain.
