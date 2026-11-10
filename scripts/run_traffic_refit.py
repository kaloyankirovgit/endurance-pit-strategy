#!/usr/bin/env python3
"""The traffic refit on 2024 and 2025 only, required by D-031 before the simulator's final test (E-021).

The E-013 and E-014 primary specifications, unchanged: within-stint fits, the race's class pace gap as the
window and the past-only window, whole-race bootstrap, plus circuit-clustered intervals and the loose
slow-lap rule. Run under the E-020 clean-lap rule and the E-021 one. The race gap window is computed from
clean laps, so it moves with the rule; the past window doesn't, so it is the cleaner comparison between rules.
Outside Le Mans. 2026 is never loaded.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from endurance_strategy.features.clean_laps import CLEAN_RULES, apply_clean_rule
from endurance_strategy.features.traffic import add_traffic_exposure, class_pace_gap
from endurance_strategy.models.pace import load_open_seasons
from endurance_strategy.models.traffic import analysis_mask, point_estimates, race_bootstrap, sample_sizes, stint_residuals
from endurance_strategy.paths import INTERIM_DIR, PROJECT_ROOT

OUTPUT_DIR = PROJECT_ROOT / "reports" / "outputs"
DIRECTIONS = {"HYPERCAR": "catching", "LMGT3": "being_caught"}


def fit(laps: pd.DataFrame, car_class: str, window, n_boot: int, slow_lap_rule: str = "standard") -> dict:
    exposed = add_traffic_exposure(laps, window, DIRECTIONS[car_class])
    frame = stint_residuals(exposed[exposed["CLASS"].eq(car_class) & analysis_mask(exposed, slow_lap_rule)])
    frame["circuit"] = frame["event_key"].str[5:]
    return {"sizes": sample_sizes(frame), "estimate": point_estimates(frame), "interval": race_bootstrap(frame, n_boot=n_boot),
            "circuit_interval": race_bootstrap(frame, n_boot=n_boot, cluster="circuit")}


def run(laps: pd.DataFrame, n_boot: int) -> dict:
    laps = laps[~laps["event_key"].str.contains("LE_MANS")]
    out = {}
    for rule in CLEAN_RULES:
        ruled = apply_clean_rule(laps, rule)
        gap = class_pace_gap(ruled)
        out[rule] = {"pace_gap_s": {k: round(float(v), 2) for k, v in gap.items()}}
        for car_class in DIRECTIONS:
            out[rule][car_class] = {"race_gap_window": fit(ruled, car_class, gap, n_boot), "past_window": fit(ruled, car_class, "past", n_boot),
                                    "loose_rule_race_gap_window": fit(ruled, car_class, gap, n_boot, slow_lap_rule="loose")}
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-boot", type=int, default=2000)
    args = parser.parse_args()
    laps = load_open_seasons(INTERIM_DIR / "laps.parquet", seasons=("2024", "2025"))
    report = {"timestamp_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), "seasons": ["2024", "2025"], **run(laps, args.n_boot)}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "e021_traffic_refit.json"
    path.write_text(json.dumps(report, indent=2, default=lambda v: v.item() if isinstance(v, np.generic) else str(v)))
    print("written to", path)


if __name__ == "__main__":
    main()
