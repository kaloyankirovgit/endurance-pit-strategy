from __future__ import annotations

import numpy as np
import pandas as pd

from endurance_strategy.features.clean_laps import EXCLUSION_FLAGS

STINT_KEY = ["event_key", "NUMBER", "stint_number"]
LOOSE_SLOW_LAP_RATIO = 1.25


def analysis_mask(laps: pd.DataFrame, slow_lap_rule: str = "standard") -> pd.Series:
    """Laps fit for the traffic comparison: green, dry, not a pit or first lap, with an exposure count.

    `slow_lap_rule` is "standard" (the 1.07 rule from D-012) or "loose" (only laps over 1.25x the
    class median are dropped). The standard rule also drops some heavily delayed traffic laps,
    which pulls the estimate towards zero; the loose rule is the check on that.
    """
    flags = [f for f in EXCLUSION_FLAGS if f != "is_slow_lap"]
    keep = ~laps[flags].any(axis=1) & laps["candidate_traffic_count"].notna()
    if slow_lap_rule == "standard":
        return keep & ~laps["is_slow_lap"]
    if slow_lap_rule == "loose":
        reference = laps["LAP_TIME_S"].where(keep).groupby([laps["event_key"], laps["CLASS"]]).transform("median")
        return keep & laps["LAP_TIME_S"].le(LOOSE_SLOW_LAP_RATIO * reference)
    raise ValueError(f"unknown slow_lap_rule {slow_lap_rule!r}")


def detrend_within_stint(frame: pd.DataFrame, columns: list[str], trend: str = "linear") -> pd.DataFrame:
    """Each column minus its own stint baseline: the stint mean, or a straight line in stint lap."""
    keys = [frame[k] for k in STINT_KEY]
    out = pd.DataFrame(index=frame.index)
    x_centred = frame["stint_lap"].astype(float) - frame.groupby(keys)["stint_lap"].transform("mean")
    x_ss = (x_centred ** 2).groupby(keys).transform("sum").replace(0, np.nan)
    for column in columns:
        centred = frame[column].astype(float) - frame.groupby(keys)[column].transform("mean")
        if trend == "linear":
            slope = (x_centred * centred).groupby(keys).transform("sum") / x_ss
            centred = centred - slope.fillna(0) * x_centred
        elif trend != "mean":
            raise ValueError(f"unknown trend {trend!r}")
        out[column] = centred
    return out


def stint_residuals(laps: pd.DataFrame, trend: str = "linear", min_laps: int = 5, cap: int = 4, slope_cap: int = 6) -> pd.DataFrame:
    """Lap time and exposure, both measured against the car's own stint baseline.

    One stint is one car, one driver and one set of tyres, so every comparison is within that.
    The exposure count and its 1..cap indicator columns are detrended the same way as the lap
    time; detrending only the lap time would hide part of the effect in the stint baseline.
    Stints with fewer than `min_laps` analysis laps are dropped.
    """
    frame = laps.copy()
    frame = frame[frame.groupby(STINT_KEY)["LAP_TIME_S"].transform("size") >= min_laps].copy()
    frame["exposure_for_slope"] = frame["candidate_traffic_count"].clip(upper=slope_cap)
    bucket = frame["candidate_traffic_count"].clip(upper=cap).astype(int)
    dummies = [f"exposure_is_{k}" for k in range(1, cap + 1)]
    for k, name in enumerate(dummies, start=1):
        frame[name] = (bucket == k).astype(float)
    detrended = detrend_within_stint(frame, ["LAP_TIME_S", "exposure_for_slope"] + dummies, trend)
    frame["lap_residual_s"] = detrended["LAP_TIME_S"]
    frame["exposure_residual"] = detrended["exposure_for_slope"]
    for name in dummies:
        frame[f"{name}_residual"] = detrended[name]
    return frame


def race_totals(frame: pd.DataFrame, cap: int = 4, cluster: str = "event_key") -> dict:
    """Per-race sums that both estimates are built from, so a bootstrap can reweight races instead of copying rows."""
    races = list(frame[cluster].unique())
    level_columns = [f"exposure_is_{k}_residual" for k in range(1, cap + 1)]
    n = len(races)
    totals = {"races": races, "sxy": np.zeros(n), "sxx": np.zeros(n),
              "xtx": np.zeros((n, cap, cap)), "xty": np.zeros((n, cap)), "level_laps": np.zeros((n, cap))}
    for i, (_, rows) in enumerate(frame.groupby(cluster, sort=False)):
        y = rows["lap_residual_s"].to_numpy()
        x = rows["exposure_residual"].to_numpy()
        design = rows[level_columns].to_numpy()
        totals["sxy"][i], totals["sxx"][i] = x @ y, x @ x
        totals["xtx"][i], totals["xty"][i] = design.T @ design, design.T @ y
        totals["level_laps"][i] = rows[[f"exposure_is_{k}" for k in range(1, cap + 1)]].sum().to_numpy()
    return totals


def estimate_from_totals(totals: dict, weights: np.ndarray) -> dict:
    """Seconds per slower car caught, and each exposure level against zero, from weighted race sums.

    Least squares on stint-detrended columns, which is the fixed-effects estimator with a separate
    line per stint. A level with no laps in the weighted sample is NaN.
    """
    slope = float(weights @ totals["sxy"] / (weights @ totals["sxx"]))
    xtx = np.tensordot(weights, totals["xtx"], axes=1)
    xty = weights @ totals["xty"]
    present = (weights @ totals["level_laps"]) > 0
    coefficients = np.full(len(present), np.nan)
    coefficients[present] = np.linalg.solve(xtx[np.ix_(present, present)], xty[present])
    return {
        "slope_s_per_car": slope,
        "difference_from_zero_s": {k + 1: float(c) for k, c in enumerate(coefficients)},
    }


def point_estimates(frame: pd.DataFrame, cap: int = 4) -> dict:
    totals = race_totals(frame, cap)
    return estimate_from_totals(totals, np.ones(len(totals["races"])))


def resample_races(frame: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """One bootstrap sample as rows: draw races with replacement and keep every lap of each drawn race."""
    races = frame["event_key"].unique()
    drawn = races[rng.choice(len(races), size=len(races), replace=True)]
    by_race = {race: rows for race, rows in frame.groupby("event_key")}
    return pd.concat([by_race[race] for race in drawn], ignore_index=True)


def race_bootstrap(frame: pd.DataFrame, n_boot: int = 2000, seed: int = 20261024, cap: int = 4, cluster: str = "event_key") -> dict:
    """95% percentile intervals from resampling whole races (or another `cluster` column, such as circuit).

    This treats races as exchangeable. They share circuits, cars and drivers, which it does not resample.

    Each sample draws races with replacement, the same draw as `resample_races`, and weights
    each race's sums by how often it was drawn.
    """
    totals = race_totals(frame, cap, cluster)
    n = len(totals["races"])
    rng = np.random.default_rng(seed)
    slopes, differences = [], []
    for _ in range(n_boot):
        weights = np.bincount(rng.choice(n, size=n, replace=True), minlength=n).astype(float)
        estimate = estimate_from_totals(totals, weights)
        slopes.append(estimate["slope_s_per_car"])
        differences.append(estimate["difference_from_zero_s"])
    differences = pd.DataFrame(differences)
    interval = lambda values: [float(np.nanpercentile(values, 2.5)), float(np.nanpercentile(values, 97.5))]
    return {
        "n_boot": n_boot,
        "seed": seed,
        "cluster": cluster,
        "clusters": n,
        "slope_s_per_car": interval(slopes),
        "difference_from_zero_s": {int(k): interval(differences[k]) for k in differences.columns},
    }


def joint_fit(frame: pd.DataFrame, columns: list[str], n_boot: int = 2000, seed: int = 20261024,
              cap: int = 6, cluster: str = "event_key") -> dict:
    """Within-stint least squares of lap time on several counts at once, with cluster-bootstrap intervals.

    `frame` is the output of `stint_residuals`. Each count is capped at `cap` and detrended within
    stint the same way as the lap time. Used for the placebo checks.
    """
    frame = frame.dropna(subset=columns)
    counts = frame[columns].clip(upper=cap)
    detrended = detrend_within_stint(pd.concat([frame[STINT_KEY + ["stint_lap", "LAP_TIME_S"]], counts], axis=1),
                                     ["LAP_TIME_S"] + columns)
    clusters = frame[cluster].to_numpy()
    names = list(pd.unique(clusters))
    x, y = detrended[columns].to_numpy(), detrended["LAP_TIME_S"].to_numpy()
    xtx = np.stack([x[clusters == c].T @ x[clusters == c] for c in names])
    xty = np.stack([x[clusters == c].T @ y[clusters == c] for c in names])
    solve = lambda w: np.linalg.solve(np.tensordot(w, xtx, axes=1), w @ xty)
    rng = np.random.default_rng(seed)
    n = len(names)
    draws = np.array([solve(np.bincount(rng.choice(n, size=n, replace=True), minlength=n).astype(float)) for _ in range(n_boot)])
    estimate = solve(np.ones(n))
    return {
        "laps": int(len(frame)),
        "clusters": n,
        "coefficients_s": {c: float(v) for c, v in zip(columns, estimate)},
        "intervals_s": {c: [float(np.percentile(draws[:, j], 2.5)), float(np.percentile(draws[:, j], 97.5))] for j, c in enumerate(columns)},
    }


def sample_sizes(frame: pd.DataFrame, cap: int = 4) -> dict:
    bucket = frame["candidate_traffic_count"].clip(upper=cap).astype(int)
    return {
        "races": int(frame["event_key"].nunique()),
        "cars": int(frame.groupby(["event_key", "NUMBER"]).ngroups),
        "drivers": int(frame["DRIVER_NAME"].nunique()) if "DRIVER_NAME" in frame else None,
        "stints": int(frame.groupby(STINT_KEY).ngroups),
        "laps": int(len(frame)),
        "laps_by_count": {int(k): int(v) for k, v in bucket.value_counts().sort_index().items()},
        "mean_count_in_top_level": float(frame.loc[bucket == cap, "candidate_traffic_count"].mean()),
    }
