# Literature

Reading notes for the papers and repositories that inform design decisions.

**Read strategically.** The purpose is to make better architecture and modelling decisions, not to reproduce an academic paper line for line. A paper earns an entry here when it has changed, or explicitly failed to change, something about this project.

**Nothing below has been read yet.** The entries are stubs recording why each source is on the list, taken from `Strategy.md` §25. Citation details are as given in the specification and should be verified against the source on first read.

---

## Template

```
## Short citation

PAPER:              Full citation, DOI or arXiv ID, link.
DATE READ:
RESEARCH QUESTION:  What the authors set out to answer.
METHODOLOGY:        How they did it — data, model, evaluation.
USEFUL RESULT:      The specific finding or technique worth having.
LIMITATION:         What the work does not establish; where it would not transfer.
RELEVANCE HERE:     What this changes in our design — a decision, a method, or an
                    argument for not doing something. "Interesting" is not relevance.
```

---

## Reading queue

Ordered by when the project needs them.

| Priority | Source | Needed for |
|---|---|---|
| 1 | Heilmeier et al. 2020 — Monte Carlo race simulation | Layer 4 simulator design |
| 2 | TUMFTM race-simulation repository | Layer 4 architecture reference |
| 3 | Heilmeier et al. 2020 — Virtual Strategy Engineer | Layer 4–5 state and decision representation |
| 4 | Fieni et al. 2025 | Layer 5 optimisation formulation |
| 5 | Sasikumar et al. 2025 | Sample-size and validation-design comparison |
| 6 | Boettinger & Klotz 2023 | GT endurance specifics; stretch RL reference |
| 7 | Thomas et al. 2026 | Stretch RL reference only |

---

## TUMFTM race-simulation (repository)

SOURCE: <https://github.com/TUMFTM/race-simulation>
DATE READ: —
WHY IT IS HERE: Reference implementation of lap-discrete race simulation with probabilistic effects. Useful for simulator architecture, the separation of state transition from stochastic sampling, and race-strategy formulation.
CAUTION: Do not copy the architecture blindly — it is built for a different series with different data availability. This project's model must fit WEC's multi-class structure and the fields the timing data actually provides. **Check the repository licence before reusing code or substantial implementation patterns.**
STATUS: Not read.

---

## Heilmeier et al. (2020) — Virtual Strategy Engineer

PAPER: "Virtual Strategy Engineer: Using Artificial Neural Networks for Making Race Strategy Decisions in Circuit Motorsport". DOI: [10.3390/app10217805](https://doi.org/10.3390/app10217805)
DATE READ: —
WHY IT IS HERE: How a race-strategy decision can be formalised — state representation, decision-making architecture, and the relationship between a learned strategy model and the underlying race simulator.
STATUS: Not read.

---

## Heilmeier et al. (2020) — Monte Carlo race simulation

PAPER: "Application of Monte Carlo Methods to Consider Probabilistic Effects in a Race Simulation for Circuit Motorsport". DOI: [10.3390/app10124229](https://doi.org/10.3390/app10124229)
DATE READ: —
WHY IT IS HERE: The closest reference for Layer 4. Probabilistic lap times, pit-stop variability, FCY and safety-car modelling, and the argument for evaluating robustness rather than a single deterministic optimum.
STATUS: Not read. **Read before designing the simulator's stochastic components.**

---

## Boettinger & Klotz (2023) — Mastering Nordschleife

PAPER: arXiv:[2306.16088](https://arxiv.org/abs/2306.16088)
DATE READ: —
WHY IT IS HERE: Race simulation for GT endurance racing specifically — fuel, tyre and pit strategy, observation and reward design, and the stated limitations of simulation-based strategy learning. The endurance context is closer to this project than the F1 literature.
STATUS: Not read.

---

## Fieni et al. (2025) — Towards Learning-Based Formula 1 Race Strategies

PAPER: arXiv:[2512.21570](https://arxiv.org/abs/2512.21570)
DATE READ: —
WHY IT IS HERE: Joint energy, tyre and pit-stop strategy; mixed-integer optimisation; an RL-versus-optimisation comparison. Directly relevant to the argument in DECISIONS D-007 that an optimisation baseline should precede RL.
STATUS: Not read.

---

## Thomas et al. (2026) — Race Strategy Reinforcement Learning

PAPER: "Race Strategy Reinforcement Learning: Optimising Pitstop Strategy with Emergent Tactics in Formula One". *Machine Learning*, 2026. DOI: [10.1007/s10994-026-07081-3](https://link.springer.com/article/10.1007/s10994-026-07081-3)
DATE READ: —
WHY IT IS HERE: RL for race strategy, multi-agent interaction, cross-circuit generalisation and explainability.
CAUTION: **Stretch reference.** Its presence on this list is not a reason to implement RL. See DECISIONS D-007.
STATUS: Not read.

---

## Sasikumar, Leema & Balakrishnan (2025) — Pit-stop decision support for F1

PAPER: "Data-driven pit stop decision support for Formula 1 using deep learning models". *Frontiers in Artificial Intelligence*, 2025. DOI: [10.3389/frai.2025.1673148](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1673148/full)
DATE READ: —
WHY IT IS HERE: A comparison point for time-series modelling, pit-stop prediction, class imbalance and train/test design at lap-level resolution.
CAUTION: The paper reports roughly 99,928 lap observations and about 3,131 pit-stop instances before class balancing. **This is a scale reference, not a sample-size justification.** Those laps are clustered within races, cars and drivers, and adjacent laps are temporally correlated — the effective sample size for most questions is far smaller than the row count. Do not cite this figure as evidence that a given number of laps confers statistical validity. See `.claude/rules/statistics.md`.
STATUS: Not read.

---

## Gaps in the reading list

Areas where a reference is wanted but none has been identified:

- Multi-class traffic effects specifically. The cited literature is predominantly single-class (F1). If no multi-class treatment exists, that is worth stating in the final report — it makes the traffic layer the novel part of this project rather than a reimplementation.
- Statistical identification of traffic effects from timing-only data, without positional telemetry.
- Endurance-specific driver-change and driving-time constraints in a strategy optimisation context.
