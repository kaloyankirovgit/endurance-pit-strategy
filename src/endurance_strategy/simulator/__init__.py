"""Layer 4: a lap-by-lap race simulator for one car (D-034, E-022).

The five parts are kept apart, as `.claude/rules/simulation.md` asks:
1. state transition: `engine.step`, deterministic given its inputs;
2. stochastic sampling: `engine.Randomness` and `engine.draw_cautions`, the only places randomness enters;
3. strategy action: `engine.decide`, from the planned stints;
4. search: `compare.py`, a small fixed comparison for now (Layer 5 is the optimiser);
5. evaluation: `compare.py` and `replay.py`.
Legality is checked first and separately in `feasibility.py` (D-006).
"""
