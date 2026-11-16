"""Comparing strategies on the same simulated races (common random numbers).

Each seed is one simulated race. Every strategy runs on every seed, so the difference between two
strategies isn't swamped by race-to-race luck. Results are SIMULATED and are not a prediction of a real race.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from endurance_strategy.simulator.engine import CarParams, Randomness, Strategy, simulate


def run_strategies(params: CarParams, strategies: dict[str, Strategy], randomness: Randomness | None,
                   seeds: range | list[int]) -> pd.DataFrame:
    rows = []
    for seed in seeds:
        for name, strategy in strategies.items():
            result = simulate(params, strategy, randomness, seed=seed)
            rows.append({"seed": seed, "strategy": name, "laps": result.laps, "finish_time_s": result.finish_time_s,
                         "stops": result.stops, "extra_stops": result.extra_stops, "deferred_laps": result.deferred_laps,
                         "cautions": len(result.cautions), "lap_times": result.records["race_time_s"].to_numpy()})
    return pd.DataFrame(rows)


def time_at_lap(runs: pd.DataFrame, lap: int) -> pd.Series:
    return runs["lap_times"].map(lambda times: float(times[lap - 1]) if len(times) >= lap else np.nan)


def paired_summary(runs: pd.DataFrame, baseline: str, lap: int) -> dict:
    """Per strategy against `baseline`: the time to complete `lap` laps, difference per seed.

    The quantiles describe outcome randomness for a car with these parameters. They aren't a confidence
    interval for a real effect. `lap` should be one every run reaches; any seed that doesn't is counted.
    """
    runs = runs.assign(time_at=time_at_lap(runs, lap))
    wide = runs.pivot(index="seed", columns="strategy", values="time_at")
    laps = runs.pivot(index="seed", columns="strategy", values="laps")
    out = {}
    for name in wide.columns:
        diff = (wide[name] - wide[baseline]).dropna()
        out[name] = {
            "mean_time_at_lap_s": float(wide[name].mean()),
            "difference_vs_baseline_s": {"mean": float(diff.mean()), "p05": float(diff.quantile(0.05)), "p50": float(diff.median()),
                                         "p95": float(diff.quantile(0.95))},
            "share_faster_than_baseline": float((diff < 0).mean()),
            "laps": {"mean": float(laps[name].mean()), "p05": float(laps[name].quantile(0.05)), "p95": float(laps[name].quantile(0.95))},
            "mean_stops": float(runs.loc[runs["strategy"] == name, "stops"].mean()),
            "mean_extra_stops": float(runs.loc[runs["strategy"] == name, "extra_stops"].mean()),
            "seeds": int(diff.size), "seeds_dropped": int(len(wide) - diff.size),
        }
    return out
