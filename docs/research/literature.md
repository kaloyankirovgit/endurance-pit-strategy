# Reading list

Papers and code I want to read before designing the parts they cover. The list below says why each is on it. The Layer 3 section further down records what has been read so far and what it changed.

| When | Source | For |
|---|---|---|
| Before the simulator | Heilmeier et al. 2020, Monte Carlo race simulation | How to add randomness to a race sim |
| Before the simulator | TUMFTM race-simulation repo | A working reference implementation |
| Before the optimiser | Heilmeier et al. 2020, Virtual Strategy Engineer | How a strategy decision can be framed |
| Before the optimiser | Fieni et al. 2025 | Optimisation versus RL for race strategy |
| For validation design | Sasikumar et al. 2025 | How others have split train and test |
| Stretch | Boettinger & Klotz 2023 | GT endurance, closest to WEC |
| Stretch | Thomas et al. 2026 | RL for pit strategy |

## Notes on each

**Heilmeier et al. (2020), "Application of Monte Carlo Methods to Consider Probabilistic Effects in a Race Simulation for Circuit Motorsport".** [doi:10.3390/app10124229](https://doi.org/10.3390/app10124229). The closest thing to what I want the simulator to be, with random lap times and pit stop variation, with safety cars on top. The one to read first.

**TUMFTM race-simulation.** <https://github.com/TUMFTM/race-simulation>. The code behind the paper above. It's built for F1, so I'll borrow ideas, not structure. Need to check the licence before reusing anything.

**Heilmeier et al. (2020), "Virtual Strategy Engineer".** [doi:10.3390/app10217805](https://doi.org/10.3390/app10217805). Neural networks making pit decisions on top of a race sim. Mostly interesting for how they represent the race state.

**Fieni et al. (2025), "Towards Learning-Based Formula 1 Race Strategies".** [arXiv:2512.21570](https://arxiv.org/abs/2512.21570). Compares mixed-integer optimisation with RL. Relevant to why I'm doing plain search first (D-007).

**Sasikumar, Leema & Balakrishnan (2025), "Data-driven pit stop decision support for Formula 1".** [Frontiers in AI](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1673148/full). About 100,000 laps and 3,000 pit stops. A useful comparison for scale, but laps from the same race aren't independent, so a big lap count isn't a big sample.

**Boettinger & Klotz (2023), "Mastering Nordschleife".** [arXiv:2306.16088](https://arxiv.org/abs/2306.16088). RL strategy for GT endurance racing. Closer to WEC than the F1 papers.

**Thomas et al. (2026), "Race Strategy Reinforcement Learning".** [doi:10.1007/s10994-026-07081-3](https://link.springer.com/article/10.1007/s10994-026-07081-3). RL pit strategy in F1. Only relevant if I ever get to the RL stretch goal.

## Read for Layer 3: what counts as a usable lap, and what a stop costs (2026-11-09)

The question was which laps other people use to estimate degradation and pit loss from timing data, and whether that changes E-020. I read the sections on lap selection and pit modelling in each. Almost all of this is single-class F1, where tyre age and compound are published, so the methods that use them don't transfer.

**Cappello & Hoegh (2025), "A State-Space Approach to Modeling Tire Degradation in Formula 1 Racing".** [arXiv:2512.00640](https://arxiv.org/abs/2512.00640). Preprint. Bayesian state-space model on FastF1 lap times.
- Data and cleaning: one driver in one race (Hamilton, Austria 2025), chosen for having no safety car and clean air. Cleaning only removed pit entry and exit laps. Fuel is assumed: 110 kg falling linearly to zero.
- Limits it states: safety-car laps should suspend degradation, and being held up behind a car adds lap time that isn't degradation.
- Changes here: supports E-020's all-green and traffic sensitivities. One race can't speak to generalisation, and an assumed fuel curve doesn't separate fuel from tyres in our data either (D-005).

**Santillana (2026), "Pitwall".** [arXiv:2607.06495](https://arxiv.org/abs/2607.06495). Preprint, single author. F1 Monte Carlo engine calibrated on 126 races with 2025 to 2026 held out.
- Lap selection: degradation is fitted per race and compound on green laps only, with safety-car, VSC, in-laps and out-laps excluded.
- Useful: it says raw fitted slopes mix tyre wear with fuel burn-off and track evolution, that the blended slope is often negative, and that an optimiser will exploit a negative slope with impossibly long stints. It also found that leaving a cold out-lap penalty out of the simulator biased it towards pitting.
- Doesn't transfer: it adds back a calibrated fuel effect and clamps tyre wear to a bounded range. That is an assumption we would have to label ASSUMED (D-005).
- Changes here: warm-up is measured as its own quantity, and the simulator must respect the support limit. E-020 expects that a negative slope may be real.

**Joshi (2026), "The Persistence of the Dirty Air Penalty".** [arXiv:2608.03192](https://arxiv.org/abs/2608.03192). Preprint. F1, OLS with standard errors clustered by race, and causal forests.
- Lap selection: a green-flag filter, which it reports removed more of 2021 than later seasons because 2021 had more disruption.
- Doesn't transfer: it fits tyre life and lap number jointly, which needs published tyre age, and it reads lap number as fuel.
- Changes here: E-020 reports the share of laps each flag removes, by season.

**Fieni et al. (2025), "Benchmarking Learning-Based Formula 1 Race Strategies" (first version titled "Towards Learning-Based Formula 1 Race Strategies").** [arXiv:2512.21570](https://arxiv.org/abs/2512.21570). Preprint. Simulated F1 strategy, not an analysis of timing data.
- Useful: it models a normal lap, an in-lap, an out-lap and an out-in lap (two stops on consecutive laps) as four separate cases, and notes the out-lap starts at pit-lane speed. Its nominal lap of 93.1 s is a model output, not a measurement.
- Changes here: a lap that is both an out-lap and an in-lap would distort in-lap + out-lap, so `pit_events` gives those stops their own status and no pit loss.

**Sasikumar, Leema & Balakrishnan (2025).** Queried for its lap filters rather than read in full, and the last 19,000 characters of the page weren't reached. It drops wet, intermediate and unknown tyres and describes no filter for in-laps, out-laps or safety-car laps, keeping track status as a feature. It holds out the last 8 races of 2024. So excluding pit and caution laps is common but isn't universal.

**Howson (2026), "How multi class traffic shapes WEC lap time".** [Motorsport Reports](https://motorsportreports.com/wec-how-multi-class-traffic-shapes-lap-time/). Conceptual article with no data. It takes the best clean lap in a stint as the reference. Not adopted: a best lap is a selected extreme, so losses measured against it come out too large. E-020 uses a median.

**Tried and not read.** Heilmeier et al. (2020, the MDPI page) and the TUM dissertation refused automated access. The Research Square preprint "Baseline-relative evaluation of lap-time and tyre-degradation models" returned only its title. None of them is cited for anything until read.

## Gaps

These Layer 3 searches found no open study fitting stint age from WEC timing data, and nothing supporting the 1.07 slow-lap ratio in particular.

I haven't found anything on traffic between classes specifically. Almost all of this is single-class F1. If there really isn't much out there, that makes the traffic work the most original part of the project. I'm also looking for anything on picking out traffic effects from timing data alone, without GPS.
