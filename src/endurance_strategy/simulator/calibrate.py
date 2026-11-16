"""Simulator parameters from 2024 and 2025 races outside Le Mans (E-022 Part A). 2026 is never read.

Figures carried over from earlier experiments are constants here, each with its source. Everything else is
measured from the laps by this module's functions.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from endurance_strategy.features.traffic import add_traffic_exposure
from endurance_strategy.models.pace import CLASSES, analysis_laps, circuit_of, eligible_stops, routine_stop_events
from endurance_strategy.models.traffic import STINT_KEY, detrend_within_stint
from endurance_strategy.simulator.engine import CAUTIONS, CarParams, Randomness

# D-032, from E-021's refit on 2024 and 2025.
AGE_SLOPE_RANGE_S = {"HYPERCAR": (0.016, -0.002, 0.033), "LMGT3": (0.026, -0.014, 0.065)}   # ASSUMED sensitivity: mean, low, high
AGE_LIMIT_LAPS = {"HYPERCAR": 35, "LMGT3": 30}                                               # D-032 support limits
WARM_UP_S = {"HYPERCAR": 0.34, "LMGT3": 0.19}                                                # INFERRED, no interval
TRAFFIC_S_PER_CAR = {"HYPERCAR": 0.343, "LMGT3": 0.168}                                      # INFERRED, past-only window
TRAFFIC_DIRECTION = {"HYPERCAR": "catching", "LMGT3": "being_caught"}
LONG_STOP_EXCESS_S = 60.0       # E-020: stops this far over their pit-lane time sit next to cautions
STINT_LIMIT_QUANTILE = 0.95     # ASSUMED energy-limit proxy
SC_PIT_LOSS_FACTOR = 0.3        # ASSUMED: a stop under a safety car costs this share of a green one (E-022 Part A)
MIN_EPISODE_CROSSINGS = 3       # a caution needs at least this many line crossings under it


def race_hours(laps: pd.DataFrame) -> pd.Series:
    """OBSERVED race length per event, in whole hours (6, 8 or 10)."""
    return (laps.groupby("event_key")["ELAPSED_S"].max() / 3600).round().astype(int)


def caution_episodes(laps: pd.DataFrame) -> pd.DataFrame:
    """RECONSTRUCTED caution periods from line crossings across the field.

    Runs of crossings under a caution flag (SF or FCY) are merged when the gap between them is under one
    median green lap, so a stray green crossing doesn't split a safety car and an FCY that turns into a
    safety car stays one episode. A merged episode takes the type with more crossings. A red flag (RF)
    isn't modelled. The length runs from the first to the last crossing plus one median green lap.
    """
    rows = []
    for event, race in laps.groupby("event_key"):
        crossings = race.sort_values("ELAPSED_S")
        flags = crossings["FLAG_AT_FL"].to_numpy()
        times = crossings["ELAPSED_S"].to_numpy(dtype=float)
        lap_s = float(race.loc[race["FLAG_AT_FL"].eq("GF"), "LAP_TIME_S"].median())
        caution = np.isin(flags, CAUTIONS)
        current = None
        for t, flag, is_caution in zip(times, flags, caution):
            if not is_caution:
                continue
            if current is not None and t - current["end"] < lap_s:
                current["end"] = t
                current[flag] = current.get(flag, 0) + 1
            else:
                if current is not None:
                    rows.append(current)
                current = {"event_key": event, "start": t, "end": t, flag: 1, "lap_s": lap_s}
        if current is not None:
            rows.append(current)
    out = []
    for r in rows:
        counts = {kind: r.get(kind, 0) for kind in CAUTIONS}
        if sum(counts.values()) >= MIN_EPISODE_CROSSINGS:
            out.append({"event_key": r["event_key"], "kind": max(counts, key=counts.get), "start_s": r["start"],
                        "duration_s": r["end"] - r["start"] + r["lap_s"], "crossings": sum(counts.values()),
                        "mixed": all(counts.values())})
    return pd.DataFrame(out, columns=["event_key", "kind", "start_s", "duration_s", "crossings", "mixed"])


def caution_model(laps: pd.DataFrame) -> dict:
    """INFERRED: episode rates per hour of green running (so the generator can match them), and lengths."""
    episodes = caution_episodes(laps)
    hours = race_hours(laps)
    green_s = float((hours * 3600).sum() - episodes["duration_s"].sum())
    per_race = (episodes.groupby(["event_key", "kind"]).size().unstack(fill_value=0)
                .reindex(index=hours.index, columns=list(CAUTIONS), fill_value=0))
    per_race["hours"] = hours
    return {
        "racing_hours": float(hours.sum()), "green_hours": green_s / 3600,
        "episodes": {kind: int((episodes["kind"] == kind).sum()) for kind in CAUTIONS},
        "mixed_episodes": int(episodes["mixed"].sum()),
        "rate_per_green_hour": {kind: float((episodes["kind"] == kind).sum() / (green_s / 3600)) for kind in CAUTIONS},
        "durations_s": {kind: episodes.loc[episodes["kind"] == kind, "duration_s"].round(1).tolist() for kind in CAUTIONS},
        "per_race": per_race.reset_index().to_dict("records"),
    }


def caution_lap_ratio(laps: pd.DataFrame) -> dict:
    """INFERRED: per class, the median over races of (median caution lap / median clean lap), by caution type."""
    out = {}
    for car_class in CLASSES:
        rows = laps[laps["CLASS"] == car_class]
        ratios = {kind: [] for kind in CAUTIONS}
        for _, race in rows.groupby("event_key"):
            clean = race.loc[race["is_usable_for_pace_model"], "LAP_TIME_S"].median()
            for kind in CAUTIONS:
                under = race.loc[race["FLAG_AT_FL"].eq(kind) & ~race["is_pit_lap"] & ~race["is_first_lap"], "LAP_TIME_S"]
                if len(under) >= 10 and clean > 0:
                    ratios[kind].append(float(under.median() / clean))
        out[car_class] = {kind: float(np.median(values)) if values else 1.0 for kind, values in ratios.items()}
    return out


def lap_residuals(laps: pd.DataFrame) -> dict:
    """INFERRED: clean-lap residuals after removing each stint's own straight line, by class."""
    frame = analysis_laps(laps)
    out = {}
    for car_class in CLASSES:
        rows = frame[frame["CLASS"] == car_class]
        out[car_class] = detrend_within_stint(rows, ["LAP_TIME_S"])["LAP_TIME_S"].to_numpy()
    return out


def pit_loss_samples(laps: pd.DataFrame) -> dict:
    """INFERRED: routine green-flag stop losses by class and driver change, without the long stops (D-032)."""
    stops = eligible_stops(routine_stop_events(laps))
    stops = stops[stops["pit_loss_s"] - stops["pit_time_s"] <= LONG_STOP_EXCESS_S]
    return {car_class: {changed: group["pit_loss_s"].to_numpy() for changed, group in stops[stops["CLASS"] == car_class].groupby("driver_changed")}
            for car_class in CLASSES}


def circuit_table(laps: pd.DataFrame) -> pd.DataFrame:
    """Per circuit and class: race length, clean pace, energy-limit proxy and traffic rate (2024 and 2025 pooled)."""
    hours = race_hours(laps)
    frame = analysis_laps(laps)
    rows = []
    for car_class in CLASSES:
        exposed = analysis_laps(add_traffic_exposure(laps, "past", TRAFFIC_DIRECTION[car_class]))
        exposed = exposed[exposed["CLASS"] == car_class]
        for circuit, group in frame[frame["CLASS"] == car_class].groupby(frame["event_key"].map(circuit_of)):
            events = group["event_key"].unique()
            race_laps = laps[laps["event_key"].isin(events) & (laps["CLASS"] == car_class)]
            stints = race_laps.groupby(STINT_KEY).agg(length=("stint_lap", "max"), ended=("is_in_lap", "any"),
                                                        caution=("is_caution_lap", "any"))
            clean_stints = stints[stints["ended"] & ~stints["caution"]]["length"]
            counts = exposed.loc[exposed["event_key"].isin(events), "candidate_traffic_count"].clip(upper=6)
            rows.append({"circuit": circuit, "CLASS": car_class, "races": len(events),
                         "hours": int(hours[events].max()), "clean_median_s": float(group["LAP_TIME_S"].median()),
                         "max_stint_laps": int(np.floor(clean_stints.quantile(STINT_LIMIT_QUANTILE))),
                         "stints_for_limit": int(len(clean_stints)), "traffic_rate": float(counts.mean())})
    return pd.DataFrame(rows)


def calibrate(laps: pd.DataFrame) -> dict:
    if laps["event_key"].str.startswith("2026").any():
        raise ValueError("2026 is sealed for the simulator's final test")
    laps = laps[~laps["event_key"].str.contains("LE_MANS")]
    pits = pit_loss_samples(laps)
    return {
        "races": sorted(laps["event_key"].unique()),
        "circuits": circuit_table(laps).to_dict("records"),
        "caution": caution_model(laps),
        "caution_lap_ratio": caution_lap_ratio(laps),
        "pit_loss_median_s": {c: {str(k): float(np.median(v)) for k, v in d.items()} for c, d in pits.items()},
        "pit_loss_samples_s": {c: {str(k): np.round(v, 2).tolist() for k, v in d.items()} for c, d in pits.items()},
        "lap_residuals_s": {c: np.round(v, 3).tolist() for c, v in lap_residuals(laps).items()},
    }


def car_params(calibration: dict, circuit: str, car_class: str, base_pace_s: float | None = None, **overrides) -> CarParams:
    """The parameters for one class at one circuit. Base pace defaults to the class's clean median there,
    with the expected traffic taken off so it isn't counted twice."""
    row = next(r for r in calibration["circuits"] if r["circuit"] == circuit and r["CLASS"] == car_class)
    traffic = row["traffic_rate"] * TRAFFIC_S_PER_CAR[car_class]
    medians = calibration["pit_loss_median_s"][car_class]
    values = dict(circuit=circuit, car_class=car_class, duration_s=row["hours"] * 3600.0,
                  base_pace_s=(row["clean_median_s"] if base_pace_s is None else base_pace_s) - traffic,
                  max_stint_laps=row["max_stint_laps"], pit_loss_s={False: medians["False"], True: medians["True"]},
                  age_slope_s=0.0, age_limit_laps=AGE_LIMIT_LAPS[car_class], warm_up_s=WARM_UP_S[car_class], traffic_rate=row["traffic_rate"],
                  traffic_s_per_car=TRAFFIC_S_PER_CAR[car_class], sc_pit_loss_factor=SC_PIT_LOSS_FACTOR, caution_lap_ratio=calibration["caution_lap_ratio"][car_class])
    values.update(overrides)
    return CarParams(**values)


def randomness(calibration: dict, car_class: str, lap_noise: bool = True, pit_spread: bool = True, cautions: bool = True,
               slope_uncertainty: bool = False) -> Randomness:
    """The random parts, each of which can be switched off to see what it adds (simulation.md).

    `slope_uncertainty` draws the stint-age slope once per race from D-032's range (centred on its mean),
    replacing the flat default. It's a sensitivity, since the flat model held (D-032)."""
    caution = calibration["caution"]
    mean, low, high = AGE_SLOPE_RANGE_S[car_class]
    samples = calibration["pit_loss_samples_s"][car_class]
    return Randomness(
        lap_residuals_s=np.asarray(calibration["lap_residuals_s"][car_class]) if lap_noise else None,
        pit_loss_samples_s={False: np.asarray(samples["False"]), True: np.asarray(samples["True"])} if pit_spread else None,
        caution_rate_per_green_s={k: v / 3600 for k, v in caution["rate_per_green_hour"].items()} if cautions else None,
        caution_durations_s={k: np.asarray(v) for k, v in caution["durations_s"].items()} if cautions else None,
        age_slope_draw=(mean, (high - low) / (2 * 1.96)) if slope_uncertainty else None,
    )
