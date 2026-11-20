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
    assert episodes.iloc[0]["duration_s"] == pytest.approx(103.0)   # first to last caution crossing (E-023)


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


# E-023: cautions priced by time, and a caution rate drawn per race. All synthetic.

TIMED = replace(PARAMS, caution_progress={"SF": 0.5, "FCY": 0.4})
CAUTIONS_ONLY = Randomness(caution_rate_per_green_s={"SF": 1 / 5400, "FCY": 1 / 7200},
                           caution_durations_s={"SF": np.array([600.0, 1500.0]), "FCY": np.array([300.0, 450.0])})


def test_time_to_cover_slows_only_the_part_of_a_lap_inside_a_caution():
    from endurance_strategy.simulator.engine import time_to_cover
    progress = {"SF": 0.5, "FCY": 0.25}
    assert time_to_cover(100.0, 0.0, [], progress) == pytest.approx(100.0)
    assert time_to_cover(100.0, 0.0, [(0.0, 1000.0, "SF")], progress) == pytest.approx(200.0)       # wholly inside
    assert time_to_cover(100.0, 0.0, [(50.0, 1000.0, "SF")], progress) == pytest.approx(50.0 + 100.0)  # starts green
    assert time_to_cover(100.0, 0.0, [(-50.0, 40.0, "FCY")], progress) == pytest.approx(40.0 + 90.0)   # ends mid-lap
    assert time_to_cover(100.0, 0.0, [(10.0, 20.0, "SF"), (30.0, 40.0, "FCY")], progress) == pytest.approx(100.0 + 5.0 + 7.5)
    assert time_to_cover(100.0, 500.0, [(0.0, 400.0, "SF")], progress) == pytest.approx(100.0)        # already over


def test_full_speed_under_cautions_means_exactly_zero_caution_loss():
    free = replace(TIMED, caution_progress={"SF": 1.0, "FCY": 1.0})
    for seed in range(10):
        result = simulate(free, STRATEGY, CAUTIONS_ONLY, seed=seed)
        assert result.cautions and (result.records["caution_s"].abs() < 1e-9).all()   # zero up to float rounding


@pytest.mark.parametrize("randomness", [None, CAUTIONS_ONLY])
def test_time_priced_simulator_keeps_the_state_invariants(randomness):
    for seed in range(5):
        records = simulate(TIMED, STRATEGY, randomness, seed=seed).records
        assert (records["race_time_s"].diff().dropna() > 0).all()
        assert (records["caution_s"] >= -1e-9).all()
        assert (records.loc[records["flag"].ne("GF"), "incident_s"] == 0).all()
        if randomness is None:
            assert (records["caution_s"].abs() < 1e-9).all()


def test_caution_time_is_charged_by_time_not_by_laps():
    """Two races whose only difference is where one 10-minute safety car falls relative to the laps lose the
    same time, up to the last lap's partial cover, which per-lap pricing can't do."""
    from endurance_strategy.simulator.engine import RaceDraws
    import endurance_strategy.simulator.engine as engine
    flat = replace(TIMED, traffic_on=False, warm_up_s=0.0, pit_loss_s={False: 0.0, True: 0.0})
    one_stint = Strategy(stint_laps=(400,), drivers=("A",))
    lost = []
    for start in (1000.0, 1037.0, 1071.0):
        original = engine.draw_race
        engine.draw_race = lambda *a, s=start: replace(RaceDraws.none(), cautions=[(s, s + 600.0, "SF")])
        try:
            records = simulate(flat, one_stint, CAUTIONS_ONLY, seed=1, check=False).records
        finally:
            engine.draw_race = original
        lost.append(records["caution_s"].sum())
    assert lost == pytest.approx([300.0] * 3)   # 600 s at half speed covers 300 s of green running


def test_a_gamma_rate_per_race_spreads_counts_without_moving_their_mean():
    from endurance_strategy.simulator.engine import draw_cautions
    short = Randomness(caution_rate_per_green_s={"SF": 6 / (6 * 3600)}, caution_durations_s={"SF": np.array([1.0])})
    spread = replace(short, caution_rate_shape={"SF": 1.0})
    constant = [len(draw_cautions(short, 6 * 3600.0, np.random.default_rng(i))) for i in range(3000)]
    varied = [len(draw_cautions(spread, 6 * 3600.0, np.random.default_rng(i))) for i in range(3000)]
    assert np.mean(constant) == pytest.approx(6.0, rel=0.05) and np.var(constant) == pytest.approx(6.0, rel=0.15)
    assert np.mean(varied) == pytest.approx(6.0, rel=0.07)
    assert np.var(varied) == pytest.approx(6.0 + 36.0, rel=0.2)          # mu + mu^2 / k with k = 1
    assert np.mean(np.array(varied) == 0) > 0.05                          # some races have none


def test_the_spread_fit_recovers_a_known_spread_and_keeps_the_mean_count():
    """Synthetic recovery on many races with realistic episode lengths, which use up green time. A gamma
    multiplier alone would lower the mean count; the joint fit must keep it at the observed one."""
    from endurance_strategy.simulator.calibrate import _simulated_counts, rate_spread
    rates, durations = {"SF": 1.0, "FCY": 0.5}, {"SF": [900.0, 1500.0], "FCY": [300.0]}
    hours = np.resize([6.0, 6.0, 8.0, 10.0], 800)
    rng = np.random.default_rng(11)
    grid = np.round(np.arange(0.0, 2.01, 0.25), 2)
    for truth in (0.0, 1.0):
        counts = _simulated_counts("SF", truth, rates, durations, hours, rng)
        per_race = pd.DataFrame({"hours": hours, "SF": counts, "FCY": 0})
        fit = rate_spread(per_race, rates, durations, grid=grid, races_per_point=2000, checks=3, seed=3)["SF"]
        assert fit["inverse_shape"] == pytest.approx(truth, abs=0.25)
        again = _simulated_counts("SF", fit["inverse_shape"], dict(rates, SF=fit["rate_per_green_hour"]), durations, hours, rng)
        assert again.mean() == pytest.approx(counts.mean(), rel=0.06)


def test_a_spread_beyond_the_generator_is_flagged_not_hidden():
    from endurance_strategy.simulator.calibrate import rate_spread
    hours = np.full(14, 6.0)
    per_race = pd.DataFrame({"hours": hours, "SF": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 30, 30], "FCY": 0})
    fit = rate_spread(per_race, {"SF": 1.0, "FCY": 0.0}, {"SF": [1200.0], "FCY": [300.0]},
                      grid=np.array([0.0, 0.5, 1.0]), races_per_point=600, checks=2, seed=1)["SF"]
    assert fit["out_of_reach"]


def _timed_race(progress: float, episodes, cars: int = 30, lap_s: float = 100.0, hours: float = 2.0,
                restart_s: float = 0.0) -> pd.DataFrame:
    """A field of cars at a steady 100 s lap, spread round the track, running at `progress` of green speed inside
    one safety-car episode. A full field matters: with a few cars, the gaps between caution crossings exceed a
    green lap and the reconstructed episode splits."""
    from endurance_strategy.simulator.engine import flag_at, time_to_cover
    rows = []
    for car in range(cars):
        t, lap = car * 3.3, 0
        while t < hours * 3600:
            took = time_to_cover(lap_s, t, episodes, {"SF": progress, "FCY": progress})
            if flag_at(t, episodes) == "GF" and any(t - lap_s < e[1] <= t for e in episodes):
                took += restart_s   # the field restarting, on the lap after an episode
            t, lap = t + took, lap + 1
            rows.append({"event_key": "2024_X", "NUMBER": str(car), "CLASS": "HYPERCAR", "LAP_NUMBER": lap, "ELAPSED_S": t,
                         "LAP_TIME_S": took, "FLAG_AT_FL": flag_at(t, episodes), "is_pit_lap": False,
                         "is_usable_for_pace_model": abs(took - lap_s) < 1e-9})
    return pd.DataFrame(rows)


def test_caution_share_fitted_from_crossings_then_applied_replays_the_field_exactly():
    """Fit then use, as the real run does: a field running at a known share in several episodes, the share
    fitted from rebuilt episodes, then every car's race rebuilt lap by lap with that share and those episodes."""
    from endurance_strategy.simulator.calibrate import caution_progress
    from endurance_strategy.simulator.engine import time_to_cover
    for truth in (0.35, 0.6):
        episodes_true = [(1500.0, 2400.0, "SF"), (3100.0, 3400.0, "SF"), (4300.0, 5600.0, "SF")]
        laps = _timed_race(truth, episodes_true, hours=2.5, lap_s=130.0)
        rebuilt = caution_episodes(laps)
        fit = caution_progress(laps, rebuilt)["HYPERCAR"]["SF"]
        assert len(rebuilt) == 3 and fit["car_episodes"] >= 80
        windows = [(r.start_s, r.start_s + r.duration_s, r.kind) for r in rebuilt.itertuples()]
        errors = []
        for _, car in laps.groupby("NUMBER"):
            t = float(car["ELAPSED_S"].iloc[0])
            for _ in car["LAP_NUMBER"].iloc[1:]:
                t += time_to_cover(130.0, t, windows, {"SF": fit["progress"]})
            errors.append((t - car["ELAPSED_S"].iloc[-1]) / car["ELAPSED_S"].iloc[-1])
        assert abs(np.median(errors)) < 0.001   # under 0.1% of race time, against a 0.5% gate


def test_a_restart_cost_is_fitted_and_charged_per_episode_so_many_short_cautions_are_not_too_fast():
    """The review's case: the same caution time in one long or six short safety cars, with 6 s lost on each
    car's restart lap. Without a restart cost, the six-episode race replays about 45 s too fast."""
    from endurance_strategy.simulator.calibrate import caution_progress
    from endurance_strategy.simulator.engine import time_to_cover
    races = {"2024_A": [(1500.0, 5100.0, "SF")],
             "2024_B": [(1000.0 + i * 1500.0, 1600.0 + i * 1500.0, "SF") for i in range(6)]}
    laps = pd.concat([_timed_race(0.5, eps, hours=3.0, restart_s=6.0).assign(event_key=e) for e, eps in races.items()])
    rebuilt = caution_episodes(laps)
    fit = caution_progress(laps, rebuilt)["HYPERCAR"]
    assert fit["restart"]["extra_s"] == pytest.approx(6.0, abs=0.5)
    for event, group in laps.groupby("event_key"):
        windows = [(r.start_s, r.start_s + r.duration_s, r.kind) for r in rebuilt[rebuilt["event_key"] == event].itertuples()]
        errors = []
        for _, car in group.groupby("NUMBER"):
            t = float(car["ELAPSED_S"].iloc[0])
            for _ in car["LAP_NUMBER"].iloc[1:]:
                took = time_to_cover(100.0, t, windows, {"SF": fit["SF"]["progress"]})
                if not any(s <= t < e for s, e, _ in windows) and any(t - 100.0 < e <= t for _, e, _ in windows):
                    took += fit["restart"]["extra_s"]
                t += took
            errors.append(t - car["ELAPSED_S"].iloc[-1])
        assert abs(np.median(errors)) < 10.0, event   # seconds over 3 hours


def test_a_car_that_pits_in_a_caution_is_left_out_of_its_progress():
    from endurance_strategy.simulator.calibrate import caution_progress
    laps = _timed_race(0.5, [(2000.0, 3500.0, "SF")])
    laps.loc[(laps["NUMBER"] == "0") & laps["ELAPSED_S"].between(2500, 2700), "is_pit_lap"] = True
    assert caution_progress(laps, caution_episodes(laps))["HYPERCAR"]["SF"]["car_episodes"] == 29


def test_a_missing_caution_share_is_an_error_not_a_free_caution():
    from endurance_strategy.simulator.calibrate import car_params
    calibration = {"circuits": [{"circuit": "X", "CLASS": "HYPERCAR", "hours": 6, "clean_median_s": 100.0, "max_stint_laps": 40,
                                 "traffic_rate": 1.0}],
                   "pit_loss_median_s": {"HYPERCAR": {"False": 70.0, "True": 85.0}}, "caution_lap_ratio": {"HYPERCAR": {"SF": 1.5, "FCY": 1.5}},
                   "caution_progress": {"HYPERCAR": {"SF": {"progress": 0.5}, "FCY": {"progress": None}}}}
    with pytest.raises(ValueError):
        car_params(calibration, "X", "HYPERCAR")
    calibration["caution_progress"]["HYPERCAR"]["FCY"]["progress"] = 1.2
    with pytest.raises(ValueError):
        car_params(calibration, "X", "HYPERCAR")


def test_replay_on_the_clock_of_a_simulated_car_has_zero_error():
    from endurance_strategy.simulator.replay import replay_car
    from endurance_strategy.simulator import calibrate as cal
    params = replace(TIMED, circuit="IMOLA", traffic_s_per_car=cal.TRAFFIC_S_PER_CAR["HYPERCAR"])
    strategy = Strategy(stint_laps=(30, 30, 30, 30, 30, 30, 60), drivers=("A", "A", "B", "B", "C", "C", "C"))
    for seed in range(4):
        result = simulate(params, strategy, CAUTIONS_ONLY, seed=seed, check=False)
        records = result.records
        assert result.cautions
        laps = pd.DataFrame({"event_key": "2024_IMOLA", "NUMBER": "7", "CLASS": "HYPERCAR", "LAP_NUMBER": records["lap"],
                             "LAP_TIME_S": records["lap_time_s"], "FLAG_AT_FL": records["flag"], "stint_lap": records["stint_lap"],
                             "is_out_lap": records["out_lap"], "DRIVER_NUMBER": records["driver"], "ELAPSED_S": records["race_time_s"],
                             "is_usable_for_pace_model": ~records["out_lap"] & ~records["in_lap"] & records["stint_lap"].ge(3)
                             & records["caution_s"].abs().lt(1e-9)})
        calibration = {"circuits": [{"circuit": "IMOLA", "CLASS": "HYPERCAR", "hours": 6, "clean_median_s": 0.0, "max_stint_laps": 40,
                                     "traffic_rate": params.traffic_rate}],
                       "pit_loss_median_s": {"HYPERCAR": {"False": 70.0, "True": 85.0}},
                       "pit_loss_samples_s": {"HYPERCAR": {"False": [70.0], "True": [85.0]}},
                       "caution_lap_ratio": {"HYPERCAR": params.caution_lap_ratio},
                       "caution_progress": {"HYPERCAR": {k: {"progress": v} for k, v in params.caution_progress.items()}},
                       "caution": {"episodes_by_race": {"2024_IMOLA": [list(e) for e in result.cautions]}}}
        old = cal.WARM_UP_S["HYPERCAR"]
        cal.WARM_UP_S["HYPERCAR"] = params.warm_up_s
        try:
            predicted = replay_car(laps, calibration, "M3")
        finally:
            cal.WARM_UP_S["HYPERCAR"] = old
        assert predicted == pytest.approx(float(records["race_time_s"].iloc[-1]), abs=1e-6)
