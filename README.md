# Endurance Pit Strategy Planner

I've followed endurance racing for years, and the part I find most interesting isn't the driving — it's the pit wall. In a six or twenty-four hour race a team has to decide when to stop and who drives next, all while guessing how much time the slower cars in the other class are going to cost them. Most of that is judgement. I wanted to see how far I could get with real timing data and some honest statistics.

This repo is that attempt. It starts from the public FIA WEC lap timing and works towards a race simulator that can compare pit strategies — with proper uncertainty on the answer, not just a single number.

The question I'm working towards:

> For a given car, circuit and race length, when should the team pit — once driver pace, stint length, pit losses, traffic from the other class and the odd safety car are accounted for — and how sure can we be about that answer?

## Where it's at

Early. The data side is in place and tested, and nothing is modelled yet.

What works right now:

- A loader for the WEC race CSVs that deals with the quirks of the source format — a BOM, leading spaces in some headers, two different duration formats and car numbers like `007` that must stay strings.
- Structural checks across all 21 races from 2024 to 2026 (179,259 laps). Every one comes back clean, and I deliberately broke each check to prove it would actually catch a fault — a zero from a check that can't fail doesn't mean much.
- Pit stops and stints rebuilt from the timing data. The source never says "this is an in-lap", so I worked it out: the `B` marker is the lap into the pits and `PIT_TIME` sits on the lap out. That gives 10,577 stints across the corpus, and every one of the 3,478 driver changes lands on an out-lap.
- A clean-lap filter for pace modelling. 139,283 laps (78%) make it through, and I checked how much that number moves as the rules change — about 5% between the strictest and loosest settings.

The full log of what's been tried is in [`docs/EXPERIMENT_LOG.md`](docs/EXPERIMENT_LOG.md), and the reasoning behind the bigger choices is in [`docs/DECISIONS.md`](docs/DECISIONS.md).

## The plan

The build goes in layers — each one has to work before the next one leans on it.

1. **Data pipeline** — raw files to clean, validated tables (Parquet and DuckDB). *In progress.*
2. **Race order and traffic** — rebuild who was where on track, then look at how lap times change when a faster car is working through slower traffic.
3. **Pace, stints and pit loss** — how pace fades through a stint, and what a stop actually costs.
4. **Simulator** — a lap-by-lap race model, deterministic first, then with randomness added one piece at a time and checked against real races.
5. **Optimiser** — search the legal pit windows and compare strategies with intervals rather than single numbers.
6. **Regulation assistant** — an LLM that can look up the sporting regulations, call the simulator as a tool and explain the result with citations. It explains the answer — it never makes the numbers up.

Reinforcement learning is a maybe for the very end, and only if the simulator holds up against real races first. An RL agent trained on a bad simulator just learns the simulator's mistakes.

## A few things I'm being careful about

- **Timing data can't see overtakes.** There's no GPS here, just line crossings and sector times. So the traffic work looks at inferred exposure to slower cars and the lap time that goes with it — not individual passes.
- **Fuel and tyres can't be separated.** Both get worse as a stint goes on, and timing alone can't tell them apart. I model the combined stint effect and treat any split as an assumption.
- **The team's real strategy isn't the right answer.** They have telemetry and radio I don't. Comparing against it is context, not a score.
- **Laps aren't independent.** 179,259 laps sounds like a lot, but they come from 21 races and 833 car entries. Results get split by race (fit on 2024, validate on 2025, test on 2026), never by shuffling laps.
- **Outside Le Mans this is a two-class race.** Since 2024 the championship rounds are Hypercar and LMGT3 only — LMP2 turns up at Le Mans alone. So I say two-class where that's what the data is.

## Running it

```bash
git clone https://github.com/kaloyankirovgit/endurance-pit-strategy.git
cd endurance-pit-strategy
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

The tests run on a small synthetic race in `tests/fixtures/`, so they don't need the real data.

## Getting the data

The timing data belongs to Al Kamel Systems and can't be redistributed, so none of it is in this repo — not the raw files and not anything derived from them.

It's free to download for your own use from <https://fiawec.alkamelsystems.com/>. Pick a season and event, open the race session and grab the `23_Analysis_Race_Hour NN.CSV` file with the highest hour (it covers the whole race). Save it as `data/raw/wec/<YEAR>_<CIRCUIT>.CSV`, for example `2025_LE_MANS.CSV`, and then:

```python
from endurance_strategy.io.load import load_race_csv
from endurance_strategy.paths import race_path
from endurance_strategy.reconstruct.stints import add_stint_columns

laps = add_stint_columns(load_race_csv(race_path("2025_LE_MANS")))
```

More detail on the source, including a quirk where the site sometimes serves the wrong event, is in [`docs/research/data_sources.md`](docs/research/data_sources.md).

## How it's built

I'm building this with Claude Code as a pair programmer. The rules and review agents it works with live in [`.claude/`](.claude/) and [`CLAUDE.md`](CLAUDE.md) — they're part of the project too, since a lot of what I'm learning is how to run a workflow like this well.

This is an independent project. It isn't affiliated with the FIA, the ACO, the WEC or Al Kamel Systems.
