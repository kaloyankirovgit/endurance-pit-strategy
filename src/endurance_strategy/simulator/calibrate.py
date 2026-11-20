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
SPREAD_GRID = np.round(np.arange(0.0, 6.01, 0.2), 2)    # E-023: candidate 1/k for the per-race caution rate
SPREAD_RACES_PER_POINT = 3000   # simulated races per grid point
SPREAD_CHECKS = 200             # parametric refits at the fitted 1/k
SPREAD_SEED = 20261120


def race_hours(laps: pd.DataFrame) -> pd.Series:
    """OBSERVED race length per event, in whole hours (6, 8 or 10)."""
    return (laps.groupby("event_key")["ELAPSED_S"].max() / 3600).round().astype(int)


def caution_episodes(laps: pd.DataFrame) -> pd.DataFrame:
    """RECONSTRUCTED caution periods from line crossings across the field.

    Runs of crossings under a caution flag (SF or FCY) are merged when the gap between them is under one
    median green lap, so a stray green crossing doesn't split a safety car and an FCY that turns into a
    safety car stays one episode. A merged episode takes the type with more crossings. A red flag (RF)
    isn't modelled. E-023: the episode runs from the first to the last crossing under the caution, so it is
    the period the caution flag shows at the line, and a stop or pit closure in it matches the real flag. (E-022
    added one green lap after the last crossing.)
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
                        "duration_s": r["end"] - r["start"], "crossings": sum(counts.values()),
                        "mixed": all(counts.values())})
    return pd.DataFrame(out, columns=["event_key", "kind", "start_s", "duration_s", "crossings", "mixed"])


def _per_6h_variance(counts: np.ndarray, hours: np.ndarray) -> float:
    return float(np.var(counts / hours * 6, ddof=1))


def _simulated_counts(kind: str, inverse_shape: float, rates_per_green_h: dict, durations_s: dict, hours: np.ndarray,
                      rng: np.random.Generator) -> np.ndarray:
    """Caution counts of one type from the simulator's own generator, one race per entry of `hours`."""
    from endurance_strategy.simulator.engine import draw_cautions
    shape = {kind: 1.0 / inverse_shape} if inverse_shape > 0 else None
    randomness = Randomness(caution_rate_per_green_s={k: v / 3600 for k, v in rates_per_green_h.items()},
                            caution_durations_s={k: np.asarray(v) for k, v in durations_s.items()}, caution_rate_shape=shape)
    return np.array([sum(1 for e in draw_cautions(randomness, h * 3600.0, rng) if e[2] == kind) for h in hours])


def rate_spread(per_race: pd.DataFrame, rates_per_green_h: dict, durations_s: dict, grid=SPREAD_GRID,
                races_per_point: int = SPREAD_RACES_PER_POINT, checks: int = SPREAD_CHECKS, seed: int = SPREAD_SEED) -> dict:
    """INFERRED (E-023): per caution type, how much each race's own rate varies (1/k of a gamma multiplier),
    fitted with the rate itself so the mean count stays where it was observed.

    Simulated moments with the simulator's own generator and the observed mix of race lengths. A gamma
    multiplier alone lowers the mean count, because races that draw a high rate fill with cautions and run out
    of green time. So for each 1/k on the grid, the rate is first rescaled until the simulated mean count per
    race matches the observed one, and then the 1/k whose variance of counts per 6 hours is closest to the
    observed one is kept. If even the top of the grid falls short, `out_of_reach` is set and the shortfall
    reported. The other type keeps its constant rate meanwhile. Then a parametric check: `checks` sets of as
    many races as observed, drawn at the fit, are refitted on the same curve to show how loosely they pin 1/k."""
    rng = np.random.default_rng(seed)
    hours = per_race["hours"].to_numpy(dtype=float)
    many = np.resize(hours, races_per_point)
    out = {}
    for kind in CAUTIONS:
        observed_counts = per_race[kind].to_numpy(dtype=float)
        observed, target_mean = _per_6h_variance(observed_counts, hours), float(observed_counts.mean())
        if rates_per_green_h.get(kind, 0) <= 0 or target_mean == 0:
            out[kind] = {"inverse_shape": 0.0, "shape": None, "rate_per_green_hour": rates_per_green_h.get(kind, 0.0),
                         "out_of_reach": False, "races": int(len(hours))}
            continue
        curve, rates = [], []
        for x in grid:
            rate = dict(rates_per_green_h)
            half = many[: races_per_point // 2]
            target = target_mean * half.mean() / hours.mean()   # the observed mean count, for this mix of race lengths
            for _ in range(3):   # rescale the rate until the simulated mean count matches
                simulated = _simulated_counts(kind, x, rate, durations_s, half, rng)
                rate[kind] *= target / max(simulated.mean(), 1e-9)
            counts = _simulated_counts(kind, x, rate, durations_s, many, rng)
            curve.append(_per_6h_variance(counts, many))
            rates.append(rate[kind])
        curve = np.array(curve)
        index = int(np.argmin(np.abs(curve - observed)))
        fitted = float(grid[index])
        rate_at_fit = dict(rates_per_green_h, **{kind: rates[index]})
        refits = [float(grid[int(np.argmin(np.abs(curve - _per_6h_variance(
            _simulated_counts(kind, fitted, rate_at_fit, durations_s, hours, rng), hours))))]) for _ in range(checks)]
        out[kind] = {"inverse_shape": fitted, "shape": 1.0 / fitted if fitted > 0 else None, "rate_per_green_hour": rates[index],
                     "observed_variance_per_6h": observed, "observed_mean_per_race": target_mean,
                     "simulated_variance_per_6h_at_fit": float(curve[index]), "constant_rate_variance_per_6h": float(curve[0]),
                     "out_of_reach": bool(index == len(grid) - 1 and curve[-1] < observed),
                     "refit_p05": float(np.quantile(refits, 0.05)), "refit_p95": float(np.quantile(refits, 0.95)),
                     "refit_share_at_zero": float(np.mean(np.array(refits) == 0)), "races": int(len(hours)),
                     "grid": [float(x) for x in grid], "curve": [round(float(v), 3) for v in curve],
                     "rates": [round(float(r), 4) for r in rates]}
    return out


def caution_progress(laps: pd.DataFrame, episodes: pd.DataFrame) -> dict:
    """INFERRED (E-023): per class and caution type, the share of green speed a car keeps inside an episode.

    Fitted the way the engine applies it. For each car and episode, take the car's last crossing at or before
    the episode's start and its first crossing at or after its end. Over that bracket the car covered
    (laps between them) × (its mean clean lap) of green running; the part of the bracket outside the episode
    is taken at full speed, and the rest of that work was done inside the episode. The share is the sum of
    that work over the sum of episode durations. The car's mean clean lap includes traffic, as the engine's
    full green lap does. Left out: lap 1, a bracket with a pit lap, a red flag or another episode in it, and a
    car with no crossing after the episode. A cell with no car-episodes is reported as None, not filled in."""
    out = {car_class: {kind: [0.0, 0.0, 0] for kind in CAUTIONS} for car_class in CLASSES}
    restart = {car_class: [] for car_class in CLASSES}
    by_event = {event: group.sort_values("start_s") for event, group in episodes.groupby("event_key")}
    for (event, number), car in laps[laps["CLASS"].isin(CLASSES)].groupby(["event_key", "NUMBER"]):
        if event not in by_event:
            continue
        car = car.sort_values("LAP_NUMBER")
        clean = car.loc[car["is_usable_for_pace_model"], "LAP_TIME_S"].mean()
        if not clean > 0:
            continue
        times = car["ELAPSED_S"].to_numpy(dtype=float)
        lap_count = car["LAP_NUMBER"].to_numpy(dtype=float)
        blocked = car.loc[car["is_pit_lap"] | car["FLAG_AT_FL"].eq("RF"), "ELAPSED_S"].to_numpy(dtype=float)
        car_class = car["CLASS"].iloc[0]
        race_episodes = by_event[event]
        for episode in race_episodes.itertuples():
            start, end = episode.start_s, episode.start_s + episode.duration_s
            a = np.searchsorted(times, start, side="right") - 1
            b = np.searchsorted(times, end, side="left")
            if a < 1 or b >= len(times):
                continue
            t_a, t_b = times[a], times[b]
            if ((blocked > t_a) & (blocked <= t_b)).any():
                continue
            others = race_episodes[(race_episodes["start_s"] != episode.start_s)]
            if ((others["start_s"] < t_b) & (others["start_s"] + others["duration_s"] > t_a)).any():
                continue
            work = (lap_count[b] - lap_count[a]) * clean
            green = (t_b - t_a) - episode.duration_s
            cell = out[car_class][episode.kind]
            cell[0] += work - green
            cell[1] += episode.duration_s
            cell[2] += 1
            # The restart lap: the one starting at the bracket's end, if it starts within one clean lap of the
            # episode's end (the engine's rule), is green throughout, and has no pit stop or red flag.
            if b + 1 < len(times) and t_b - end < clean and not ((blocked > t_b) & (blocked <= times[b + 1])).any() \
                    and not ((others["start_s"] < times[b + 1]) & (others["start_s"] + others["duration_s"] > t_b)).any():
                restart[car_class].append(times[b + 1] - t_b - clean)
    result = {car_class: {kind: {"progress": cell[0] / cell[1] if cell[1] else None, "car_episodes": cell[2]}
                          for kind, cell in kinds.items()} for car_class, kinds in out.items()}
    for car_class in CLASSES:
        result[car_class]["restart"] = {"extra_s": float(np.mean(restart[car_class])) if restart[car_class] else 0.0,
                                        "laps": len(restart[car_class])}
    return result


def caution_model(laps: pd.DataFrame) -> dict:
    """INFERRED: episode rates per hour of green running (so the generator can match them), and lengths."""
    episodes = caution_episodes(laps)
    hours = race_hours(laps)
    green_s = float((hours * 3600).sum() - episodes["duration_s"].sum())
    per_race = (episodes.groupby(["event_key", "kind"]).size().unstack(fill_value=0)
                .reindex(index=hours.index, columns=list(CAUTIONS), fill_value=0))
    per_race["hours"] = hours
    per_race["green_hours"] = (hours * 3600 - episodes.groupby("event_key")["duration_s"].sum().reindex(hours.index, fill_value=0)) / 3600
    rates = {kind: float((episodes["kind"] == kind).sum() / (green_s / 3600)) for kind in CAUTIONS}
    durations = {kind: episodes.loc[episodes["kind"] == kind, "duration_s"].round(1).tolist() for kind in CAUTIONS}
    return {
        "rate_spread": rate_spread(per_race, rates, durations),
        "episodes_by_race": {event: [[round(r.start_s, 1), round(r.start_s + r.duration_s, 1), r.kind] for r in group.itertuples()]
                             for event, group in episodes.groupby("event_key")},
        "racing_hours": float(hours.sum()), "green_hours": green_s / 3600,
        "episodes": {kind: int((episodes["kind"] == kind).sum()) for kind in CAUTIONS},
        "mixed_episodes": int(episodes["mixed"].sum()),
        "rate_per_green_hour": rates,
        "durations_s": durations,
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


def restart_and_incidents(laps: pd.DataFrame) -> dict:
    """INFERRED (E-022 amendment): per class, the restart-lap ratio and the incident process.

    Measured against each car's mean clean lap in that race. A restart lap is green at the line after a
    caution lap. An incident lap is any other green, non-pit lap after lap 1 that the clean-lap rules
    exclude as slow or field-slow (mistakes, slow zones, local yellows, without saying which).
    """
    frame = laps.sort_values(["event_key", "NUMBER", "LAP_NUMBER"])
    clean = frame[frame["is_usable_for_pace_model"]].groupby(["event_key", "NUMBER"])["LAP_TIME_S"].mean().rename("clean_mean")
    frame = frame.join(clean, on=["event_key", "NUMBER"])
    green = frame[frame["FLAG_AT_FL"].eq("GF") & ~frame["is_pit_lap"] & frame["LAP_NUMBER"].gt(1) & frame["clean_mean"].notna()]
    out = {}
    for car_class in CLASSES:
        rows = green[green["CLASS"] == car_class]
        restart = rows[rows["is_after_caution"]]
        others = rows[~rows["is_after_caution"]]
        incident = others[~others["is_usable_for_pace_model"] & (others["is_slow_lap"] | others["is_field_slow"])]
        extra = (incident["LAP_TIME_S"] - incident["clean_mean"]).clip(lower=0)
        out[car_class] = {"restart_lap_ratio": float((restart["LAP_TIME_S"] / restart["clean_mean"]).mean()) if len(restart) else 1.0,
                          "restart_laps": int(len(restart)), "incident_rate": float(len(incident) / len(others)) if len(others) else 0.0,
                          "incident_extra_s": float(extra.mean()) if len(extra) else 0.0, "incident_laps": int(len(incident)),
                          "incident_extra_samples_s": np.round(extra.to_numpy(), 2).tolist()}
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
                         "clean_mean_s": float(group["LAP_TIME_S"].mean()),
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
        "caution_progress": caution_progress(laps, caution_episodes(laps)),
        "caution_lap_ratio": caution_lap_ratio(laps),
        "pit_loss_median_s": {c: {str(k): float(np.median(v)) for k, v in d.items()} for c, d in pits.items()},
        "pit_loss_mean_s": {c: {str(k): float(np.mean(v)) for k, v in d.items()} for c, d in pits.items()},
        "restart_and_incidents": restart_and_incidents(laps),
        "pit_loss_samples_s": {c: {str(k): np.round(v, 2).tolist() for k, v in d.items()} for c, d in pits.items()},
        "lap_residuals_s": {c: np.round(v, 3).tolist() for c, v in lap_residuals(laps).items()},
    }


def car_params(calibration: dict, circuit: str, car_class: str, base_pace_s: float | None = None, **overrides) -> CarParams:
    """The parameters for one class at one circuit, as expected values, since race time is a sum (E-022
    amendment). Base pace defaults to the class's mean clean lap there, with the expected traffic taken off so
    it isn't counted twice. Pit loss is the mean routine stop."""
    row = next(r for r in calibration["circuits"] if r["circuit"] == circuit and r["CLASS"] == car_class)
    traffic = row["traffic_rate"] * TRAFFIC_S_PER_CAR[car_class]
    medians = calibration.get("pit_loss_mean_s", calibration["pit_loss_median_s"])[car_class]
    extras = calibration.get("restart_and_incidents", {}).get(car_class, {})
    progress = calibration.get("caution_progress", {}).get(car_class)
    if progress is not None:   # E-023: cautions priced by time, so the per-lap restart ratio isn't used
        restart_extra = progress.get("restart", {}).get("extra_s", 0.0)
        progress = {kind: progress[kind]["progress"] for kind in CAUTIONS}
        if all(value is None for value in progress.values()):
            progress = None    # no caution in the calibration races, so nothing to price
        elif any(value is None or not 0 < value <= 1 for value in progress.values()):
            raise ValueError(f"caution share for {car_class} is missing or outside (0, 1]: {progress}")
    values = dict(circuit=circuit, car_class=car_class, duration_s=row["hours"] * 3600.0,
                  base_pace_s=(row.get("clean_mean_s", row["clean_median_s"]) if base_pace_s is None else base_pace_s) - traffic,
                  restart_lap_ratio=1.0 if progress else extras.get("restart_lap_ratio", 1.0), caution_progress=progress,
                  restart_extra_s=restart_extra if progress else 0.0,
                  incident_rate=extras.get("incident_rate", 0.0),
                  incident_extra_s=extras.get("incident_extra_s", 0.0),
                  max_stint_laps=row["max_stint_laps"], pit_loss_s={False: medians["False"], True: medians["True"]},
                  age_slope_s=0.0, age_limit_laps=AGE_LIMIT_LAPS[car_class], warm_up_s=WARM_UP_S[car_class], traffic_rate=row["traffic_rate"],
                  traffic_s_per_car=TRAFFIC_S_PER_CAR[car_class], sc_pit_loss_factor=SC_PIT_LOSS_FACTOR, caution_lap_ratio=calibration["caution_lap_ratio"][car_class])
    values.update(overrides)
    return CarParams(**values)


def randomness(calibration: dict, car_class: str, lap_noise: bool = True, pit_spread: bool = True, cautions: bool = True,
               slope_uncertainty: bool = False, rate_by_race: bool = True) -> Randomness:
    """The random parts, each of which can be switched off to see what it adds (simulation.md).

    `slope_uncertainty` draws the stint-age slope once per race from D-032's range (centred on its mean),
    replacing the flat default. It's a sensitivity, since the flat model held (D-032)."""
    caution = calibration["caution"]
    spread = caution.get("rate_spread", {}) if rate_by_race else {}
    shapes = {kind: cell["shape"] for kind, cell in spread.items() if cell["shape"]}
    rates = {kind: (spread[kind]["rate_per_green_hour"] if kind in shapes else rate) for kind, rate in caution["rate_per_green_hour"].items()}
    mean, low, high = AGE_SLOPE_RANGE_S[car_class]
    samples = calibration["pit_loss_samples_s"][car_class]
    return Randomness(
        lap_residuals_s=np.asarray(calibration["lap_residuals_s"][car_class]) if lap_noise else None,
        pit_loss_samples_s={False: np.asarray(samples["False"]), True: np.asarray(samples["True"])} if pit_spread else None,
        caution_rate_per_green_s={k: v / 3600 for k, v in rates.items()} if cautions else None,
        caution_durations_s={k: np.asarray(v) for k, v in caution["durations_s"].items()} if cautions else None,
        caution_rate_shape=shapes if cautions and rate_by_race and shapes else None,
        age_slope_draw=(mean, (high - low) / (2 * 1.96)) if slope_uncertainty else None,
        incident_extra_samples_s=(np.asarray(calibration["restart_and_incidents"][car_class]["incident_extra_samples_s"])
                                  if lap_noise and calibration.get("restart_and_incidents", {}).get(car_class, {}).get("incident_extra_samples_s")
                                  else None),
    )
