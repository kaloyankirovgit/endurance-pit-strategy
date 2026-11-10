#!/usr/bin/env python3
"""E-021 Part 1: what the practice reference changes, on 2024 and 2025 only, with the gates registered first.

Run after the tables are rebuilt and before any rerun. It stops (exit code 1) if:
- the old flags no longer give E-020's analysis-lap counts, so earlier results wouldn't reproduce;
- COTA 2025 doesn't switch to the practice reference in both main classes;
- more than MAX_OTHER_SWITCHED other race-classes switch, which would mean the rule reaches beyond
  clearly wet races and needs an amendment before anything is rerun.
2026 is never loaded.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import pandas as pd

from endurance_strategy.features.clean_laps import apply_clean_rule
from endurance_strategy.models.pace import CLASSES, analysis_laps, load_open_seasons
from endurance_strategy.paths import INTERIM_DIR, PROJECT_ROOT

OUTPUT_DIR = PROJECT_ROOT / "reports" / "outputs"
EXPECTED_ANALYSIS_LAPS = {"2024": 41_501, "2025": 37_467}  # E-020 Part A, outside Le Mans
WET_RACE = "2025_CIRCUIT_OF_THE_AMERICAS"
MAX_OTHER_SWITCHED = 4
AGE_BANDS = [(2, 10), (11, 20), (21, 30), (31, 999)]


def race_class_table(laps: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (event, car_class), group in laps.groupby(["event_key", "CLASS"]):
        running = group[~group["is_pit_lap"]]
        rows.append({
            "event_key": event, "CLASS": car_class, "laps": int(len(running)),
            "switched": bool(group["slow_lap_reference_source"].eq("practice").any()),
            "race_vs_practice_ratio": float(group["race_vs_practice_ratio"].iloc[0]),
            "usable_share_old": float(running["is_usable_race_ref"].mean()),
            "usable_share_new": float(running["is_usable_for_pace_model"].mean()),
        })
    table = pd.DataFrame(rows)
    table["change_points"] = 100 * (table["usable_share_new"] - table["usable_share_old"])
    return table


def where_it_changes(laps: pd.DataFrame, table: pd.DataFrame) -> dict:
    """For each switched race-class: usable share under both rules by race hour and by stint-age band."""
    out = {}
    for row in table[table["switched"]].itertuples():
        group = laps[(laps["event_key"] == row.event_key) & (laps["CLASS"] == row.CLASS) & ~laps["is_pit_lap"]]
        hour = (group["ELAPSED_S"] // 3600).astype(int)
        band = pd.cut(group["stint_lap"], [low - 0.5 for low, _ in AGE_BANDS] + [AGE_BANDS[-1][1] + 0.5],
                      labels=[f"{low}-{high}" if high < 999 else f"{low}+" for low, high in AGE_BANDS])
        out[f"{row.event_key}|{row.CLASS}"] = {
            "by_hour": {int(h): [float(g["is_usable_race_ref"].mean()), float(g["is_usable_for_pace_model"].mean())] for h, g in group.groupby(hour)},
            "by_stint_age": {str(b): [float(g["is_usable_race_ref"].mean()), float(g["is_usable_for_pace_model"].mean())]
                             for b, g in group.groupby(band, observed=True)},
        }
    return out


def reproduction(laps: pd.DataFrame) -> dict:
    counts = {}
    for season in EXPECTED_ANALYSIS_LAPS:
        season_laps = laps[laps["event_key"].str.startswith(season) & ~laps["event_key"].str.contains("LE_MANS")]
        counts[season] = int(len(analysis_laps(apply_clean_rule(season_laps, "race"))))
    return counts


def gates(table: pd.DataFrame, counts: dict, expected: dict = EXPECTED_ANALYSIS_LAPS) -> list[str]:
    failures = [f"{season}: old flags give {counts[season]} analysis laps, E-020 had {expected[season]}"
                for season in expected if counts.get(season) != expected[season]]
    wet = table[(table["event_key"] == WET_RACE) & table["CLASS"].isin(CLASSES)]
    if len(wet) != len(CLASSES) or not wet["switched"].all():
        failures.append(f"{WET_RACE} doesn't switch to practice in both main classes")
    others = table[table["switched"] & (table["event_key"] != WET_RACE)]
    if len(others) > MAX_OTHER_SWITCHED:
        failures.append(f"{len(others)} other race-classes switch, more than {MAX_OTHER_SWITCHED}")
    return failures


def main() -> int:
    laps = load_open_seasons(INTERIM_DIR / "laps.parquet", seasons=("2024", "2025"))
    table = race_class_table(laps)
    counts = reproduction(laps)
    failures = gates(table, counts)
    report = {"timestamp_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), "analysis_laps_old_rule": counts,
              "race_classes": table.to_dict("records"), "where_it_changes": where_it_changes(laps, table), "gate_failures": failures}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "e021_rule_check.json").write_text(json.dumps(report, indent=2))
    print(table.round(3).to_string(index=False))
    print("analysis laps under the old rule:", counts)
    print("gate failures:", failures or "none")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
