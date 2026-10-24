#!/usr/bin/env python3
"""E-014: the traffic association for GT3 cars being caught, with a past-only window, and from 2024-25 onto 2026."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from endurance_strategy.features.traffic import add_placebo_counts, add_traffic_exposure, class_pace_gap
from endurance_strategy.models.traffic import (
    add_previous_residual,
    analysis_mask,
    holdout_check,
    joint_fit,
    point_estimates,
    race_bootstrap,
    sample_sizes,
    stint_residuals,
)
from endurance_strategy.paths import INTERIM_DIR, PROJECT_ROOT

OUTPUT_DIR = PROJECT_ROOT / "reports" / "outputs"
CLASS_FOR = {"catching": "HYPERCAR", "being_caught": "LMGT3"}


def prepare(laps: pd.DataFrame, window, direction: str, slow_lap_rule: str = "standard") -> pd.DataFrame:
    exposed = add_placebo_counts(add_traffic_exposure(laps, window, direction=direction))
    return stint_residuals(exposed[exposed["CLASS"].eq(CLASS_FOR[direction]) & analysis_mask(exposed, slow_lap_rule)])


def summary(frame: pd.DataFrame, n_boot: int) -> dict:
    return {"sizes": sample_sizes(frame), "estimate": point_estimates(frame), "interval": race_bootstrap(frame, n_boot=n_boot)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-boot", type=int, default=2000)
    args = parser.parse_args()

    laps = pd.read_parquet(INTERIM_DIR / "laps.parquet")
    laps = laps[~laps["event_key"].str.contains("LE_MANS")]
    gap = class_pace_gap(laps)
    report = {"timestamp_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}

    caught = prepare(laps, gap, "being_caught")
    report["being_caught"] = {
        **summary(caught, args.n_boot),
        "by_race_slope_s_per_car": {r: point_estimates(rows)["slope_s_per_car"] for r, rows in caught.groupby("event_key")},
        "placebo_fits": {
            name: joint_fit(caught, columns, n_boot=args.n_boot)
            for name, columns in [
                ("with_far_behind", ["candidate_traffic_count", "far_count"]),
                ("with_just_ahead", ["candidate_traffic_count", "other_side_count"]),
                ("with_two_laps_later", ["candidate_traffic_count", "exposure_two_laps_later"]),
            ]
        },
        # Added after the review (E-014 says so). The two-laps-later count depends on this lap's time,
        # so it isn't a clean placebo; these two checks replace it.
        "added_after_review": {
            name: joint_fit(add_previous_residual(caught), columns, n_boot=args.n_boot)
            for name, columns in [
                ("with_previous_lap_residual", ["candidate_traffic_count", "previous_lap_residual_s"]),
                ("with_same_class_ahead", ["candidate_traffic_count", "same_class_ahead_count"]),
            ]
        },
        "window_sensitivity": {f"window_{w}s": summary(prepare(laps, float(w), "being_caught"), args.n_boot) for w in (5, 10, 15, 20)},
    }

    report["past_window"] = {}
    for direction in CLASS_FOR:
        past = prepare(laps, "past", direction)
        report["past_window"][direction] = {
            **summary(past, args.n_boot),
            "window_s_median": float(past["traffic_window_s"].median()),
            "window_s_iqr": [float(past["traffic_window_s"].quantile(q)) for q in (0.25, 0.75)],
        }

    report["holdout_2026"] = {}
    for direction in CLASS_FOR:
        report["holdout_2026"][direction] = {}
        for label, window, rule in [("race_window", gap, "standard"), ("loose_slow_lap_rule", gap, "loose"), ("past_window", "past", "standard")]:
            frame = prepare(laps, window, direction, rule)
            report["holdout_2026"][direction][label] = holdout_check(frame, ~frame["event_key"].str.startswith("2026"), n_boot=args.n_boot)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{report['timestamp_utc']}_traffic_followup.json"
    path.write_text(json.dumps(report, indent=2, default=lambda v: v.item() if isinstance(v, np.generic) else str(v)))
    print(json.dumps(report, indent=1))
    print("written to", path)


if __name__ == "__main__":
    main()
