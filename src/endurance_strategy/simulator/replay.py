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

E-023: when the calibration prices cautions by time, M1 to M3 run the car through its race's own caution
episodes (rebuilt from the whole field's line crossings) on the model's clock, as the simulator does with
drawn episodes. A lap's flag and a stop's flag at pit entry then come from those episodes at the predicted
time, not from the car's own observed flags. M0 keeps full speed under cautions.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from dataclasses import replace

from endurance_strategy.models.pace import CLASSES
from endurance_strategy.simulator.calibrate import car_params, race_hours
from endurance_strategy.simulator.engine import CAUTIONS, GREEN, CarParams, Draws, State, flag_at, lap_time

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
                       warm_up_s=0.0, incident_rate=0.0,
                       caution_progress=None if params.caution_progress is None else {k: 1.0 for k in CAUTIONS})
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
    event = car["event_key"].iloc[0]
    params = model_params(calibration, event[5:], car["CLASS"].iloc[0], clean, model)
    if params.caution_progress is not None:
        return _replay_on_clock(car, params, [tuple(e) for e in calibration["caution"]["episodes_by_race"].get(event, [])])
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


def _replay_on_clock(car: pd.DataFrame, params: CarParams, episodes: list) -> float:
    """E-023: the car's observed laps and stops, run on the model's own clock through the race's episodes."""
    total, previous = 0.0, None
    for lap in car.itertuples():
        if lap.LAP_NUMBER == 1 or lap.FLAG_AT_FL == "RF":
            total += lap.LAP_TIME_S
        else:
            flag = flag_at(total, episodes)
            state = State(race_time_s=total, stint_lap=lap.stint_lap - 1, pitting_now=bool(lap.is_out_lap),
                          last_stop_driver_change=previous is not None and lap.DRIVER_NUMBER != previous.DRIVER_NUMBER,
                          last_stop_flag=flag_at(total, episodes))   # pit entry is the end of the in-lap, which is now
            total += lap_time(state, params, flag, Draws(), params.age_slope_s, total, episodes)[0]
        previous = lap
    return total


def caution_bias(table: pd.DataFrame, calibration: dict, model: str = "M3") -> dict:
    """E-023, descriptive: does each race's median signed error still follow its number of cautions?"""
    per_race = pd.DataFrame(calibration["caution"]["per_race"]).set_index("event_key")
    errors = table.groupby("event_key")[f"{model}_error_pct"].median()
    cautions = (per_race["SF"] + per_race["FCY"]).reindex(errors.index)
    return {"spearman": float(errors.rank().corr(cautions.rank())), "races": int(len(errors)),   # Spearman: Pearson on ranks, no SciPy
            "by_race": [{"event_key": e, "cautions": int(cautions[e]), "median_signed_pct": float(errors[e])} for e in errors.index]}


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
