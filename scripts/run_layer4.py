#!/usr/bin/env python3
"""Layer 4, as registered in E-022: calibrate the simulator, replay real races, check its randomness, compare strategies.

Stages, run in order: `calibrate`, `replay`, `sanity`, `compare`. Only 2024 and 2025 are read, outside Le Mans.
Output stays local in reports/outputs, because it's derived from the timing data.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from endurance_strategy.models.pace import load_open_seasons
from endurance_strategy.paths import INTERIM_DIR, PROJECT_ROOT
from endurance_strategy.simulator import calibrate as cal
from endurance_strategy.simulator.compare import paired_summary, run_strategies, time_at_lap
from endurance_strategy.simulator.engine import Strategy, draw_race, simulate
from endurance_strategy.simulator.feasibility import check_strategy, even_strategy
from endurance_strategy.simulator.replay import replay, summarise

OUTPUT_DIR = PROJECT_ROOT / "reports" / "outputs"
FILES = {stage: OUTPUT_DIR / f"e022_{stage}.json" for stage in ("calibrate", "replay", "sanity", "compare")}
REPLAY_GATE_PCT = 0.5
DEMO_CIRCUIT, DEMO_CLASS = "SPA_FRANCORCHAMPS", "HYPERCAR"
DRIVERS = ("A", "B", "C")
SEED = 20261113
N_RACES = 2000


def load_laps() -> pd.DataFrame:
    laps = load_open_seasons(INTERIM_DIR / "laps.parquet", seasons=("2024", "2025"))
    return laps[~laps["event_key"].str.contains("LE_MANS")]


def write(stage: str, report: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {"timestamp_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), **report}
    FILES[stage].write_text(json.dumps(report, indent=1, default=lambda v: v.item() if isinstance(v, np.generic) else str(v)))
    print("written to", FILES[stage])


def read(stage: str) -> dict:
    if not FILES[stage].exists():
        raise SystemExit(f"run --stage {stage} first")
    return json.loads(FILES[stage].read_text())


def stage_calibrate() -> None:
    write("calibrate", cal.calibrate(load_laps()))


def stage_replay() -> None:
    calibration = read("calibrate")
    table = replay(load_laps(), calibration)
    summary = summarise(table)
    gate = summary["M3"]["median_abs_pct_over_races"] <= REPLAY_GATE_PCT
    write("replay", {"summary": summary, "gate_pct": REPLAY_GATE_PCT, "gate_passed": bool(gate),
                     "cars": table.drop(columns=[]).round(4).to_dict("records")})
    print(json.dumps(summary, indent=1), "gate passed:", gate)


def fewest_stops(params, drivers=DRIVERS, most: int = 40) -> int:
    for stops in range(1, most + 1):
        if check_strategy(params, even_strategy(params, stops, drivers)).ok:
            return stops
    raise SystemExit(f"no feasible even strategy with up to {most} stops")


def stage_sanity() -> None:
    """Simulated caution counts per race against the observed ones (E-022 Part C)."""
    calibration = read("calibrate")
    caution = calibration["caution"]
    observed = pd.DataFrame(caution["per_race"])
    out = {}
    six_hours = cal.car_params(calibration, DEMO_CIRCUIT, DEMO_CLASS)
    only_cautions = cal.randomness(calibration, DEMO_CLASS, lap_noise=False, pit_spread=False)
    simulated = [draw_race(only_cautions, six_hours, SEED + i).cautions for i in range(N_RACES)]
    for kind in ("SF", "FCY"):
        per_6h = observed[kind] / observed["hours"] * 6
        counts = np.array([sum(1 for e in race if e[2] == kind) for race in simulated])
        out[kind] = {"observed_per_6h": {"mean": float(per_6h.mean()), "variance": float(per_6h.var(ddof=1)), "races": int(len(per_6h)),
                                         "races_with_none": int((observed[kind] == 0).sum())},
                     "simulated_per_6h": {"mean": float(counts.mean()), "variance": float(counts.var(ddof=1))},
                     "median_duration_s": float(np.median(caution["durations_s"][kind]))}
    params = cal.car_params(calibration, DEMO_CIRCUIT, DEMO_CLASS)
    strategy = even_strategy(params, fewest_stops(params), DRIVERS)
    added = {}
    for label, kwargs in [("deterministic", None), ("lap_noise", dict(lap_noise=True, pit_spread=False, cautions=False)),
                          ("plus_pit_spread", dict(lap_noise=True, pit_spread=True, cautions=False)),
                          ("plus_cautions", dict(lap_noise=True, pit_spread=True, cautions=True)),
                          ("plus_slope_uncertainty", dict(lap_noise=True, pit_spread=True, cautions=True, slope_uncertainty=True))]:
        randomness = None if kwargs is None else cal.randomness(calibration, DEMO_CLASS, **kwargs)
        laps = [simulate(params, strategy, randomness, seed=SEED + i).laps for i in range(1 if kwargs is None else 500)]
        added[label] = {"laps_mean": float(np.mean(laps)), "laps_p05": float(np.quantile(laps, 0.05)), "laps_p95": float(np.quantile(laps, 0.95))}
    write("sanity", {"cautions": out, "one_source_at_a_time": added})
    print(json.dumps({"cautions": out, "one_source_at_a_time": added}, indent=1))


def demo_strategies(params) -> dict:
    """E-022 Part D: the fewest stops the energy limit allows, one more stop, and the same stops with drivers double-stinting."""
    k = fewest_stops(params)
    fewest = even_strategy(params, k, DRIVERS)
    double = tuple(DRIVERS[(i // 2) % len(DRIVERS)] for i in range(k + 1))
    return {"fewest_stops": fewest, "one_more_stop": even_strategy(params, k + 1, DRIVERS),
            "fewest_stops_double_stint_drivers": Strategy(stint_laps=fewest.stint_laps, drivers=double)}


def compare_once(calibration: dict, label: str, randomness_kwargs: dict, **param_overrides) -> dict:
    params = cal.car_params(calibration, DEMO_CIRCUIT, DEMO_CLASS, **param_overrides)
    strategies = demo_strategies(params)
    runs = run_strategies(params, strategies, cal.randomness(calibration, DEMO_CLASS, **randomness_kwargs),
                          range(SEED, SEED + N_RACES))
    lap = int(runs["laps"].min())  # a lap every simulated race reaches, so no slow races drop out
    summary = paired_summary(runs, "fewest_stops", lap)
    diffs = {name: (time_at_lap(runs[runs["strategy"] == name], lap).to_numpy()
                    - time_at_lap(runs[runs["strategy"] == "fewest_stops"], lap).to_numpy()) for name in strategies}
    return {"label": label, "lap_compared": lap, "strategies": {n: {"stint_laps": s.stint_laps, "drivers": s.drivers} for n, s in strategies.items()},
            "summary": summary, "differences_s": {n: np.round(d[~np.isnan(d)], 2).tolist() for n, d in diffs.items()},
            "laps_by_strategy": {n: runs.loc[runs["strategy"] == n, "laps"].tolist() for n in strategies}}


def stage_compare() -> None:
    if not read("replay")["gate_passed"]:
        raise SystemExit("the replay gate failed, so E-022 doesn't run the strategy comparison")
    calibration = read("calibrate")
    full = dict(lap_noise=True, pit_spread=True, cautions=True)
    mean, low, high = cal.AGE_SLOPE_RANGE_S[DEMO_CLASS]
    runs = [compare_once(calibration, "primary", full),
            compare_once(calibration, "no_cautions", dict(full, cautions=False)),
            compare_once(calibration, "sc_stop_free", full, sc_pit_loss_factor=0.0),
            compare_once(calibration, "sc_stop_costly", full, sc_pit_loss_factor=0.6),
            compare_once(calibration, "age_slope_uncertain", dict(full, slope_uncertainty=True)),
            compare_once(calibration, "age_slope_high", full, age_slope_s=high)]
    write("compare", {"circuit": DEMO_CIRCUIT, "class": DEMO_CLASS, "races_per_run": N_RACES, "runs": runs})
    for run in runs:
        print(run["label"], "lap", run["lap_compared"], {n: {k: round(v, 1) for k, v in s["difference_vs_baseline_s"].items()} | {"faster": round(s["share_faster_than_baseline"], 3)}
                                                         for n, s in run["summary"].items()})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=list(FILES), required=True)
    stage = parser.parse_args().stage
    {"calibrate": stage_calibrate, "replay": stage_replay, "sanity": stage_sanity, "compare": stage_compare}[stage]()


if __name__ == "__main__":
    main()
