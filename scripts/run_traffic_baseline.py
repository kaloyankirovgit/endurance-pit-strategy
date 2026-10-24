#!/usr/bin/env python3
"""Within-stint traffic baseline (E-013): Hypercar lap time against the LMGT3 cars it is expected to catch."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from endurance_strategy.features.traffic import add_placebo_counts, add_traffic_exposure, class_pace_gap
from endurance_strategy.models.traffic import (
    analysis_mask,
    joint_fit,
    point_estimates,
    race_bootstrap,
    sample_sizes,
    stint_residuals,
)
from endurance_strategy.paths import INTERIM_DIR, PROJECT_ROOT

OUTPUT_DIR = PROJECT_ROOT / "reports" / "outputs"


def prepare(laps: pd.DataFrame, window, slow_lap_rule: str, trend: str) -> pd.DataFrame:
    exposed = add_placebo_counts(add_traffic_exposure(laps, window))
    hypercar = exposed[exposed["CLASS"].eq("HYPERCAR") & analysis_mask(exposed, slow_lap_rule)]
    return stint_residuals(hypercar, trend=trend)


def run(laps: pd.DataFrame, window, slow_lap_rule: str, trend: str, n_boot: int) -> dict:
    frame = prepare(laps, window, slow_lap_rule, trend)
    return {"sizes": sample_sizes(frame), "estimate": point_estimates(frame), "interval": race_bootstrap(frame, n_boot=n_boot)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-boot", type=int, default=2000)
    args = parser.parse_args()

    laps = pd.read_parquet(INTERIM_DIR / "laps.parquet")
    laps = laps[~laps["event_key"].str.contains("LE_MANS")]
    gap = class_pace_gap(laps)

    report = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "pace_gap_s": {k: round(float(v), 2) for k, v in gap.items()},
        "primary": run(laps, gap, "standard", "linear", args.n_boot),
        "sensitivity": {},
    }
    for label, window, rule, trend in [
        ("window_5s", 5.0, "standard", "linear"), ("window_10s", 10.0, "standard", "linear"),
        ("window_15s", 15.0, "standard", "linear"), ("window_20s", 20.0, "standard", "linear"),
        ("loose_slow_lap_rule", gap, "loose", "linear"), ("stint_mean", gap, "standard", "mean"),
    ]:
        report["sensitivity"][label] = run(laps, window, rule, trend, args.n_boot)

    primary = prepare(laps, gap, "standard", "linear")
    report["by_race_slope_s_per_car"] = {
        race: round(point_estimates(rows)["slope_s_per_car"], 3) for race, rows in primary.groupby("event_key")
    }

    # Added after the primary result was seen (E-013 says so): circuit resampling and placebo counts.
    primary["circuit"] = primary["event_key"].str[5:]
    report["added_after_primary"] = {
        "circuit_bootstrap": race_bootstrap(primary, n_boot=args.n_boot, cluster="circuit"),
        "placebo_fits": {
            name: joint_fit(primary, columns, n_boot=args.n_boot)
            for name, columns in [
                ("behind_alone", ["other_side_count"]),
                ("ahead_and_behind", ["candidate_traffic_count", "other_side_count"]),
                ("ahead_and_far_ahead", ["candidate_traffic_count", "far_count"]),
                ("ahead_and_two_laps_later", ["candidate_traffic_count", "exposure_two_laps_later"]),
                ("ahead_and_same_class_ahead", ["candidate_traffic_count", "same_class_ahead_count"]),
            ]
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{report['timestamp_utc']}_traffic_baseline.json"
    path.write_text(json.dumps(report, indent=2, default=lambda v: v.item() if isinstance(v, np.generic) else str(v)))
    print(json.dumps({k: report[k] for k in ("primary", "by_race_slope_s_per_car")}, indent=2))
    for label, result in report["sensitivity"].items():
        print(label, round(result["estimate"]["slope_s_per_car"], 3), [round(v, 3) for v in result["interval"]["slope_s_per_car"]],
              "level 1:", round(result["estimate"]["difference_from_zero_s"][1], 3),
              [round(v, 3) for v in result["interval"]["difference_from_zero_s"][1]], result["sizes"]["laps"])
    print(json.dumps(report["added_after_primary"], indent=1))
    print("written to", path)


if __name__ == "__main__":
    main()
