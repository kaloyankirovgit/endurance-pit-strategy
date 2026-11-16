"""E-022 Part B: replay finished cars from 2024 and 2025 through the lap-time model and compare race time.

Retrospective and in-sample: each car's clean pace comes from its own race, and the flags it saw are
replayed lap by lap. So this checks that the parts of the model add up to a race, not that it predicts one.
Four nested models show what each part adds:
  M0  laps × the car's clean median
  M1  + caution laps at the class's caution-lap ratio
  M2  + one class-wide pit loss per stop (shared by driver change), cut under a safety car
  M3  + the pit loss split by driver change and the warm-up lap
Lap 1 and red-flag laps are taken as observed in every model. Every model runs through `engine.lap_time`,
so the replay checks the simulator's own lap model.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from dataclasses import replace

from endurance_strategy.models.pace import CLASSES
from endurance_strategy.simulator.calibrate import car_params, race_hours
from endurance_strategy.simulator.engine import CAUTIONS, GREEN, CarParams, Draws, State, lap_time

MODELS = ("M0", "M1", "M2", "M3")


def finished_cars(laps: pd.DataFrame) -> pd.DataFrame:
    """Cars of the two main classes that took the flag, never used the garage and have a clean pace."""
    hours = race_hours(laps)
    last = laps.groupby(["event_key", "NUMBER"]).agg(CLASS=("CLASS", "first"), end_s=("ELAPSED_S", "max"),
                                                       garage=("is_garage_stop", "any"), clean=("is_usable_for_pace_model", "sum"))
    last["duration_s"] = last.index.get_level_values("event_key").map(hours) * 3600
    keep = last["CLASS"].isin(CLASSES) & ~last["garage"] & (last["end_s"] >= last["duration_s"]) & (last["clean"] >= 20)
    return last[keep].reset_index()


def model_params(calibration: dict, circuit: str, car_class: str, clean_s: float, model: str) -> CarParams:
    """The engine's parameters for one replay model. Base pace is the car's clean median, net of expected traffic."""
    params = car_params(calibration, circuit, car_class, base_pace_s=clean_s)
    pooled = float(np.mean(np.concatenate([np.asarray(v) for v in calibration["pit_loss_samples_s"][car_class].values()])))
    if model == "M0":
        return replace(params, caution_lap_ratio={k: 1.0 for k in CAUTIONS}, restart_lap_ratio=1.0, pit_loss_s={False: 0.0, True: 0.0},
                       warm_up_s=0.0, incident_rate=0.0)
    if model == "M1":
        return replace(params, pit_loss_s={False: 0.0, True: 0.0}, warm_up_s=0.0, incident_rate=0.0)
    if model == "M2":
        return replace(params, pit_loss_s={False: pooled, True: pooled}, warm_up_s=0.0, incident_rate=0.0)
    return params


def replay_car(car: pd.DataFrame, calibration: dict, model: str) -> float:
    """Predicted elapsed time at the car's last lap, from `engine.lap_time` with the observed flags and stops.

    The flag a lap is run under is its observed `FLAG_AT_FL`, and a stop's flag at pit entry is the in-lap's
    flag, the same convention the simulator uses."""
    car = car.sort_values("LAP_NUMBER")
    clean = float(car.loc[car["is_usable_for_pace_model"], "LAP_TIME_S"].mean())
    params = model_params(calibration, car["event_key"].iloc[0][5:], car["CLASS"].iloc[0], clean, model)
    total, previous = 0.0, None
    for lap in car.itertuples():
        if lap.LAP_NUMBER == 1 or lap.FLAG_AT_FL == "RF":
            total += lap.LAP_TIME_S
        else:
            flag = lap.FLAG_AT_FL if lap.FLAG_AT_FL in CAUTIONS else GREEN
            state = State(stint_lap=lap.stint_lap - 1, pitting_now=bool(lap.is_out_lap),
                          last_stop_driver_change=previous is not None and lap.DRIVER_NUMBER != previous.DRIVER_NUMBER,
                          last_stop_flag=previous.FLAG_AT_FL if previous is not None else GREEN,
                          previous_flag=(previous.FLAG_AT_FL if previous is not None and previous.FLAG_AT_FL in CAUTIONS else GREEN))
            total += lap_time(state, params, flag, Draws(), params.age_slope_s)[0]
        previous = lap
    return total


def replay(laps: pd.DataFrame, calibration: dict) -> pd.DataFrame:
    laps = laps[~laps["event_key"].str.contains("LE_MANS")]
    cars = finished_cars(laps)
    rows = []
    for car in cars.itertuples():
        car_laps = laps[(laps["event_key"] == car.event_key) & (laps["NUMBER"] == car.NUMBER)]
        observed = float(car_laps["ELAPSED_S"].max())
        row = {"event_key": car.event_key, "NUMBER": car.NUMBER, "CLASS": car.CLASS, "laps": int(car_laps["LAP_NUMBER"].max()),
               "stops": int(car_laps["is_out_lap"].sum()), "observed_s": observed}
        for model in MODELS:
            predicted = replay_car(car_laps, calibration, model)
            row[f"{model}_error_s"] = predicted - observed
            row[f"{model}_error_pct"] = 100 * (predicted - observed) / observed
        rows.append(row)
    return pd.DataFrame(rows)


def summarise(table: pd.DataFrame) -> dict:
    """Per model: the median over races of each race's median absolute error, and the bias, in %."""
    out = {}
    for model in MODELS:
        by_race = table.groupby("event_key")[f"{model}_error_pct"]
        out[model] = {"median_abs_pct_over_races": float(by_race.apply(lambda e: e.abs().median()).median()),
                      "worst_race_median_abs_pct": float(by_race.apply(lambda e: e.abs().median()).max()),
                      "median_signed_pct": float(table[f"{model}_error_pct"].median()),
                      "cars": int(len(table)), "races": int(table["event_key"].nunique())}
    return out
