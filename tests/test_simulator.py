"""Invariant and unit tests for the Layer 4 simulator. Every input here is synthetic."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from endurance_strategy.simulator.calibrate import calibrate, caution_episodes
from endurance_strategy.simulator.compare import paired_summary, run_strategies
from endurance_strategy.simulator.engine import CarParams, InfeasibleStrategy, Randomness, Strategy, simulate
from endurance_strategy.simulator.feasibility import check_strategy, even_strategy

PARAMS = CarParams(circuit="SYNTH", car_class="HYPERCAR", duration_s=6 * 3600.0, base_pace_s=100.0, max_stint_laps=40,
                   pit_loss_s={False: 70.0, True: 85.0}, warm_up_s=0.3, traffic_rate=1.5, traffic_s_per_car=0.35,
                   caution_lap_ratio={"SF": 1.4, "FCY": 1.6})
STRATEGY = even_strategy(PARAMS, 6, ("A", "B", "C"))
NOISE = Randomness(lap_residuals_s=np.array([-0.5, 0.0, 0.5]), pit_loss_samples_s={False: np.array([60.0, 70.0, 80.0]), True: np.array([80.0, 90.0])},
                   caution_rate_per_green_s={"SF": 1 / 7200, "FCY": 1 / 7200}, caution_durations_s={"SF": np.array([600.0, 900.0]), "FCY": np.array([300.0])})
HEAVY_FCY = Randomness(caution_rate_per_green_s={"FCY": 1 / 3000}, caution_durations_s={"FCY": np.array([1200.0])})


def test_deterministic_runs_are_identical_and_seeded_runs_reproduce():
    a, b = simulate(PARAMS, STRATEGY), simulate(PARAMS, STRATEGY)
    assert a.records.equals(b.records)
    c, d = simulate(PARAMS, STRATEGY, NOISE, seed=7), simulate(PARAMS, STRATEGY, NOISE, seed=7)
    assert c.records.equals(d.records)
    assert not simulate(PARAMS, STRATEGY, NOISE, seed=8).records["lap_time_s"].equals(c.records["lap_time_s"])


@pytest.mark.parametrize("randomness", [None, NOISE])
def test_state_invariants_hold_on_every_lap(randomness):
    for seed in range(5):
        records = simulate(PARAMS, STRATEGY, randomness, seed=seed).records
        assert (records["race_time_s"].diff().dropna() > 0).all()                      # race time never decreases
        assert (records["lap"].diff().dropna() == 1).all()                              # one lap at a time
        resets = records["stint_lap"].diff().dropna() < 0
        assert (records["out_lap"].iloc[1:][resets.to_numpy()]).all()                  # stint age falls only after a stop
        assert (records.loc[records["out_lap"], "stint_lap"] == 1).all()
        assert not (records["in_lap"] & records["entry_flag"].eq("FCY")).any()         # no stop while the pits are closed


def test_race_ends_at_the_first_crossing_after_time():
    result = simulate(PARAMS, STRATEGY)
    assert result.finish_time_s >= PARAMS.duration_s
    assert result.finish_time_s - result.records["lap_time_s"].iloc[-1] < PARAMS.duration_s


def test_traffic_off_means_exactly_zero_traffic_loss():
    on, off = simulate(PARAMS, STRATEGY), simulate(replace(PARAMS, traffic_on=False), STRATEGY)
    assert (off.records["traffic_s"] == 0.0).all()
    assert (on.records["traffic_s"] > 0).any()


def test_with_no_pit_loss_and_no_age_effects_stops_change_nothing():
    flat = replace(PARAMS, pit_loss_s={False: 0.0, True: 0.0}, warm_up_s=0.0, age_slope_s=0.0, traffic_on=False)
    few, many = even_strategy(flat, 5, ("A",)), even_strategy(flat, 9, ("A",))
    assert simulate(flat, few).time_at_lap(200) == pytest.approx(simulate(flat, many).time_at_lap(200))


def test_with_no_pit_loss_pitting_helps_only_through_the_age_effect():
    worn = replace(PARAMS, pit_loss_s={False: 0.0, True: 0.0}, warm_up_s=0.0, age_slope_s=0.05, traffic_on=False)
    few, many = even_strategy(worn, 5, ("A",)), even_strategy(worn, 9, ("A",))
    assert simulate(worn, many).time_at_lap(200) < simulate(worn, few).time_at_lap(200)


def test_infeasible_strategies_never_run():
    too_long = Strategy(stint_laps=(60, 60, 100), drivers=("A", "B", "C"))
    assert not check_strategy(PARAMS, too_long).ok
    with pytest.raises(InfeasibleStrategy):
        simulate(PARAMS, too_long)
    with pytest.raises(InfeasibleStrategy):
        simulate(PARAMS, Strategy(stint_laps=(30, 30), drivers=("A",)))


def test_gt3_minimum_driving_time_is_checked_with_categories():
    gt3 = replace(PARAMS, car_class="LMGT3")
    one_short_stint_for_bronze = Strategy(stint_laps=(10, 35, 35, 35, 35, 35, 35), drivers=("B1", "P", "S", "P", "S", "P", "S"))
    result = check_strategy(gt3, one_short_stint_for_bronze, {"B1": "Bronze", "S": "Silver", "P": "Platinum"})
    assert any(v.startswith("R2: B1") for v in result.violations)


def test_no_green_stint_exceeds_the_energy_limit_and_long_finals_force_a_stop():
    result = simulate(PARAMS, even_strategy(PARAMS, 6, ("A",)))
    assert result.records.groupby("stint")["stint_lap"].max().max() <= PARAMS.max_stint_laps
    long_final = Strategy(stint_laps=(20, 20, 20, 20, 20, 20, 20), drivers=("A",) * 7)  # leaves about 90 laps to the flag
    forced = simulate(PARAMS, long_final, check=False)
    assert forced.extra_stops > 0
    assert forced.records.groupby("stint")["stint_lap"].max().max() <= PARAMS.max_stint_laps


def test_driver_change_uses_its_own_pit_loss_and_caution_laps_carry_no_green_parts():
    records = simulate(PARAMS, Strategy(stint_laps=(30, 30, 30, 30, 30, 30, 60), drivers=("A", "A", "B", "B", "C", "C", "C"))).records
    out_laps = records[records["out_lap"]]
    assert sorted(out_laps["pit_s"].unique()) == [70.0, 85.0]
    caution = simulate(PARAMS, STRATEGY, NOISE, seed=3).records
    under = caution[caution["flag"].isin(["SF", "FCY"])]
    assert len(under) and (under[["age_s", "traffic_s", "noise_s", "warm_up_s"]] == 0).all().all()


def test_full_course_yellow_defers_a_planned_stop():
    always_fcy = Randomness(caution_rate_per_green_s={"FCY": 1.0}, caution_durations_s={"FCY": np.array([2000.0])})
    result = simulate(PARAMS, STRATEGY, always_fcy, seed=1)
    assert result.deferred_laps > 0


def test_strategies_share_the_same_simulated_races():
    runs = run_strategies(PARAMS, {"six": STRATEGY, "seven": even_strategy(PARAMS, 7, ("A", "B", "C"))}, NOISE, range(5))
    cautions = runs.pivot(index="seed", columns="strategy", values="cautions")
    assert (cautions["six"] == cautions["seven"]).all()
    summary = paired_summary(runs, "six", 150)
    assert summary["six"]["difference_vs_baseline_s"]["mean"] == 0.0
    assert summary["seven"]["seeds"] == 5


def test_caution_episodes_from_line_crossings():
    rows = []
    for car in range(4):
        for lap, flag in enumerate(["GF", "SF", "SF", "GF", "FCY", "GF"], start=1):
            rows.append({"event_key": "2024_X", "NUMBER": str(car), "ELAPSED_S": lap * 100.0 + car, "LAP_TIME_S": 100.0, "FLAG_AT_FL": flag})
    episodes = caution_episodes(pd.DataFrame(rows))
    assert list(episodes["kind"]) == ["SF", "FCY"]
    assert episodes.iloc[0]["duration_s"] == pytest.approx(103.0 + 100.0)


def test_calibration_refuses_the_sealed_season():
    with pytest.raises(ValueError):
        calibrate(pd.DataFrame({"event_key": ["2026_IMOLA"]}))


def test_calibration_replay_and_simulation_run_end_to_end_on_synthetic_races():
    from test_layer3_runner import synthetic_laps
    from endurance_strategy.simulator.calibrate import car_params, randomness
    from endurance_strategy.simulator.replay import replay, summarise
    rng = np.random.default_rng(3)
    laps = pd.concat([synthetic_laps(e, rng) for e in ("2024_IMOLA", "2025_IMOLA", "2024_LOSAIL")], ignore_index=True)
    for column in ("is_caution_lap", "is_wet", "is_field_slow"):
        laps[column] = False
    laps["DRIVER_NUMBER"] = (laps["stint_number"] // 2 % 2).astype(str)  # a driver change at every second stop
    calibration = calibrate(laps)
    params = car_params(calibration, "IMOLA", "HYPERCAR")
    assert params.max_stint_laps == 16 and params.base_pace_s > 90
    result = simulate(params, even_strategy(params, 25, ("A", "B")), randomness(calibration, "HYPERCAR"), seed=1)
    assert result.laps > 50
    summary = summarise(replay(laps, calibration))
    assert summary["M0"]["cars"] > 0


def test_no_stop_is_ever_made_into_closed_pits_and_green_laps_respect_the_energy_limit():
    plan = Strategy(stint_laps=(40,) * 6, drivers=("A",) * 6)
    for seed in range(60):
        records = simulate(PARAMS, plan, HEAVY_FCY, seed=seed, check=False).records
        assert not (records["in_lap"] & records["entry_flag"].eq("FCY")).any()
        over = records["green_laps_in_stint"] > PARAMS.max_stint_laps
        assert over.sum() <= 1 and records.loc[over, "in_lap"].all()   # one green lap over, only right after a deferred stop


def test_zero_pit_loss_stays_zero_with_spread_and_noise_lines_up_lap_by_lap():
    flat = replace(PARAMS, pit_loss_s={False: 0.0, True: 0.0}, warm_up_s=0.0, traffic_on=False)
    few, many = even_strategy(flat, 5, ("A",)), even_strategy(flat, 9, ("A",))
    for seed in range(10):
        a, b = simulate(flat, few, NOISE, seed=seed), simulate(flat, many, NOISE, seed=seed)
        assert (a.records["pit_s"] == 0).all()
        assert a.time_at_lap(150) == pytest.approx(b.time_at_lap(150))


def test_slope_uncertainty_is_drawn_once_per_race_around_its_mean():
    draws = [simulate(PARAMS, STRATEGY, Randomness(age_slope_draw=(0.016, 0.009)), seed=s).age_slope_s for s in range(400)]
    assert np.mean(draws) == pytest.approx(0.016, abs=0.002)
    assert 0.007 < np.std(draws) < 0.011


def test_caution_generator_matches_its_rate_per_green_hour():
    from endurance_strategy.simulator.engine import draw_cautions
    randomness = Randomness(caution_rate_per_green_s={"SF": 2 / 3600}, caution_durations_s={"SF": np.array([600.0, 900.0])})
    rng = np.random.default_rng(0)
    rates = []
    for _ in range(2000):
        episodes = draw_cautions(randomness, 6 * 3600.0, rng)
        green = 6 * 3600.0 - sum(min(end, 6 * 3600.0) - start for start, end, _ in episodes)
        rates.append(len(episodes) / (green / 3600))
    assert np.mean(rates) == pytest.approx(2.0, rel=0.08)


def test_age_effect_is_not_extrapolated_past_the_support_limit():
    worn = replace(PARAMS, age_slope_s=0.05, age_limit_laps=20)
    records = simulate(worn, Strategy(stint_laps=(39,) * 6, drivers=("A",) * 6), check=False).records
    assert records["age_s"].max() == pytest.approx(0.05 * 17)


def test_replay_of_a_simulated_car_has_zero_error_so_replay_and_simulator_share_one_lap_model():
    from endurance_strategy.simulator.replay import replay_car
    params = replace(PARAMS, circuit="IMOLA")
    strategy = Strategy(stint_laps=(30, 30, 30, 30, 30, 30, 60), drivers=("A", "A", "B", "B", "C", "C", "C"))
    records = simulate(params, strategy).records
    laps = pd.DataFrame({"event_key": "2024_IMOLA", "NUMBER": "7", "CLASS": "HYPERCAR", "LAP_NUMBER": records["lap"],
                         "LAP_TIME_S": records["lap_time_s"], "FLAG_AT_FL": records["flag"], "stint_lap": records["stint_lap"],
                         "is_out_lap": records["out_lap"], "DRIVER_NUMBER": records["driver"], "ELAPSED_S": records["race_time_s"],
                         "is_usable_for_pace_model": ~records["out_lap"] & ~records["in_lap"] & records["stint_lap"].ge(3)})
    calibration = {"circuits": [{"circuit": "IMOLA", "CLASS": "HYPERCAR", "hours": 6, "clean_median_s": 0.0, "max_stint_laps": 40,
                                 "traffic_rate": params.traffic_rate}],
                   "pit_loss_median_s": {"HYPERCAR": {"False": 70.0, "True": 85.0}},
                   "pit_loss_samples_s": {"HYPERCAR": {"False": [70.0], "True": [85.0]}},
                   "caution_lap_ratio": {"HYPERCAR": params.caution_lap_ratio}}
    from endurance_strategy.simulator import calibrate as cal
    old = cal.WARM_UP_S["HYPERCAR"]
    cal.WARM_UP_S["HYPERCAR"] = params.warm_up_s
    try:
        predicted = replay_car(laps, calibration, "M3")
    finally:
        cal.WARM_UP_S["HYPERCAR"] = old
    assert predicted == pytest.approx(float(records["race_time_s"].iloc[-1]), abs=1e-6)
