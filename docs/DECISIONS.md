# Decisions

The choices that shape the rest of the project, and why I made them. If one gets reversed, it stays here with a note pointing to whatever replaced it.

---

## D-001 — Where the project lives

*2026-09-22*

In `~/Projects/endurance-pit-strategy-planner` rather than Downloads or an iCloud folder. Downloads gets cleared out, and iCloud sync doesn't get on well with Git.

## D-002 — raw / interim / processed

*2026-09-22*

Data moves from `raw` to `interim` to `processed`. It's the same idea as the bronze/silver/gold layers people use in data engineering — the source is never touched, and every step after it is cleaner and built for something more specific. I went with the more common folder names so there's only one vocabulary.

## D-003 — Test fixtures go in `tests/fixtures/`

*2026-09-22*

Everything under `data/` is git-ignored so real timing data can't slip into a commit. Putting fixtures in `data/fixtures/` would mean punching a hole in exactly that rule. So fixtures live with the tests instead, and they're always synthetic.

## D-004 — Traffic is inferred exposure, not overtakes

*2026-09-22*

The timing data records when a car crosses a timing line — not where it is on track in between. An "overtake detector" built on that couldn't be checked against anything, because there's no ground truth. So the traffic model looks at when a car was likely running into slower traffic and how its lap times behaved, and says plainly that the exact pass isn't observed.

The 15-point Le Mans data (D-009) narrows *where* time was lost. It still doesn't see a pass, so this stands.

## D-005 — Fuel and tyres aren't separated

*2026-09-22*

Fuel burning off makes a car faster through a stint, tyres wearing makes it slower, and both happen as the stint goes on. Timing data alone can't tell those two apart. So I model one combined stint-age effect from the data. If the simulator needs separate fuel and tyre terms, they're labelled as assumptions and I test how sensitive the answer is to them.

This only changes if I find a source that actually measures fuel or tyre state.

## D-006 — Regulations are a separate check

*2026-09-22*

Legality gets checked before the simulator runs, by its own function that returns whether a strategy is allowed and which rules it breaks. The rules sit in a versioned table where every row cites a document and page — they change by season and sometimes by event, so they can't be hard-coded. This also gives the LLM layer a real job later on: pointing to the exact rule that ruled a strategy out.

## D-007 — Plain search before reinforcement learning

*2026-09-22*

The first optimiser is an exhaustive search over legal pit windows. It's easy to test, and it gives a baseline anything fancier has to beat. RL only comes in once the simulator has been checked against real races — otherwise it just learns the simulator's mistakes, and you can't tell which is to blame.

This carries over from my dissertation: tuning parameters and evaluating a policy are different jobs and need different data.

## D-008 — The LLM explains, it doesn't compute

*2026-09-22*

The language model can read the regulations, pick simulator inputs from a fixed schema, call the simulator and explain what came back — with citations. It can't change the numbers or decide pit timing in prose. Every number in an answer has to trace back to a tool call or a document. Without that line it's a chatbot with a racing theme.

## D-009 — Breadth first, with a Le Mans deep-dive

*2026-09-22*

The archive has 121 events at 3-sector resolution. Only Le Mans (2025 and 2026) and COTA 2026 have the finer 15-point timing.

Breadth helps generalisation — more races, more circuits. Depth helps with the traffic question, since finer timing makes it more likely the effect can be picked out at all. So I'm doing both: the pipeline and all the pace and pit modelling run across the full corpus, and the 15-point races become a separate traffic sub-study.

The two are never pooled into one number without an argument. A traffic effect found at Le Mans is a Le Mans result until something shows it transfers.

## D-010 — The corpus is 2024 to 2026 (21 races)

*2026-09-22*

| Option | Races | Circuits | Laps |
|---|---:|---:|---:|
| 2023–2026, everything | 28 | 11 | 236,738 |
| **2024–2026** | **21** | **8** | **179,259** |
| Le Mans only | 4 | 1 | 70,968 |

2023 is effectively a different championship. Its third class is LMGTE Am rather than LMGT3, and LMP2 ran the whole season. Mixing it in would mean an era adjustment in every model for six extra races. A clean 21-race set is easier to defend.

It also splits neatly by time — **fit on 2024 (8 races), validate on 2025 (8), test on 2026 (5)**. The 2023 files stay on disk for a later robustness check.

One consequence: 18 of the 21 races are two-class (Hypercar and LMGT3), because LMP2 only races at Le Mans now. So I describe it as two-class wherever that's what the data is, and class-pair effects get estimated per pair.

## D-011 — How pits and stints are read from the timing

*2026-09-24*

The source has no in-lap or out-lap column. Working from the whole corpus (E-003):

- `CROSSING_FINISH_LINE_IN_PIT = B` is the **in-lap** — the lap that ends in the pit lane.
- `PIT_TIME` is on the **out-lap** — the lap after. It's time in the pit lane including the stop, not just time stationary.
- A new stint starts on each out-lap. The in-lap is the last lap of its stint.
- A lap-1 `PIT_TIME` is a pit-lane start, which is still stint 1.

This lives in `src/endurance_strategy/reconstruct/stints.py` and is pinned by tests. A few `PIT_TIME` values run to hours — cars parked in the garage — so pit loss and garage time will need separating before any pit-loss model.

## D-012 — What counts as a clean lap

*2026-09-24*

A lap feeds the pace model only if it's green at the line, not the first lap, not an in-lap or out-lap, not the lap right after a caution, has all its times, and is within 7% of the median clean lap for its class at that race. The numbers are in E-004.

Laps are flagged, never deleted. Each rule has its own column, so any model can use a different combination and say which it used. The 7% is a judgement call — about 5% of the usable count moves between 3% and 15% — so results that depend on it get checked at other thresholds.

## D-013 — Weather joining and garage visits

*2026-09-24*

Lap times get a UTC timestamp from `HOUR` (local wall clock), the race date and a per-circuit time zone — not from `ELAPSED`, which stops during red flags. Each lap takes the latest weather reading at or before it crossed the line, within five minutes. `RAIN` above 0 counts as wet, and wet laps are left out of the clean-lap set (so D-012 now has seven rules).

A stop is a garage visit if its `PIT_TIME` is over 3× the race median. The long stops under safety car stay as normal stops, because queueing at pit exit is part of what a stop costs. Evidence in E-005.

---

## Tools

The rule of thumb is to use a few tools properly rather than a lot of them badly. A tool comes in when a real need shows up.

**In use:** Python, pandas, pytest, Git, GitHub Actions.

**Coming when needed:** Parquet and DuckDB (Layer 1), Pandera for data contracts, statsmodels and SciPy for the mixed-effects and bootstrap work, Matplotlib for figures, then Streamlit and Docker at the end.

**Only if something calls for it:** Polars, FastAPI, scikit-learn or XGBoost as a comparison to a simpler baseline, a vector store for retrieval, Ruff.

**Staying away from for now:** orchestration frameworks like Dagster or Prefect, Great Expectations (Pandera covers it), deep learning, cloud deployment, Kubernetes, and agent frameworks like LangChain. Direct tool calls against a fixed schema are easier to test and easier to explain.
