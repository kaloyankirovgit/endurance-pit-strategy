from __future__ import annotations

import numpy as np
import pandas as pd

from endurance_strategy.models.traffic import (
    estimate_from_totals,
    point_estimates,
    joint_fit,
    race_bootstrap,
    race_totals,
    resample_races,
    stint_residuals,
)


def synthetic_laps(effect_s: float, n_races: int = 12, race_effect_sd: float = 0.0, seed: int = 0,
                   exposure_trend: float = 0.0) -> pd.DataFrame:
    """Made-up Hypercar laps with a known time cost per slower car caught.

    Each race has 6 cars with 3 stints of 20 laps. Lap time = car pace + tyre wear in the
    stint + cost per car caught + noise. With `race_effect_sd` the cost varies by race,
    which is what makes laps within a race dependent. With `exposure_trend` the expected count
    rises through the stint, so exposure and tyre age are correlated. `unrelated_count` has no effect.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for race in range(n_races):
        race_cost = effect_s + rng.normal(0, race_effect_sd)
        for car in range(6):
            pace = 100 + rng.normal(0, 0.8)
            for stint in range(1, 4):
                for stint_lap in range(1, 21):
                    caught = rng.poisson(1.5 + exposure_trend * stint_lap / 20)
                    lap = pace + 0.06 * stint_lap + race_cost * caught + rng.normal(0, 0.4)
                    rows.append((f"R{race}", str(car), stint, stint_lap, caught, rng.poisson(1.5), lap))
    return pd.DataFrame(rows, columns=["event_key", "NUMBER", "stint_number", "stint_lap", "candidate_traffic_count",
                                       "unrelated_count", "LAP_TIME_S"])


def test_linear_trend_removes_tyre_wear_within_a_stint():
    stint = pd.DataFrame({"event_key": "R", "NUMBER": "1", "stint_number": 1, "stint_lap": range(1, 11),
                          "candidate_traffic_count": 0, "LAP_TIME_S": [100 + 0.1 * k for k in range(1, 11)]})
    residuals = stint_residuals(stint)["lap_residual_s"]
    assert np.allclose(residuals, 0)


def test_short_stints_are_dropped():
    stint = pd.DataFrame({"event_key": "R", "NUMBER": "1", "stint_number": 1, "stint_lap": [1, 2, 3],
                          "candidate_traffic_count": 0, "LAP_TIME_S": [100.0, 101.0, 102.0]})
    assert stint_residuals(stint, min_laps=5).empty


def test_known_cost_per_car_is_recovered():
    frame = stint_residuals(synthetic_laps(effect_s=1.2))
    estimate = point_estimates(frame)
    assert abs(estimate["slope_s_per_car"] - 1.2) < 0.05
    assert abs(estimate["difference_from_zero_s"][1] - 1.2) < 0.1


def test_zero_cost_gives_an_interval_around_zero():
    frame = stint_residuals(synthetic_laps(effect_s=0.0, race_effect_sd=0.2, seed=1))
    low, high = race_bootstrap(frame, n_boot=300)["slope_s_per_car"]
    assert low < 0 < high


def test_bootstrap_sample_keeps_whole_races():
    frame = synthetic_laps(effect_s=1.0, n_races=5)
    sample = resample_races(frame, np.random.default_rng(3))
    race_size = frame.groupby("event_key").size().iloc[0]
    assert len(sample) == len(frame)
    assert (sample.groupby("event_key").size() % race_size == 0).all()


def test_race_level_interval_is_wider_than_a_row_level_one_when_races_differ():
    frame = stint_residuals(synthetic_laps(effect_s=1.0, race_effect_sd=0.5, seed=2))
    race_low, race_high = race_bootstrap(frame, n_boot=300)["slope_s_per_car"]
    rng = np.random.default_rng(0)
    row_slopes = [point_estimates(frame.sample(len(frame), replace=True, random_state=rng).reset_index(drop=True))["slope_s_per_car"] for _ in range(300)]
    row_low, row_high = np.percentile(row_slopes, [2.5, 97.5])
    assert (race_high - race_low) > 3 * (row_high - row_low)


def test_bootstrap_is_reproducible_with_a_seed():
    frame = stint_residuals(synthetic_laps(effect_s=1.0, n_races=4))
    assert race_bootstrap(frame, n_boot=50, seed=7) == race_bootstrap(frame, n_boot=50, seed=7)


def test_reweighted_race_sums_match_copying_the_rows():
    frame = stint_residuals(synthetic_laps(effect_s=1.0, n_races=5, race_effect_sd=0.3))
    copied = point_estimates(resample_races(frame, np.random.default_rng(11)))
    totals = race_totals(frame)
    n = len(totals["races"])
    weights = np.bincount(np.random.default_rng(11).choice(n, size=n, replace=True), minlength=n).astype(float)
    reweighted = estimate_from_totals(totals, weights)
    assert np.isclose(copied["slope_s_per_car"], reweighted["slope_s_per_car"])
    assert np.allclose(list(copied["difference_from_zero_s"].values()), list(reweighted["difference_from_zero_s"].values()))


def test_every_exposure_level_is_recovered_when_exposure_rises_with_tyre_age():
    frame = stint_residuals(synthetic_laps(effect_s=1.2, exposure_trend=2.0, seed=4))
    levels = point_estimates(frame)["difference_from_zero_s"]
    for k in (1, 2, 3):
        assert abs(levels[k] - 1.2 * k) < 0.1
    top_mean = frame.loc[frame["candidate_traffic_count"] >= 4, "candidate_traffic_count"].mean()
    assert abs(levels[4] - 1.2 * top_mean) < 0.15


def test_joint_fit_keeps_the_real_count_and_gives_an_unrelated_count_nothing():
    frame = stint_residuals(synthetic_laps(effect_s=1.0, race_effect_sd=0.1, seed=5))
    fit = joint_fit(frame, ["candidate_traffic_count", "unrelated_count"], n_boot=200)
    assert abs(fit["coefficients_s"]["candidate_traffic_count"] - 1.0) < 0.05
    low, high = fit["intervals_s"]["unrelated_count"]
    assert low < 0 < high
