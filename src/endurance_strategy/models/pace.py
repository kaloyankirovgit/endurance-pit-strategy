"""Stint-age pace, pit loss and race-pace predictors, as registered in E-020.

Everything here is INFERRED or RECONSTRUCTED from timing data. The stint-age effect combines fuel,
tyres and anything else that moves steadily with laps since a stop (D-005), and `stint_lap` is not
tyre age, because the timing doesn't say which stops changed tyres.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from endurance_strategy.features.clean_laps import EXCLUSION_FLAGS
from endurance_strategy.features.practice import clean_practice_mask, practice_pace  # noqa: F401  (re-exported for E-020's code)
from endurance_strategy.io.load import CORPUS_V1
from endurance_strategy.models.traffic import LOOSE_SLOW_LAP_RATIO, STINT_KEY, T_975

SEALED_SEASON = "2026"
OPEN_SEASONS = ("2024", "2025")
CLASSES = ("HYPERCAR", "LMGT3")
FIRST_FIT_AGE = 3  # Stint lap 2 is warm-up: reported on its own and kept out of the straight-line fits.
ANCHOR_LAPS = 5
MIN_HOLDOUT_STINT_LAPS = 10
SUPPORT_MIN_STINTS = 30
SUPPORT_MIN_RACES = 4
REFERENCE_LAPS = 5
MIN_REFERENCE_LAPS = 3


class SealedDataError(RuntimeError):
    """Raised when 2026 is reached without being explicitly opened (D-031)."""


def require_open(events, open_sealed: bool = False) -> None:
    sealed = sorted({event for event in events if str(event).startswith(SEALED_SEASON)})
    if sealed and not open_sealed:
        raise SealedDataError(f"{len(sealed)} sealed events requested. 2026 stays closed until the simulator's final test")


def race_list(season: str) -> list[str]:
    return [event for event in CORPUS_V1 if event.startswith(season) and "LE_MANS" not in event]


def load_open_seasons(path: Path, seasons: tuple[str, ...] = OPEN_SEASONS, open_sealed: bool = False) -> pd.DataFrame:
    """Read only the named seasons' rows, so sealed rows never reach memory."""
    require_open(seasons, open_sealed)
    events = [event for event in CORPUS_V1 if event[:4] in seasons]
    return pq.read_table(path, filters=[("event_key", "in", events)]).to_pandas()


def circuit_of(event_key: str) -> str:
    return event_key[5:]


# --- Part A and B: stint age -------------------------------------------------------------------


def analysis_laps(laps: pd.DataFrame, slow_lap_rule: str = "standard", min_stint_laps: int = 5) -> pd.DataFrame:
    """Clean laps in stints of at least `min_stint_laps` such laps, leaving out stints that began with a garage stop."""
    frame = laps.copy()
    frame["garage_stint"] = frame.groupby(STINT_KEY)["is_garage_stop"].transform("any")
    frame["stint_all_green"] = frame["FLAG_AT_FL"].isin(["GF", "FF"]).groupby([frame[key] for key in STINT_KEY]).transform("all")  # FF is the finish flag.
    flags = [flag for flag in EXCLUSION_FLAGS if flag != "is_slow_lap"]
    keep = ~frame[flags].any(axis=1) & ~frame["garage_stint"] & frame["CLASS"].isin(CLASSES)
    if slow_lap_rule == "standard":
        keep &= ~frame["is_slow_lap"]
    elif slow_lap_rule == "loose":
        reference = frame["LAP_TIME_S"].where(keep).groupby([frame["event_key"], frame["CLASS"]]).transform("median")
        keep &= frame["LAP_TIME_S"].le(LOOSE_SLOW_LAP_RATIO * reference)
    else:
        raise ValueError(f"unknown slow_lap_rule {slow_lap_rule!r}")
    frame = frame[keep]
    frame = frame[frame.groupby(STINT_KEY)["LAP_TIME_S"].transform("size") >= min_stint_laps].copy()
    frame["lap_pct"] = 100.0 * frame["LAP_TIME_S"] / frame.groupby(["event_key", "CLASS"])["LAP_TIME_S"].transform("median")
    return frame


def sample_counts(frame: pd.DataFrame) -> dict:
    """Sample size in every unit, not only laps."""
    return {
        "races": int(frame["event_key"].nunique()),
        "circuits": int(frame["event_key"].map(circuit_of).nunique()),
        "car_entries": int(frame.groupby(["event_key", "NUMBER"]).ngroups),
        "drivers": int(frame["DRIVER_NAME"].nunique()),
        "stints": int(frame.groupby(STINT_KEY).ngroups),
        "laps": int(len(frame)),
    }


def support_by_age(frame: pd.DataFrame) -> pd.DataFrame:
    """Per class and stint age: how many stints, and from how many races, reach that age."""
    return (frame.groupby(["CLASS", "stint_lap"])
            .agg(stints=("stint_number", "size"), races=("event_key", "nunique"))
            .reset_index())


def support_limit(frame: pd.DataFrame, min_stints: int = SUPPORT_MIN_STINTS, min_races: int = SUPPORT_MIN_RACES) -> dict[str, int]:
    """The highest age per class up to which every age from `FIRST_FIT_AGE` meets the support rule. 0 if none does."""
    table = support_by_age(frame)
    limits = {}
    for car_class, rows in table.groupby("CLASS"):
        good = set(rows.loc[(rows["stints"] >= min_stints) & (rows["races"] >= min_races), "stint_lap"])
        age = FIRST_FIT_AGE
        while age + 1 in good:
            age += 1
        limits[car_class] = age if FIRST_FIT_AGE in good else 0
    return limits


def within_stint_coefficients(frame: pd.DataFrame, columns: list[str], y: str = "LAP_TIME_S") -> np.ndarray:
    """Least squares of `y` on `columns` with one intercept per stint, by demeaning within stint."""
    ids = frame.groupby(STINT_KEY, sort=False).ngroup().to_numpy()
    counts = np.bincount(ids)
    demeaned = lambda values: values - (np.bincount(ids, values) / counts)[ids]
    x = np.column_stack([demeaned(frame[column].to_numpy(dtype=float)) for column in columns])
    return np.linalg.lstsq(x, demeaned(frame[y].to_numpy(dtype=float)), rcond=None)[0]


def race_coefficients(frame: pd.DataFrame, columns: list[str], y: str = "LAP_TIME_S") -> pd.DataFrame:
    """One within-stint fit per race and class. Races are the independent unit, so each gets equal weight later."""
    rows = []
    for (event, car_class), group in frame.groupby(["event_key", "CLASS"]):
        rows.append({"event_key": event, "CLASS": car_class,
                     **dict(zip(columns, within_stint_coefficients(group, columns, y)))})
    return pd.DataFrame(rows)


def with_age_terms(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.assign(age=frame["stint_lap"].astype(float), age_sq=frame["stint_lap"].astype(float) ** 2)


def t_half_width(values, extra_variance: float = 0.0) -> float:
    values = np.asarray(values, dtype=float)
    n = len(values)
    return float(T_975[n - 1] * values.std(ddof=1) * np.sqrt(1 / n + extra_variance))


def mean_with_t_interval(values) -> dict:
    values = np.asarray(values, dtype=float)
    half = t_half_width(values)
    return {"mean": float(values.mean()), "t_interval": [float(values.mean() - half), float(values.mean() + half)], "races": int(len(values))}


def prediction_interval(values) -> list[float]:
    """95% interval for one new race's value: the mean's uncertainty plus the spread between races."""
    values = np.asarray(values, dtype=float)
    half = t_half_width(values, extra_variance=1.0)
    return [float(values.mean() - half), float(values.mean() + half)]


def race_bootstrap_interval(race_values, n_boot: int = 2000, seed: int = 20261109, statistic=np.mean) -> list[float]:
    """Percentile interval of a statistic over races, drawing whole races with replacement."""
    values = np.asarray(race_values, dtype=float)
    rng = np.random.default_rng(seed)
    draws = statistic(values[rng.integers(0, len(values), size=(n_boot, len(values)))], axis=1)
    return [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]


def median_age_profile(frame: pd.DataFrame, limit: int) -> dict[int, float]:
    """Baseline B: median at each age minus the median at ages 3 to 7, per race, averaged equally over races.

    The value at age 2 is the warm-up figure E-020 reports on its own.
    """
    profiles = []
    for _, race in frame.groupby("event_key"):
        reference = race.loc[race["stint_lap"].between(3, 7), "LAP_TIME_S"].median()
        profiles.append(race.groupby("stint_lap")["LAP_TIME_S"].median() - reference)
    return {int(age): float(value) for age, value in pd.concat(profiles, axis=1).mean(axis=1).items() if age <= limit}


def fit_age_models(frame: pd.DataFrame, limits: dict[str, int], circuit_model: bool = True) -> dict:
    """Fit B, L, Q and C per class on laps at supported ages only.

    C keeps one slope per circuit, so it needs one race per circuit. Pass `circuit_model=False` when
    fitting several seasons together.
    """
    models: dict[str, dict] = {}
    for car_class in CLASSES:
        supported = frame[(frame["CLASS"] == car_class) & (frame["stint_lap"] <= limits[car_class])]
        rows = with_age_terms(supported[supported["stint_lap"] >= FIRST_FIT_AGE])
        linear = race_coefficients(rows, ["age"])
        quadratic = race_coefficients(rows, ["age", "age_sq"])
        if circuit_model and linear["event_key"].map(circuit_of).duplicated().any():
            raise ValueError("C needs one race per circuit")
        models[car_class] = {
            "limit": limits[car_class],
            "B": median_age_profile(supported, limits[car_class]),
            "L": float(linear["age"].mean()),
            "Q": [float(quadratic["age"].mean()), float(quadratic["age_sq"].mean())],
            **({"C": {circuit_of(event): float(slope) for event, slope in zip(linear["event_key"], linear["age"])}} if circuit_model else {}),
            "race_slopes": {event: float(slope) for event, slope in zip(linear["event_key"], linear["age"])},
        }
    return models


def slope_summary(frame: pd.DataFrame, limits: dict[str, int], extra: tuple[str, ...] = (), first_age: int = FIRST_FIT_AGE,
                  seed: int = 20261109, n_boot: int = 2000, classes: tuple[str, ...] = CLASSES) -> dict:
    """The per-class stint-age slope in seconds and as a percentage of the race's median clean lap, with intervals over races."""
    out = {}
    columns = ["age", *extra]
    for car_class in classes:
        rows = frame[(frame["CLASS"] == car_class) & frame["stint_lap"].between(first_age, limits[car_class])].dropna(subset=list(extra))
        rows = with_age_terms(rows)
        summary = {"laps": int(len(rows)), "stints": int(rows.groupby(STINT_KEY).ngroups)}
        for unit, y in (("s_per_lap", "LAP_TIME_S"), ("pct_per_lap", "lap_pct")):
            coefficients = race_coefficients(rows, columns, y)
            slopes = coefficients.set_index("event_key")["age"]
            summary[unit] = {**mean_with_t_interval(slopes), "bootstrap": race_bootstrap_interval(slopes, n_boot=n_boot, seed=seed),
                             "race_slopes": {event: float(value) for event, value in slopes.items()}}
        out[car_class] = summary
    return out


def is_unstable(primary: dict, alternative_slope: float) -> bool:
    """E-020's test: moved by more than the interval's half-width, or changed sign when the interval excludes zero."""
    low, high = primary["t_interval"]
    moved = abs(alternative_slope - primary["mean"]) > (high - low) / 2
    flipped = (low > 0 or high < 0) and np.sign(alternative_slope) != np.sign(primary["mean"])
    return bool(moved or flipped)


def age_effect(name: str, model: dict, ages: np.ndarray, circuit: str) -> np.ndarray:
    """f(age) for one of the registered models. Only differences in f between ages are meaningful."""
    ages = np.asarray(ages, dtype=float)
    if name == "F":
        return np.zeros(len(ages))
    if name == "B":
        profile = model["B"]
        known = sorted(profile)
        return np.interp(ages, known, [profile[age] for age in known])  # Flat beyond the last supported age.
    if name == "L":
        return model["L"] * ages
    if name == "Q":
        return model["Q"][0] * ages + model["Q"][1] * ages ** 2
    if name == "C":
        return model["C"][circuit] * ages
    raise ValueError(f"unknown model {name!r}")


def holdout_stint_errors(frame: pd.DataFrame, models: dict, names: tuple[str, ...] = ("F", "B", "L", "Q", "C")) -> pd.DataFrame:
    """Per race, class and model: errors predicting later laps of a stint from its first laps alone.

    A stint's first `ANCHOR_LAPS` analysis laps at age 3 or above set its level. Later laps at ages
    within the fit's support are scored, using those earlier laps and the age effect fitted on other
    races. Lap selection still uses whole-race information, so the test is retrospective.
    """
    rows = []
    for (event, car_class), race in frame.groupby(["event_key", "CLASS"]):
        model, circuit = models[car_class], circuit_of(event)
        errors: dict[str, list[np.ndarray]] = {name: [] for name in names}
        for _, stint in race[race["stint_lap"] >= FIRST_FIT_AGE].sort_values("stint_lap").groupby(STINT_KEY):
            if len(stint) < MIN_HOLDOUT_STINT_LAPS:
                continue
            anchor, later = stint.iloc[:ANCHOR_LAPS], stint.iloc[ANCHOR_LAPS:]
            later = later[later["stint_lap"] <= model["limit"]]
            if later.empty:
                continue
            for name in names:
                level = anchor["LAP_TIME_S"].mean() - age_effect(name, model, anchor["stint_lap"].to_numpy(), circuit).mean()
                predicted = level + age_effect(name, model, later["stint_lap"].to_numpy(), circuit)
                errors[name].append(later["LAP_TIME_S"].to_numpy() - predicted)
        for name in names:
            if errors[name]:
                joined = np.concatenate(errors[name])
                rows.append({"event_key": event, "CLASS": car_class, "model": name, "laps": len(joined),
                             "stints": len(errors[name]), "mae_s": float(np.abs(joined).mean()), "mean_error_s": float(joined.mean())})
    return pd.DataFrame(rows)


def paired_comparison(better: pd.Series, simpler: pd.Series) -> dict:
    """Does `better` (one error per race) beat `simpler`? Positive differences favour `better`."""
    differences = (simpler - better).dropna()
    summary = mean_with_t_interval(differences)
    summary["replaces_simpler"] = bool(summary["t_interval"][0] > 0)
    return summary


def decision_ladder(errors: pd.DataFrame, car_class: str) -> dict:
    """E-020's fixed order: F holds, B then L challenge the holder, Q and C challenge L only if L holds."""
    table = errors[errors["CLASS"] == car_class].pivot(index="event_key", columns="model", values="mae_s")
    holder, steps = "F", []
    for challenger in ("B", "L"):
        result = paired_comparison(table[challenger], table[holder])
        steps.append({"challenger": challenger, "against": holder, **result})
        if result["replaces_simpler"]:
            holder = challenger
    description = {}
    if holder == "L":
        winners = []
        for challenger in ("Q", "C"):
            result = paired_comparison(table[challenger], table["L"])
            steps.append({"challenger": challenger, "against": "L", **result})
            if result["replaces_simpler"]:
                winners.append(challenger)
        if winners:
            holder = min(winners, key=lambda name: table[name].mean())
    else:
        description = {name: paired_comparison(table[name], table["L"]) for name in ("Q", "C")}
    return {"holder": holder, "steps": steps, "not_tested_description_only": description,
            "mean_race_mae_s": {name: float(table[name].mean()) for name in table.columns}}


def slope_coverage(fit_race_slopes, check_race_slopes) -> dict:
    """How many held-out race slopes fall inside the prediction interval from the fit races."""
    low, high = prediction_interval(fit_race_slopes)
    check = np.asarray(check_race_slopes, dtype=float)
    inside = int(((check >= low) & (check <= high)).sum())
    return {"interval": [low, high], "width": high - low, "inside": inside, "of": int(len(check)), "under_coverage": inside < len(check) - 1}


# --- Part C: pit loss --------------------------------------------------------------------------


def pit_events(laps: pd.DataFrame, usable: str = "is_usable_for_pace_model") -> pd.DataFrame:
    """One row per stop with its reconstructed pit loss and, if it has none, the reason.

    Pit loss is in-lap time + out-lap time minus twice the car's reference pace. The reference is
    the median of its last clean laps before the in-lap, in the stint ending at the stop, and first
    clean laps at age 3 or above after the out-lap, in the stint starting at the stop. It uses laps
    from after the stop, so it's a calibration quantity and isn't race-time information.
    """
    rows = []
    for (event, number), car in laps.sort_values(["event_key", "NUMBER", "LAP_NUMBER"]).groupby(["event_key", "NUMBER"]):
        records = car.reset_index(drop=True)
        for index in records.index[records["is_out_lap"]]:
            out_lap = records.loc[index]
            in_lap = records.loc[index - 1] if index else None  # An out-lap as a car's first row is a pit-lane start.
            status, reference, loss = "pit_lane_start", np.nan, np.nan
            if in_lap is not None:
                before = records[(records["stint_number"] == in_lap["stint_number"]) & records[usable] & (records["LAP_NUMBER"] < in_lap["LAP_NUMBER"])].tail(REFERENCE_LAPS)
                after = records[(records["stint_number"] == out_lap["stint_number"]) & records[usable] & records["stint_lap"].ge(FIRST_FIT_AGE)].head(REFERENCE_LAPS)
                status = _stop_status(in_lap, out_lap, len(before), len(after))
                if status == "eligible":
                    reference = float(pd.concat([before["LAP_TIME_S"], after["LAP_TIME_S"]]).median())
                    loss = float(in_lap["LAP_TIME_S"] + out_lap["LAP_TIME_S"] - 2 * reference)
            rows.append({
                "event_key": event, "NUMBER": number, "CLASS": out_lap["CLASS"], "out_lap": int(out_lap["LAP_NUMBER"]),
                "stint_number": int(out_lap["stint_number"]), "status": status, "pit_time_s": out_lap["PIT_TIME_S"],
                "driver_changed": bool(in_lap is not None and out_lap["DRIVER_NUMBER"] != in_lap["DRIVER_NUMBER"]),
                "reference_pace_s": reference, "pit_loss_s": loss,
            })
    return pd.DataFrame(rows)


def _stop_status(in_lap: pd.Series, out_lap: pd.Series, n_before: int, n_after: int) -> str:
    if out_lap["is_garage_stop"]:
        return "garage"
    if not in_lap["is_in_lap"] or out_lap["LAP_NUMBER"] != in_lap["LAP_NUMBER"] + 1:
        return "not_consecutive"
    if out_lap["is_in_lap"] or in_lap["is_out_lap"]:
        return "out_in_lap"
    if in_lap["FLAG_AT_FL"] != "GF" or out_lap["FLAG_AT_FL"] != "GF":
        return "caution"
    if in_lap["is_wet"] or out_lap["is_wet"] or in_lap["is_field_slow"] or out_lap["is_field_slow"]:
        return "wet_or_field_slow"
    if pd.isna(in_lap["LAP_TIME_S"]) or pd.isna(out_lap["LAP_TIME_S"]):
        return "missing_time"
    if n_before < MIN_REFERENCE_LAPS or n_after < MIN_REFERENCE_LAPS:
        return "too_few_reference_laps"
    return "eligible"


def routine_stop_events(laps: pd.DataFrame) -> pd.DataFrame:
    """`pit_events` with the registered reference: the car's analysis laps, as selected by `analysis_laps`."""
    return pit_events(laps.assign(is_analysis_lap=laps.index.isin(analysis_laps(laps).index)), usable="is_analysis_lap")


def eligible_stops(events: pd.DataFrame) -> pd.DataFrame:
    return events[events["status"] == "eligible"].assign(circuit=lambda f: f["event_key"].map(circuit_of))


def stop_quantiles(events: pd.DataFrame, by: list[str]) -> list[dict]:
    """10th, 50th and 90th percentiles of pit loss and pit-lane time, with the number of stops and cars behind each."""
    rows = []
    for key, group in eligible_stops(events).groupby(by):
        key = key if isinstance(key, tuple) else (key,)
        row = {**dict(zip(by, key)), "stops": int(len(group)), "cars": int(group.groupby(["event_key", "NUMBER"]).ngroups)}
        for name, column in (("pit_loss_s", "pit_loss_s"), ("pit_time_s", "pit_time_s")):
            row[name] = {f"p{int(q * 100)}": float(group[column].quantile(q)) for q in (0.1, 0.5, 0.9)}
        rows.append(row)
    return rows


def car_bootstrap_median(stops: pd.DataFrame, n_boot: int = 2000, seed: int = 20261109) -> list[float]:
    """Within-race uncertainty of a median, drawing whole cars. It says nothing about variation between years."""
    by_car = [group["pit_loss_s"].to_numpy() for _, group in stops.groupby(["event_key", "NUMBER"])]
    rng = np.random.default_rng(seed)
    medians = [np.median(np.concatenate([by_car[i] for i in rng.integers(0, len(by_car), len(by_car))])) for _ in range(n_boot)]
    return [float(np.percentile(medians, 2.5)), float(np.percentile(medians, 97.5))]


def pit_holdout(fit: pd.DataFrame, check: pd.DataFrame) -> dict:
    """Per class: does the same circuit's previous median beat the class-wide one? Races are the unit."""
    fit_medians = eligible_stops(fit).groupby(["event_key", "CLASS"])["pit_loss_s"].median()
    check_medians = eligible_stops(check).groupby(["event_key", "CLASS"])["pit_loss_s"].median()
    out = {}
    for car_class in CLASSES:
        class_figure = float(fit_medians.xs(car_class, level="CLASS").median())
        rows = []
        for event, observed in check_medians.xs(car_class, level="CLASS").items():
            circuit_figure = float(fit_medians[(previous_season_event(event), car_class)])
            rows.append({"event_key": event, "observed_s": float(observed), "class_error_s": abs(class_figure - observed),
                         "circuit_error_s": abs(circuit_figure - observed)})
        table = pd.DataFrame(rows).set_index("event_key")
        out[car_class] = {"class_figure_s": class_figure, "races": table.reset_index().to_dict("records"),
                          "circuit_vs_class": paired_comparison(table["circuit_error_s"], table["class_error_s"])}
    return out


def pit_coverage(fit: pd.DataFrame, check: pd.DataFrame, driver_changed: bool | None = None, min_fit_stops: int = 5) -> dict:
    """Share of held-out stops inside the same circuit's earlier 10th to 90th range, per race and class (nominal 80%)."""
    fit_stops, check_stops = eligible_stops(fit), eligible_stops(check)
    if driver_changed is not None:
        fit_stops = fit_stops[fit_stops["driver_changed"] == driver_changed]
        check_stops = check_stops[check_stops["driver_changed"] == driver_changed]
    out = {}
    for car_class in CLASSES:
        rows, skipped = [], 0
        for event, stops in check_stops[check_stops["CLASS"] == car_class].groupby("event_key"):
            earlier = fit_stops[(fit_stops["event_key"] == previous_season_event(event)) & (fit_stops["CLASS"] == car_class)]["pit_loss_s"]
            if len(earlier) < min_fit_stops:
                skipped += 1
                continue
            low, high = earlier.quantile(0.1), earlier.quantile(0.9)
            rows.append({"event_key": event, "stops": int(len(stops)), "share_inside": float(stops["pit_loss_s"].between(low, high).mean())})
        shares = [row["share_inside"] for row in rows]
        median = float(np.median(shares)) if shares else float("nan")
        out[car_class] = {"race_classes": rows, "skipped_too_few_earlier_stops": skipped, "median_share_inside": median, "carries_over": bool(0.7 <= median <= 0.9),
                          "outside_70_to_90": int(sum(not 0.7 <= share <= 0.9 for share in shares))}
    return out


# --- Part D: what predicts a race's clean pace -------------------------------------------------


def race_target(laps: pd.DataFrame) -> pd.Series:
    return laps[laps["is_usable_for_pace_model"]].groupby(["event_key", "CLASS"])["LAP_TIME_S"].median()


def previous_season_event(event_key: str) -> str:
    return f"{int(event_key[:4]) - 1}_{circuit_of(event_key)}"


def pace_predictions(target: pd.Series, practice: pd.Series, fit_events: list[str], check_events: list[str]) -> pd.DataFrame:
    """P1 (last season's race), P2 (practice × a class ratio from the fit races) and P3 (raw practice)."""
    joined = pd.DataFrame({"target": target, "practice": practice}).dropna()
    fit = joined[joined.index.get_level_values("event_key").isin(fit_events)]
    ratio = (fit["target"] / fit["practice"]).groupby(level="CLASS").mean()
    rows = []
    for (event, car_class), row in joined[joined.index.get_level_values("event_key").isin(check_events)].iterrows():
        earlier = (previous_season_event(event), car_class)
        rows.append({
            "event_key": event, "CLASS": car_class, "target_s": row["target"],
            "P1": target.get(earlier, np.nan),
            "P2": row["practice"] * ratio.get(car_class, np.nan),
            "P3": row["practice"],
        })
    table = pd.DataFrame(rows)
    for name in ("P1", "P2", "P3"):
        table[f"{name}_abs_error_s"] = (table[name] - table["target_s"]).abs()
    return table


def pace_comparisons(predictions: pd.DataFrame, expected_races: int | None = None) -> dict:
    """E-020's three comparisons. Races are the unit, with the classes averaged within each race."""
    errors = ["P1_abs_error_s", "P2_abs_error_s", "P3_abs_error_s"]
    if predictions[errors].isna().any().any() or predictions.groupby("event_key")["CLASS"].nunique().nunique() != 1:
        raise ValueError("every race needs the same classes and all three predictions")
    races = predictions.groupby("event_key")[errors].mean()
    if expected_races is not None and len(races) != expected_races:
        raise ValueError(f"expected {expected_races} races, got {len(races)}")
    out = {}
    for better, simpler in (("P2", "P3"), ("P2", "P1"), ("P1", "P3")):
        result = mean_with_t_interval(races[f"{simpler}_abs_error_s"] - races[f"{better}_abs_error_s"])
        low, high = result["t_interval"]
        result["clear_gap"] = bool(low > 0 or high < 0)
        out[f"{better}_vs_{simpler}"] = result
    return out
