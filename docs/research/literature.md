# Reading list

Papers and code I want to read before designing the parts they cover. Nothing here has been read properly yet — each entry just says why it's on the list. Once I've read one, I'll note what it actually changes for this project, or why it doesn't.

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

**Heilmeier et al. (2020), "Application of Monte Carlo Methods to Consider Probabilistic Effects in a Race Simulation for Circuit Motorsport".** [doi:10.3390/app10124229](https://doi.org/10.3390/app10124229). The closest thing to what I want the simulator to be — random lap times and pit stop variation, with safety cars on top. The one to read first.

**TUMFTM race-simulation.** <https://github.com/TUMFTM/race-simulation>. The code behind the paper above. It's built for F1, so I'll borrow ideas, not structure. Need to check the licence before reusing anything.

**Heilmeier et al. (2020), "Virtual Strategy Engineer".** [doi:10.3390/app10217805](https://doi.org/10.3390/app10217805). Neural networks making pit decisions on top of a race sim. Mostly interesting for how they represent the race state.

**Fieni et al. (2025), "Towards Learning-Based Formula 1 Race Strategies".** [arXiv:2512.21570](https://arxiv.org/abs/2512.21570). Compares mixed-integer optimisation with RL. Relevant to why I'm doing plain search first (D-007).

**Sasikumar, Leema & Balakrishnan (2025), "Data-driven pit stop decision support for Formula 1".** [Frontiers in AI](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1673148/full). About 100,000 laps and 3,000 pit stops. A useful comparison for scale — but laps from the same race aren't independent, so a big lap count isn't a big sample.

**Boettinger & Klotz (2023), "Mastering Nordschleife".** [arXiv:2306.16088](https://arxiv.org/abs/2306.16088). RL strategy for GT endurance racing. Closer to WEC than the F1 papers.

**Thomas et al. (2026), "Race Strategy Reinforcement Learning".** [doi:10.1007/s10994-026-07081-3](https://link.springer.com/article/10.1007/s10994-026-07081-3). RL pit strategy in F1. Only relevant if I ever get to the RL stretch goal.

## Gaps

I haven't found anything on traffic between classes specifically — almost all of this is single-class F1. If there really isn't much out there, that makes the traffic work the most original part of the project. I'm also looking for anything on picking out traffic effects from timing data alone, without GPS.
