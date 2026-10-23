# Endurance Pit Strategy Planner

In a six or twenty-four hour race a team has to decide when to stop and who drives next, all while guessing how much time the slower cars in the other class are going to cost them. Most of that is judgement. I wanted to see how far I could get with real timing data and some honest statistics.

This repo is that attempt. It starts from the public FIA WEC lap timing and works towards a race simulator that can compare pit strategies.
The question I'm working towards:

> For a given car, circuit and race length, when should the team pit? Once driver pace, stint length, pit losses, traffic from the other class and the odd safety car are accounted for and how sure can we be about that answer?

## Where it's at

Early. The data side is in place and tested, and nothing is modelled yet.

What works right now:

- **One command builds everything**
  - `python -m endurance_strategy.pipeline` takes the raw race and weather files to a validated lap table plus stint and pit-stop tables, in Parquet, in about 13 seconds.
- **21 races from 2024 to 2026**
  - 179,259 laps from 833 car entries, split into 10,577 stints. 138,884 laps pass the clean-lap rules.
- **Pit stops and stints**
  - In-laps, out-laps and driver changes are flagged, and garage visits are kept apart from normal stops.
- **Weather on every lap**
  - Joined by the time of day rather than the race clock, because the race clock stops during red flags. At Spa 2024 that would have put the weather two hours out.
- **Race order and gaps**
  - Rebuilt at every timing-line crossing in DuckDB SQL, including the gap to the car ahead on track and its class. Every car's lap count and finishing time were checked against the official classification. They match apart from 51 cars, whose differences fit post-race penalties.
- **An eval for the AI review agent**
  - 16 synthetic write-ups with planted flaws and clean controls, run headless through Claude Code and scored against labels. It caught 11 of the 12 planted flaws. See [`evals/statistical_reviewer/`](evals/statistical_reviewer/).
- **Regulation retrieval**
  - The 2024 to 2026 sporting regulations, split into article-level chunks with season and page, searched with BM25. It finds the right 2026 clause in the top 5 for 24 of 30 hand-written questions. See [`evals/regulations/`](evals/regulations/).
- **100 tests on synthetic data**
  - They run in GitHub Actions on every push, with no real data needed.

The full log of what's been tried is in [`docs/EXPERIMENT_LOG.md`](docs/EXPERIMENT_LOG.md), and the reasoning behind the bigger choices is in [`docs/DECISIONS.md`](docs/DECISIONS.md).

## The plan

The build goes in layers. Each one has to work before the next one leans on it.

1. **Data pipeline**
   - Raw files to clean, validated tables (Parquet and DuckDB).
2. **Race order and traffic**
   - Rebuild who was where on track, then look at how lap times change when a faster car is working through slower traffic.
3. **Pace, stints and pit loss**
   - How pace fades through a stint, and what a stop actually costs.
4. **Simulator**
   - A lap-by-lap race model, deterministic first, then with randomness added one piece at a time and checked against real races.
5. **Optimiser**
   - Search the legal pit windows and compare strategies with intervals rather than single numbers.
6. **Regulation assistant**
   - An LLM that can look up the sporting regulations, call the simulator as a tool and explain the result with citations. It explains the answer but never makes the numbers up.

Reinforcement learning is a maybe for the very end, and only if the simulator holds up against real races first. An RL agent trained on a bad simulator just learns the simulator's mistakes.

## A few things I'm being careful about

- **Timing data can't see overtakes.** There's no GPS here, just line crossings and sector times. So the traffic work looks at inferred exposure to slower cars and the lap time that goes with it, not individual passes.
- **Fuel and tyres can't be separated.** Both get worse as a stint goes on, and timing alone can't tell them apart. I model the combined stint effect and treat any split as an assumption.
- **The team's real strategy isn't the right answer.** They have telemetry and radio I don't. Comparing against it is context, not a score.
- **Laps aren't independent.** 179,259 laps sounds like a lot, but they come from 21 races and 833 car entries. Results get split by race (fit on 2024, validate on 2025, test on 2026), never by shuffling laps.
- **Outside Le Mans this is a two-class race.** Since 2024 the championship rounds are Hypercar and LMGT3 only, with LMP2 turning up at Le Mans alone. So I say two-class where that's what the data is.

## Running it

```bash
git clone https://github.com/kaloyankirovgit/endurance-pit-strategy.git
cd endurance-pit-strategy
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
git config core.hooksPath .githooks
pytest -q
```

The `git config` line turns on a pre-commit hook that stops anything git-ignored from being committed, which matters here because the timing data can't be shared.

The tests run on a small synthetic race in `tests/fixtures/`, so they don't need the real data.

## Getting the data

The timing data belongs to Al Kamel Systems and can't be redistributed, so none of it is in this repo. That covers the raw files and anything derived from them.

It's free to download for your own use from <https://fiawec.alkamelsystems.com/>. Pick a season and event, open the race session and grab the `23_Analysis_Race_Hour NN.CSV` file with the highest hour (it covers the whole race). Save it as `data/raw/wec/<YEAR>_<CIRCUIT>.CSV`, for example `2025_LE_MANS.CSV`, and then:

```python
from endurance_strategy.io.load import load_race_csv
from endurance_strategy.paths import race_path
from endurance_strategy.reconstruct.stints import add_stint_columns

laps = add_stint_columns(load_race_csv(race_path("2025_LE_MANS")))
```

More detail on the source, including a quirk where the site sometimes serves the wrong event, is in [`docs/research/data_sources.md`](docs/research/data_sources.md).

## How it's built

This project is built in close collaboration with Claude Code, Anthropic's coding agent. AI assistance runs through most of it, so it's worth saying plainly how that works.

- **Where Claude helps:** writing and editing the pipeline code, the tests and CI, the write-ups in `docs/`, and running the review agents and evals.
- **Where I come in:** I set the direction and the standards, and I review every change before it's committed. Every commit goes through me, and I'm accountable for what's in the repo.
- **How the work is kept honest:**
  - [`CLAUDE.md`](CLAUDE.md) and [`.claude/rules/`](.claude/rules/) set the standards Claude works to, from data licensing to how statistical results are allowed to be worded.
  - Review agents in [`.claude/agents/`](.claude/agents/) check code, data, statistics and the simulator before a result is reported. The statistical reviewer is itself evaluated against planted flaws in [`evals/`](evals/).
  - A commit hook blocks the licensed timing data from being committed, whether Claude or I run the commit (D-016).

The setup is part of the project, not just tooling around it. A lot of the work here is about running an AI-assisted workflow where the checks are enforced rather than hoped for.

This is an independent project. It isn't affiliated with the FIA, the ACO, the WEC or Al Kamel Systems.
