#!/usr/bin/env python3
"""E-015: at Le Mans, each class's lap time against each other class it meets, counted separately."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from endurance_strategy.features.traffic import CLASS_RANK, add_class_pair_counts
from endurance_strategy.models.traffic import analysis_mask, joint_fit, sample_sizes, stint_residuals, t_interval
from endurance_strategy.paths import INTERIM_DIR, PROJECT_ROOT

OUTPUT_DIR = PROJECT_ROOT / "reports" / "outputs"
CLASSES = sorted(CLASS_RANK, key=CLASS_RANK.get)


def fit_class(counted: pd.DataFrame, own: str, slow_lap_rule: str, races: list[str], n_boot: int) -> dict:
    others = [c for c in CLASSES if c != own]
    main_columns = [f"count_{o}" for o in others]
    keep = counted["CLASS"].eq(own) & analysis_mask(counted, slow_lap_rule) & counted["event_key"].isin(races)
    frame = stint_residuals(counted[keep])
    frame["car"] = frame["event_key"] + "/" + frame["NUMBER"]
    by_race = {race: joint_fit(rows, main_columns, n_boot=n_boot, cluster="car") for race, rows in frame.groupby("event_key")}
    pooled = joint_fit(frame, main_columns, n_boot=n_boot, cluster="car")
    placebo = joint_fit(frame, main_columns + [f"far_{o}" for o in others], n_boot=n_boot, cluster="car")
    return {
        "sizes": sample_sizes(frame),
        "mean_count": {c: float(frame[c].mean()) for c in main_columns},
        "pooled": pooled,
        "by_race": by_race,
        "mean_of_race_figures_t_interval": {
            c: {"mean": float(np.mean([r["coefficients_s"][c] for r in by_race.values()])),
                "interval": t_interval(r["coefficients_s"][c] for r in by_race.values())} for c in main_columns
        } if len(by_race) > 2 else None,
        "pooled_with_far_placebo": placebo,
    }


def main() -> None:
    laps = pd.read_parquet(INTERIM_DIR / "laps.parquet")
    laps = laps[laps["event_key"].str.contains("LE_MANS")]
    counted = add_class_pair_counts(laps)
    all_races = sorted(counted["event_key"].unique())
    report = {"timestamp_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
              "note": "Intervals inside a race or pooled resample car entries (event and car number); the t-interval is over race figures.",
              "lap_flags_by_race": {race: {f: float(rows[f].mean()) for f in ("is_slow_lap", "is_caution_lap", "is_wet")}
                                    for race, rows in counted.groupby("event_key")},
              "specifications": {}}
    for label, rule, races in [("standard", "standard", all_races), ("loose_slow_lap_rule", "loose", all_races),
                               ("standard_without_2024", "standard", [r for r in all_races if not r.startswith("2024")]),
                               ("loose_without_2024", "loose", [r for r in all_races if not r.startswith("2024")])]:
        report["specifications"][label] = {own: fit_class(counted, own, rule, races, n_boot=1000) for own in CLASSES}

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{report['timestamp_utc']}_traffic_le_mans.json"
    path.write_text(json.dumps(report, indent=2, default=lambda v: v.item() if isinstance(v, np.generic) else str(v)))
    print(json.dumps(report["lap_flags_by_race"], indent=1))
    for label, spec in report["specifications"].items():
        print("==", label)
        for own, result in spec.items():
            print(own, result["sizes"]["laps"], "laps")
            for column, value in result["pooled"]["coefficients_s"].items():
                low, high = result["pooled"]["intervals_s"][column]
                races = {r[:4]: f"{v['coefficients_s'][column]:.2f} ({v['intervals_s'][column][0]:.2f} to {v['intervals_s'][column][1]:.2f})"
                         for r, v in result["by_race"].items()}
                print(f"  {column}: pooled {value:.3f} ({low:.3f} to {high:.3f}) | {races}")
            far = {k: f"{v:.3f} ({result['pooled_with_far_placebo']['intervals_s'][k][0]:.3f} to {result['pooled_with_far_placebo']['intervals_s'][k][1]:.3f})"
                   for k, v in result["pooled_with_far_placebo"]["coefficients_s"].items() if k.startswith("far_")}
            print("  far placebo:", far)
    print("written to", path)


if __name__ == "__main__":
    main()
