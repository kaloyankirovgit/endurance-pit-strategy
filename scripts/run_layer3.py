#!/usr/bin/env python3
"""Layer 3, as registered in E-020: stint age, pit loss and race-pace predictors, in three stages.

`--stage fit` reads 2024 only and freezes the parameters. `--stage check` reads 2025 only, needs the
frozen file and runs once. `--stage refit` uses both seasons for the simulator's parameters. No
stage reads 2026. Output stays local in reports/outputs because it's derived from the timing data.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from endurance_strategy.features.clean_laps import EXCLUSION_FLAGS
from endurance_strategy.features.traffic import add_traffic_exposure, class_pace_gap
from endurance_strategy.models import pace
from endurance_strategy.paths import INTERIM_DIR, PROJECT_ROOT

OUTPUT_DIR = PROJECT_ROOT / "reports" / "outputs"
FIT_FILE = OUTPUT_DIR / "e020_fit.json"
CHECK_FILE = OUTPUT_DIR / "e020_check.json"
REFIT_FILE = OUTPUT_DIR / "e020_refit.json"
BETWEEN_RACE_SEED = 20261109
OTHER_SEED = 20261110
TRAFFIC_CAP = 6


def load(season: str | tuple[str, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    seasons = (season,) if isinstance(season, str) else season
    return (pace.load_open_seasons(INTERIM_DIR / "laps.parquet", seasons=seasons),
            pace.load_open_seasons(INTERIM_DIR / "practice_laps.parquet", seasons=seasons))


def outside_le_mans(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[~frame["event_key"].str.contains("LE_MANS")]


def flag_shares(laps: pd.DataFrame) -> dict:
    """Share of laps each exclusion flag catches, per class. Reported because a filter can bite unevenly by season."""
    rows = laps[laps["CLASS"].isin(pace.CLASSES)]
    return {car_class: {flag: float(group[flag].mean()) for flag in EXCLUSION_FLAGS} for car_class, group in rows.groupby("CLASS")}


def support_tables(frame: pd.DataFrame) -> dict:
    out = {"overall": pace.sample_counts(frame), "by_class_circuit": []}
    labelled = frame.assign(circuit=frame["event_key"].map(pace.circuit_of))
    for (car_class, circuit), group in labelled.groupby(["CLASS", "circuit"]):
        out["by_class_circuit"].append({"CLASS": car_class, "circuit": circuit, **pace.sample_counts(group)})
    return out


def laps_past_limit(frame: pd.DataFrame, limits: dict[str, int]) -> dict:
    return {car_class: int((frame[frame["CLASS"] == car_class]["stint_lap"] > limits[car_class]).sum()) for car_class in pace.CLASSES}


def with_traffic_count(laps: pd.DataFrame) -> pd.DataFrame:
    """The E-013 and E-014 candidate counts, with the window from this season's laps only."""
    gap = class_pace_gap(laps)
    frames = []
    for car_class, direction in (("HYPERCAR", "catching"), ("LMGT3", "being_caught")):
        exposed = pace.analysis_laps(add_traffic_exposure(laps, gap, direction))
        frames.append(exposed[exposed["CLASS"] == car_class])
    joined = pd.concat(frames, ignore_index=True)
    joined["traffic_count"] = joined["candidate_traffic_count"].clip(upper=TRAFFIC_CAP)
    return joined


def drop_last_two(frame: pd.DataFrame) -> pd.DataFrame:
    laps_from_end = frame.sort_values("stint_lap").groupby(pace.STINT_KEY).cumcount(ascending=False)
    return frame[laps_from_end.reindex(frame.index) >= 2]


def median_stint_limits(laps: pd.DataFrame, frame: pd.DataFrame, limits: dict[str, int]) -> dict[str, int]:
    """The support limit, or the class's median stint length out-lap to in-lap if that's shorter. Analysis stints only."""
    stints = frame[pace.STINT_KEY + ["CLASS"]].drop_duplicates()
    lengths = laps.groupby(pace.STINT_KEY)["stint_lap"].max().rename("length").reset_index().merge(stints, on=pace.STINT_KEY)
    median = lengths.groupby("CLASS")["length"].median()
    return {car_class: int(min(limits[car_class], median[car_class])) for car_class in pace.CLASSES}


def sensitivities(laps: pd.DataFrame, primary_frame: pd.DataFrame, limits: dict[str, int], primary: dict) -> dict:
    variants = {
        "loose_slow_lap_rule": pace.slope_summary(pace.analysis_laps(laps, slow_lap_rule="loose"), limits),
        "include_stint_lap_2": pace.slope_summary(primary_frame, limits, first_age=2),
        "drop_last_two_laps": pace.slope_summary(drop_last_two(primary_frame), limits),
        "at_least_10_laps_per_stint": pace.slope_summary(pace.analysis_laps(laps, min_stint_laps=10), limits),
        "ages_to_median_stint_length": pace.slope_summary(primary_frame, median_stint_limits(laps, primary_frame, limits)),
        "all_green_stints": pace.slope_summary(primary_frame[primary_frame["stint_all_green"]], limits),
        "track_temperature": pace.slope_summary(primary_frame, limits, extra=("TRACK_TEMP",)),
        "traffic_count": pace.slope_summary(with_traffic_count(laps), limits, extra=("traffic_count",)),
        "other_bootstrap_seed": pace.slope_summary(primary_frame, limits, seed=OTHER_SEED),
    }
    out = {}
    for name, variant in variants.items():
        out[name] = {}
        for car_class in pace.CLASSES:
            slope = variant[car_class]["s_per_lap"]["mean"]
            out[name][car_class] = {"laps": variant[car_class]["laps"], "stints": variant[car_class]["stints"],
                                    "s_per_lap": variant[car_class]["s_per_lap"], "pct_per_lap": variant[car_class]["pct_per_lap"],
                                    "unstable": pace.is_unstable(primary[car_class]["s_per_lap"], slope)}
    return out


def describe_le_mans(laps: pd.DataFrame) -> dict:
    """Description only, not fitted into anything: one race, so no support rule or interval over races applies."""
    races = laps[laps["event_key"].str.contains("LE_MANS")]
    frame = pace.analysis_laps(races)
    slopes = {}
    for car_class in pace.CLASSES:
        rows = pace.with_age_terms(frame[(frame["CLASS"] == car_class) & (frame["stint_lap"] >= pace.FIRST_FIT_AGE)])
        slopes[car_class] = {"s_per_lap": float(pace.race_coefficients(rows, ["age"])["age"].iloc[0]), "laps": int(len(rows))}
    return {"sizes": pace.sample_counts(frame), "slopes": slopes,
            "stops": pace.stop_quantiles(pace.routine_stop_events(races), ["CLASS"])}


def stop_status_counts(events: pd.DataFrame) -> dict:
    return {str(k): int(v) for k, v in events.groupby(["CLASS", "status"]).size().items()}


def series_records(series: pd.Series) -> list[dict]:
    return [{"event_key": event, "CLASS": car_class, "value": float(value)} for (event, car_class), value in series.items()]


def from_records(records: list[dict]) -> pd.Series:
    return pd.DataFrame(records).set_index(["event_key", "CLASS"])["value"]


def json_ready(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return str(value)


def write(path, report: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, default=json_ready))
    print("written to", path)


def caution_summary(events: pd.DataFrame) -> dict:
    cautions = events[events["status"] == "caution"]
    return {car_class: {"stops": int(len(group)), "pit_time_s_median": float(group["pit_time_s"].median())}
            for car_class, group in cautions.groupby("CLASS")}


def stage_fit(n_boot: int) -> None:
    if FIT_FILE.exists():
        raise SystemExit("the 2024 fit is already frozen. Amend E-020 before removing this file")
    laps, practice = load("2024")
    pace.require_open(laps["event_key"].unique())
    fit_laps = outside_le_mans(laps)
    frame = pace.analysis_laps(fit_laps)
    limits = pace.support_limit(frame)
    models = pace.fit_age_models(frame, limits)
    primary = pace.slope_summary(frame, limits, n_boot=n_boot)
    events = pace.routine_stop_events(fit_laps)
    stops = pace.eligible_stops(events)
    race_medians = stops.groupby(["event_key", "CLASS"])["pit_loss_s"].median()
    report = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "races": sorted(fit_laps["event_key"].unique()),
        "part_a": {"sizes": support_tables(frame), "support_limits": limits, "laps_past_limit": laps_past_limit(frame, limits),
                   "support_by_age": pace.support_by_age(frame).to_dict("records"),
                   "flag_share_2024": flag_shares(fit_laps), "median_stint_limits": median_stint_limits(fit_laps, frame, limits)},
        "part_b": {"models": models, "primary": primary,
                   "warm_up_s_median_age2_minus_ages3to7": {c: models[c]["B"].get(2) for c in pace.CLASSES},
                   "sensitivity": sensitivities(fit_laps, frame, limits, primary)},
        "part_c": {
            "status_counts": stop_status_counts(events),
            "caution_stops": caution_summary(events),
            "by_class_circuit": pace.stop_quantiles(events, ["CLASS", "circuit"]),
            "by_class_driver_change": pace.stop_quantiles(events, ["CLASS", "driver_changed"]),
            "class_median_of_race_medians": {c: {"median_s": float(race_medians.xs(c, level="CLASS").median()),
                                                 "race_bootstrap": pace.race_bootstrap_interval(race_medians.xs(c, level="CLASS"), n_boot=n_boot, statistic=np.median)}
                                             for c in pace.CLASSES},
            "per_circuit_car_bootstrap": {f"{car_class}|{circuit}": pace.car_bootstrap_median(group, n_boot=n_boot)
                                          for (car_class, circuit), group in stops.groupby(["CLASS", "circuit"])},
        },
        "le_mans_2024_described_only": describe_le_mans(laps),
        "frozen": {"fit_stops": events.assign(pit_time_s=events["pit_time_s"].astype(float)).to_dict("records"),
                   "target": series_records(pace.race_target(laps)),
                   "practice": series_records(pace.practice_pace(practice)),
                   "practice_fastest": series_records(pace.practice_pace(practice, fastest_session_only=True))},
    }
    write(FIT_FILE, report)
    print(json.dumps({"limits": limits, "L": {c: primary[c]["s_per_lap"] for c in pace.CLASSES}}, indent=1, default=json_ready))


def frozen_models(fit: dict) -> dict:
    models = fit["part_b"]["models"]
    for model in models.values():
        model["B"] = {int(age): value for age, value in model["B"].items()}
    return models


def stage_check() -> None:
    if not FIT_FILE.exists():
        raise SystemExit("the 2024 fit isn't frozen yet: run --stage fit first")
    if CHECK_FILE.exists():
        raise SystemExit("the 2025 check has already run and E-020 allows it once. Amend E-020 before removing this file")
    fit = json.loads(FIT_FILE.read_text())
    models = frozen_models(fit)
    laps, practice = load("2025")
    check_laps = outside_le_mans(laps)
    frame = pace.analysis_laps(check_laps)

    errors = pace.holdout_stint_errors(frame, models)
    frozen_limits = {c: models[c]["limit"] for c in pace.CLASSES}
    check_slopes = pace.slope_summary(frame, frozen_limits)
    fit_primary = fit["part_b"]["primary"]
    coverage = {c: {unit: pace.slope_coverage(list(fit_primary[c][unit]["race_slopes"].values()),
                                              list(check_slopes[c][unit]["race_slopes"].values()))
                    for unit in ("s_per_lap", "pct_per_lap")} for c in pace.CLASSES}

    fit_events = pd.DataFrame(fit["frozen"]["fit_stops"])
    events = pace.routine_stop_events(check_laps)

    target = pd.concat([from_records(fit["frozen"]["target"]), pace.race_target(laps)])
    fit_races = fit["races"]
    tables = {}
    for label, seasonal, frozen_key, fastest in (("primary", pace.practice_pace(practice), "practice", False),
                                                 ("fastest_session", pace.practice_pace(practice, fastest_session_only=True), "practice_fastest", True)):
        practice_all = pd.concat([from_records(fit["frozen"][frozen_key]), seasonal])
        tables[label] = pace.pace_predictions(target, practice_all, fit_races, sorted(laps["event_key"].unique()))
    non_lm = {label: table[~table["event_key"].str.contains("LE_MANS")] for label, table in tables.items()}

    report = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "fit_timestamp": fit["timestamp_utc"],
        "races": sorted(check_laps["event_key"].unique()),
        "flag_share_2025": flag_shares(check_laps),
        "part_a_2025": support_tables(frame),
        "laps_past_2024_limit": laps_past_limit(frame, frozen_limits),
        "part_b": {"errors_by_race": errors.to_dict("records"),
                   "ladder": {c: pace.decision_ladder(errors, c) for c in pace.CLASSES},
                   "slopes_2025": check_slopes, "coverage": coverage},
        "part_c": {
            "status_counts": stop_status_counts(events),
            "caution_stops": caution_summary(events),
            "by_class_circuit": pace.stop_quantiles(events, ["CLASS", "circuit"]),
            "by_class_driver_change": pace.stop_quantiles(events, ["CLASS", "driver_changed"]),
            "holdout": pace.pit_holdout(fit_events, events),
            "coverage": pace.pit_coverage(fit_events, events),
            "coverage_driver_change": pace.pit_coverage(fit_events, events, driver_changed=True),
            "coverage_no_driver_change": pace.pit_coverage(fit_events, events, driver_changed=False),
            "pit_time_vs_loss_median_difference_s": {c: float((group["pit_loss_s"] - group["pit_time_s"]).median())
                                                     for c, group in pace.eligible_stops(events).groupby("CLASS")},
        },
        "part_d": {
            "predictions": non_lm["primary"].to_dict("records"),
            "comparisons": pace.pace_comparisons(non_lm["primary"], expected_races=7),
            "by_class": {c: pace.pace_comparisons(non_lm["primary"][non_lm["primary"]["CLASS"] == c]) for c in pace.CLASSES},
            "sensitivity_fastest_session": pace.pace_comparisons(non_lm["fastest_session"], expected_races=7),
            "le_mans_2025_shown_apart": tables["primary"][tables["primary"]["event_key"].str.contains("LE_MANS")].to_dict("records"),
        },
        "le_mans_2025_described_only": describe_le_mans(laps),
    }
    write(CHECK_FILE, report)
    print(json.dumps({"ladder": {c: report["part_b"]["ladder"][c]["holder"] for c in pace.CLASSES}}, indent=1))


def stage_refit(n_boot: int) -> None:
    if not CHECK_FILE.exists():
        raise SystemExit("the 2025 check hasn't run: the refit comes after it")
    limits = json.loads(FIT_FILE.read_text())["part_a"]["support_limits"]  # Frozen on 2024, so no age untested on 2025 goes through.
    laps, _ = load(("2024", "2025"))
    fit_laps = outside_le_mans(laps)
    frame = pace.analysis_laps(fit_laps)
    events = pace.routine_stop_events(fit_laps)
    report = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "races": sorted(fit_laps["event_key"].unique()),
        "support_limits": limits,
        "models": pace.fit_age_models(frame, limits, circuit_model=False),
        "primary": pace.slope_summary(frame, limits, n_boot=n_boot),
        "stops": pace.stop_quantiles(events, ["CLASS", "circuit"]),
        "stops_by_driver_change": pace.stop_quantiles(events, ["CLASS", "driver_changed"]),
    }
    write(REFIT_FILE, report)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["fit", "check", "refit"], required=True)
    parser.add_argument("--n-boot", type=int, default=2000)
    args = parser.parse_args()
    if args.stage == "fit":
        stage_fit(args.n_boot)
    elif args.stage == "check":
        stage_check()
    else:
        stage_refit(args.n_boot)


if __name__ == "__main__":
    main()
