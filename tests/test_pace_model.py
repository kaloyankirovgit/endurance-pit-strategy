"""Tests of the Layer 3 estimators on synthetic data. Every frame here is synthetic, generated in the test."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from endurance_strategy.models.pace import (
    SealedDataError,
    age_effect,
    car_bootstrap_median,
    decision_ladder,
    analysis_laps,
    clean_practice_mask,
    fit_age_models,
    holdout_stint_errors,
    is_unstable,
    load_open_seasons,
    mean_with_t_interval,
    pace_comparisons,
    pace_predictions,
    paired_comparison,
    pit_coverage,
    pit_events,
    pit_holdout,
    practice_pace,
    prediction_interval,
    race_coefficients,
    require_open,
    routine_stop_events,
    slope_coverage,
    slope_summary,
    support_limit,
    with_age_terms,
)


def make_stints(slope_by_race: dict[str, float], stints: int = 20, laps: int = 20, noise: float = 0.0, seed: int = 1,
                curve: float = 0.0, car_class: str = "HYPERCAR") -> pd.DataFrame:
    """Synthetic stints: each has its own level, one shared slope per race, ages 2 to laps + 1."""
    rng = np.random.default_rng(seed)
    rows = []
    for event, slope in slope_by_race.items():
        for stint in range(1, stints + 1):
            level = 100 + rng.normal(0, 2)
            age = np.arange(2, laps + 2, dtype=float)
            rows.append(pd.DataFrame({
                "event_key": event, "NUMBER": str(stint), "CLASS": car_class, "stint_number": 1,
                "stint_lap": age.astype(int), "LAP_NUMBER": age.astype(int),
                "LAP_TIME_S": level + slope * age + curve * age ** 2 + rng.normal(0, noise, len(age)) if noise else level + slope * age + curve * age ** 2,
            }))
    return pd.concat(rows, ignore_index=True)


def test_seal_refuses_2026_unless_opened():
    with pytest.raises(SealedDataError):
        require_open(["2026_IMOLA"])
    require_open(["2026_IMOLA"], open_sealed=True)
    require_open(["2024_IMOLA", "2025_LOSAIL"])


def test_loader_refuses_the_sealed_season(tmp_path):
    with pytest.raises(SealedDataError):
        load_open_seasons(tmp_path / "unused.parquet", seasons=("2025", "2026"))


def test_loader_drops_sealed_rows(tmp_path):
    frame = pd.DataFrame({"event_key": ["2024_IMOLA", "2026_IMOLA"], "x": [1, 2]})
    path = tmp_path / "laps.parquet"
    frame.to_parquet(path, index=False)
    assert load_open_seasons(path)["event_key"].tolist() == ["2024_IMOLA"]


def test_within_stint_fit_recovers_the_slope_despite_different_stint_levels():
    frame = with_age_terms(make_stints({"2024_A": 0.05}))
    assert race_coefficients(frame, ["age"])["age"].iloc[0] == pytest.approx(0.05, abs=1e-9)


def test_race_slopes_are_equally_weighted_not_lap_weighted():
    long_race = make_stints({"2024_A": 0.10}, stints=40)
    short_race = make_stints({"2024_B": 0.00}, stints=5)
    frame = pd.concat([long_race, short_race], ignore_index=True)
    coefficients = race_coefficients(with_age_terms(frame), ["age"])
    assert coefficients["age"].mean() == pytest.approx(0.05, abs=1e-9)  # Lap weighting would give about 0.089.


def test_support_limit_stops_at_the_first_unsupported_age():
    frame = make_stints({f"2024_{i}": 0.0 for i in range(5)}, stints=8, laps=10)
    rare = frame[frame["stint_lap"] <= 8]  # Ages over 8 vanish.
    limits = support_limit(rare, min_stints=30, min_races=4)
    assert limits["HYPERCAR"] == 8
    assert support_limit(rare, min_stints=30, min_races=6)["HYPERCAR"] == 0


def test_support_starts_at_the_first_fitted_age():
    frame = make_stints({f"2024_{i}": 0.0 for i in range(5)}, stints=8, laps=10)
    assert support_limit(frame[frame["stint_lap"] >= 4], min_stints=30, min_races=4)["HYPERCAR"] == 0
    assert support_limit(frame[frame["stint_lap"] >= 3], min_stints=30, min_races=4)["HYPERCAR"] == 11


def test_warm_up_lap_stays_out_of_the_straight_line_but_in_the_baseline():
    frame = make_stints({f"2024_{i}": 0.04 for i in range(3)}, stints=21)
    frame["LAP_TIME_S"] -= frame.groupby(["event_key", "NUMBER"])["LAP_TIME_S"].transform("min") - 100.0
    frame.loc[frame["stint_lap"] == 2, "LAP_TIME_S"] += 0.8
    models = _models(frame, 21)["HYPERCAR"]
    assert models["L"] == pytest.approx(0.04, abs=1e-9)
    assert models["B"][2] == pytest.approx(0.8 - 0.04 * 3, abs=0.05)  # Warm-up measured against the median of ages 3 to 7.


def _models(frame: pd.DataFrame, limit: int) -> dict:
    other = frame.assign(CLASS="LMGT3")
    return fit_age_models(pd.concat([frame, other], ignore_index=True), {"HYPERCAR": limit, "LMGT3": limit})


def test_fit_models_recover_slope_and_curve():
    frame = make_stints({f"2024_{i}": 0.04 for i in range(3)}, curve=0.002)
    models = _models(frame, 21)["HYPERCAR"]
    assert models["Q"][0] == pytest.approx(0.04, abs=1e-9)
    assert models["Q"][1] == pytest.approx(0.002, abs=1e-9)


def test_median_baseline_recovers_a_known_rise_across_ages():
    frame = make_stints({f"2024_{i}": 0.1 for i in range(3)}, stints=21)
    frame["LAP_TIME_S"] -= frame.groupby(["event_key", "NUMBER"])["LAP_TIME_S"].transform("min") - 100.0  # Same level per stint.
    profile = _models(frame, 21)["HYPERCAR"]["B"]
    assert profile[12] - profile[2] == pytest.approx(1.0, abs=1e-9)


def test_baseline_held_flat_past_its_last_supported_age():
    model = {"B": {2: 0.0, 3: 0.5}}
    assert age_effect("B", model, np.array([10.0]), "ANY")[0] == 0.5


def test_holdout_anchor_makes_the_true_model_perfect_and_flat_wrong():
    fit = make_stints({"2024_X": 0.1}, stints=10)
    models = _models(fit, 21)
    check = make_stints({"2025_X": 0.1}, stints=6, seed=2)
    errors = holdout_stint_errors(check.assign(CLASS="HYPERCAR"), models)
    by_model = errors.set_index("model")["mae_s"]
    assert by_model["L"] == pytest.approx(0.0, abs=1e-9)
    assert by_model["C"] == pytest.approx(0.0, abs=1e-9)
    assert by_model["F"] > 0.5


def test_holdout_uses_only_earlier_laps_of_the_stint():
    fit = make_stints({"2024_X": 0.1}, stints=10)
    models = _models(fit, 21)
    check = make_stints({"2025_X": 0.1}, stints=4, seed=2)
    baseline = holdout_stint_errors(check, models)
    changed = check.copy()
    changed.loc[changed["stint_lap"] >= 20, "LAP_TIME_S"] += 50
    errors_a = baseline.set_index("model")["mae_s"]
    errors_b = holdout_stint_errors(changed, models).set_index("model")["mae_s"]
    assert errors_b["L"] > errors_a["L"]  # The change is scored as error, so it did not feed the anchor.
    early_change = check.copy()
    early_change.loc[early_change["stint_lap"].between(3, 7), "LAP_TIME_S"] += 50
    assert holdout_stint_errors(early_change, models).set_index("model")["mae_s"]["L"] > 40


def test_holdout_anchor_ignores_a_slow_warm_up_lap():
    fit = make_stints({"2024_X": 0.1}, stints=10)
    models = _models(fit, 21)
    check = make_stints({"2025_X": 0.1}, stints=4, seed=2)
    check.loc[check["stint_lap"] == 2, "LAP_TIME_S"] += 5.0
    assert holdout_stint_errors(check, models).set_index("model")["mae_s"]["L"] == pytest.approx(0.0, abs=1e-9)


def test_holdout_ignores_ages_past_the_fit_support():
    fit = make_stints({"2024_X": 0.1}, stints=10)
    models = _models(fit, 12)
    check = make_stints({"2025_X": 0.1}, stints=4, seed=2)
    errors = holdout_stint_errors(check, models).set_index("model")
    assert errors.loc["L", "laps"] == 4 * (12 - 7)  # Anchor is ages 3 to 7, then ages 8 to 12.


def test_paired_comparison_declares_a_win_only_when_the_interval_clears_zero():
    simpler = pd.Series([1.0, 1.1, 0.9, 1.0, 1.05, 0.95, 1.0])
    assert paired_comparison(simpler - 0.2, simpler)["replaces_simpler"] is True
    mixed = simpler + np.array([0.1, -0.1, 0.1, -0.1, 0.1, -0.1, 0.0])
    assert paired_comparison(mixed, simpler)["replaces_simpler"] is False


def test_prediction_interval_is_wider_than_the_mean_interval():
    values = [0.01, 0.02, 0.03, 0.05, -0.01, 0.04, 0.02]
    mean_low, mean_high = mean_with_t_interval(values)["t_interval"]
    low, high = prediction_interval(values)
    assert (high - low) > 2 * (mean_high - mean_low)


def test_slope_coverage_counts_races_inside_the_interval():
    fit = np.array([0.0, 0.01, 0.02, -0.01, 0.015, -0.005, 0.005])
    result = slope_coverage(fit, [0.0, 0.01, 99.0])
    assert (result["inside"], result["of"]) == (2, 3)
    assert result["width"] > 0
    assert slope_coverage(fit, [0.0] * 5 + [99.0])["under_coverage"] is False
    assert slope_coverage(fit, [0.0] * 5 + [99.0, 99.0])["under_coverage"] is True


def with_lap_pct(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.assign(lap_pct=100.0 * frame["LAP_TIME_S"] / frame.groupby(["event_key", "CLASS"])["LAP_TIME_S"].transform("median"))


def test_slope_summary_bootstrap_draws_races_and_a_lap_bootstrap_would_be_too_narrow():
    rng = np.random.default_rng(3)
    frame = with_lap_pct(make_stints({f"2024_{i}": float(rng.normal(0.05, 0.03)) for i in range(7)}, stints=12, noise=0.1))
    result = slope_summary(frame, {"HYPERCAR": 21}, classes=("HYPERCAR",), n_boot=2000)["HYPERCAR"]["s_per_lap"]
    low, high = result["bootstrap"]
    rows = with_age_terms(frame[frame["stint_lap"] >= 3])
    lap_draws = []
    for _ in range(150):
        sample = rows.iloc[rng.integers(0, len(rows), len(rows))]
        lap_draws.append(race_coefficients(sample, ["age"])["age"].mean())
    lap_low, lap_high = np.percentile(lap_draws, [2.5, 97.5])
    assert (high - low) > 3 * (lap_high - lap_low)


def test_recovery_and_interval_coverage_on_synthetic_races():
    """E-020's gate: a known mean slope with race-to-race variation is recovered and covered."""
    rng = np.random.default_rng(20261109)
    true_slope, between_races_sd, warm_up = 0.04, 0.02, 0.8
    hits, estimates = 0, []
    for _ in range(500):
        tables = []
        for race in range(7):
            slope = rng.normal(true_slope, between_races_sd)
            for stint in range(6):
                length = 12 + rng.binomial(12, 0.6)  # Stints end at varying ages.
                age = np.arange(2, length + 2)
                times = rng.normal(100, 2) + slope * age + rng.normal(0, 0.4, age.size) + warm_up * (age == 2)
                tables.append(pd.DataFrame({"event_key": f"2024_{race}", "NUMBER": str(stint), "CLASS": "HYPERCAR",
                                            "stint_number": 1, "stint_lap": age, "LAP_TIME_S": times}))
        frame = with_lap_pct(pd.concat(tables, ignore_index=True))
        summary = slope_summary(frame, {"HYPERCAR": 40}, classes=("HYPERCAR",), n_boot=2)["HYPERCAR"]["s_per_lap"]
        low, high = summary["t_interval"]
        hits += low <= true_slope <= high
        estimates.append(summary["mean"])
    assert abs(np.mean(estimates) - true_slope) <= 0.005
    assert 0.92 <= hits / 500 <= 0.98


def _car_laps(event: str = "2024_X", number: str = "7") -> pd.DataFrame:
    """Two stints with a stop between them, reference pace 100 s, one in-lap and one out-lap."""
    laps = pd.DataFrame({"LAP_NUMBER": list(range(1, 15))})
    laps["LAP_TIME_S"] = 100.0
    laps["event_key"], laps["NUMBER"], laps["CLASS"] = event, number, "HYPERCAR"
    laps["is_out_lap"] = laps["LAP_NUMBER"].eq(8)
    laps["is_in_lap"] = laps["LAP_NUMBER"].eq(7)
    laps["stint_number"] = (laps["LAP_NUMBER"] >= 8).astype(int) + 1
    laps["stint_lap"] = laps.groupby("stint_number").cumcount() + 1
    laps["FLAG_AT_FL"] = "GF"
    laps["is_garage_stop"] = False
    laps["is_wet"] = False
    laps["is_field_slow"] = False
    laps["DRIVER_NUMBER"] = (laps["LAP_NUMBER"] >= 8).map({False: "1", True: "2"})
    laps["PIT_TIME_S"] = np.where(laps["is_out_lap"], 50.0, np.nan)
    laps.loc[laps["is_in_lap"], "LAP_TIME_S"] = 112.0
    laps.loc[laps["is_out_lap"], "LAP_TIME_S"] = 148.0
    laps["is_usable_for_pace_model"] = ~(laps["is_in_lap"] | laps["is_out_lap"])
    return laps


def test_pit_loss_recovers_a_known_cost_and_differs_from_pit_time():
    event = pit_events(_car_laps()).iloc[0]
    assert event["status"] == "eligible"
    assert event["pit_loss_s"] == pytest.approx(60.0, abs=0.05)
    assert event["pit_time_s"] == 50.0
    assert bool(event["driver_changed"]) is True


def test_pit_loss_reference_skips_the_warm_up_lap():
    laps = _car_laps()
    laps.loc[laps["LAP_NUMBER"] == 9, "LAP_TIME_S"] = 180.0
    laps.loc[laps["LAP_NUMBER"].between(10, 14), "LAP_TIME_S"] = 100.0
    laps.loc[laps["LAP_NUMBER"].between(2, 6), "LAP_TIME_S"] = 100.0
    laps = laps[laps["LAP_NUMBER"] != 14]  # Leaves four clean laps after warm-up, so lap 9 would alter a count of five.
    assert pit_events(laps).iloc[0]["reference_pace_s"] == pytest.approx(100.0, abs=1e-9)


def test_a_pit_lane_start_is_counted_without_a_loss():
    laps = _car_laps()
    laps.loc[laps["LAP_NUMBER"] == 1, "is_out_lap"] = True
    event = pit_events(laps).iloc[0]
    assert (event["status"], event["driver_changed"]) == ("pit_lane_start", False)
    assert np.isnan(event["pit_loss_s"])


def test_reference_comes_from_analysis_laps_not_every_usable_lap():
    laps = _car_laps()
    for flag in ["is_first_lap", "is_caution_lap", "is_after_caution", "is_missing_data", "is_slow_lap"]:
        laps[flag] = False
    laps["is_pit_lap"] = laps["is_in_lap"] | laps["is_out_lap"]
    assert routine_stop_events(laps).iloc[0]["status"] == "eligible"
    laps.loc[laps["LAP_NUMBER"].between(11, 14), "is_slow_lap"] = True  # Leaves 2 clean laps after the stop: a short stint.
    assert pit_events(laps).iloc[0]["status"] == "eligible"
    assert routine_stop_events(laps).iloc[0]["status"] == "too_few_reference_laps"


def test_an_out_lap_that_is_also_an_in_lap_gets_no_pit_loss():
    laps = _car_laps()
    laps.loc[laps["LAP_NUMBER"] == 8, "is_in_lap"] = True
    assert pit_events(laps).iloc[0]["status"] == "out_in_lap"


def test_pit_loss_reference_uses_both_sides_of_the_stop():
    laps = _car_laps()
    laps.loc[laps["LAP_NUMBER"].between(2, 6), "LAP_TIME_S"] = 98.0
    laps.loc[laps["LAP_NUMBER"].between(9, 14), "LAP_TIME_S"] = 102.0
    event = pit_events(laps).iloc[0]
    assert event["reference_pace_s"] == pytest.approx(100.0, abs=1e-9)  # Median of five at 98 s and five at 102 s.


@pytest.mark.parametrize("change, status", [
    ("caution", "caution"),
    ("garage", "garage"),
    ("wet", "wet_or_field_slow"),
    ("field_slow", "wet_or_field_slow"),
    ("few_reference", "too_few_reference_laps"),
    ("few_before", "too_few_reference_laps"),
    ("missing_time", "missing_time"),
    ("gap_in_laps", "not_consecutive"),
])
def test_stops_without_a_pit_loss_say_why(change, status):
    laps = _car_laps()
    if change == "caution":
        laps.loc[laps["is_out_lap"], "FLAG_AT_FL"] = "FCY"
    elif change == "garage":
        laps.loc[laps["is_out_lap"], "is_garage_stop"] = True
    elif change == "wet":
        laps.loc[laps["is_in_lap"], "is_wet"] = True
    elif change == "field_slow":
        laps.loc[laps["is_out_lap"], "is_field_slow"] = True
    elif change == "few_reference":
        laps.loc[laps["LAP_NUMBER"].between(10, 14), "is_usable_for_pace_model"] = False
    elif change == "few_before":
        laps.loc[laps["LAP_NUMBER"].between(1, 5), "is_usable_for_pace_model"] = False
    elif change == "missing_time":
        laps.loc[laps["is_in_lap"], "LAP_TIME_S"] = np.nan
    else:
        laps = laps[laps["LAP_NUMBER"] != 7]
    event = pit_events(laps).iloc[0]
    assert event["status"] == status
    assert np.isnan(event["pit_loss_s"])


def _practice() -> pd.DataFrame:
    frame = pd.DataFrame({
        "event_key": "2024_X", "session": "FP1", "CLASS": "HYPERCAR",
        "LAP_TIME_S": [100.0, 100.0, 100.0, 100.0, 120.0, 100.0, 100.0],
        "S1_S": 30.0, "S2_S": 30.0, "S3_S": 40.0, "FLAG_AT_FL": "GF",
        "is_in_lap": False, "is_out_lap": False,
        "stint_lap": [1, 2, 3, 4, 5, 6, 7],
    })
    return frame


def test_clean_practice_rule_drops_slow_first_and_flagged_laps():
    frame = _practice()
    frame.loc[6, "FLAG_AT_FL"] = "FCY"
    assert clean_practice_mask(frame).tolist() == [False, True, True, True, False, True, False]


@pytest.mark.parametrize("column, value", [("is_in_lap", True), ("is_out_lap", True), ("S2_S", np.nan)])
def test_clean_practice_rule_drops_pit_laps_and_missing_sectors(column, value):
    frame = _practice()
    frame.loc[2, column] = value
    assert not clean_practice_mask(frame).iloc[2]


def test_three_predictors_use_only_what_each_is_allowed():
    index = lambda events: pd.MultiIndex.from_tuples([(e, "HYPERCAR") for e in events], names=["event_key", "CLASS"])
    target = pd.Series([102.0, 103.0], index=index(["2024_X", "2025_X"]))
    practice = pd.Series([100.0, 101.0], index=index(["2024_X", "2025_X"]))
    table = pace_predictions(target, practice, ["2024_X"], ["2025_X"]).iloc[0]
    assert table["P1"] == pytest.approx(102.0)
    assert table["P2"] == pytest.approx(101.0 * 1.02)
    assert table["P3"] == pytest.approx(101.0)
    assert table["P3_abs_error_s"] == pytest.approx(2.0)


def test_wet_looking_session_is_dropped_from_practice_pace():
    frame = pd.concat([_practice().assign(session="FP1"), _practice().assign(session="FP2", LAP_TIME_S=lambda f: f["LAP_TIME_S"] * 1.2)], ignore_index=True)
    assert practice_pace(frame).iloc[0] == pytest.approx(100.0)
    near = pd.concat([_practice().assign(session="FP1"), _practice().assign(session="FP2", LAP_TIME_S=lambda f: f["LAP_TIME_S"] * 1.02)], ignore_index=True)
    assert 100.0 < practice_pace(near).iloc[0] <= 102.0


def test_fastest_session_version_uses_one_session():
    frame = pd.concat([_practice().assign(session="FP1"), _practice().assign(session="FP2", LAP_TIME_S=lambda f: f["LAP_TIME_S"] * 1.02)], ignore_index=True)
    assert practice_pace(frame, fastest_session_only=True).iloc[0] == pytest.approx(100.0)


def _errors(values: dict[str, list[float]], car_class: str = "HYPERCAR") -> pd.DataFrame:
    return pd.DataFrame([{"event_key": f"2025_{i}", "CLASS": car_class, "model": name, "mae_s": v}
                         for name, series in values.items() for i, v in enumerate(series)])


BASE = [1.0, 1.1, 0.9, 1.0, 1.05, 0.95, 1.02]


def test_ladder_moves_through_winners_in_order():
    errors = _errors({"F": BASE, "B": [v - 0.2 for v in BASE], "L": [v - 0.4 for v in BASE],
                      "Q": [v - 0.41 + 0.05 * (-1) ** i for i, v in enumerate(BASE)], "C": [v - 0.4 for v in BASE]})
    result = decision_ladder(errors, "HYPERCAR")
    assert result["holder"] == "L"
    assert [step["challenger"] for step in result["steps"]] == ["B", "L", "Q", "C"]
    assert [step["against"] for step in result["steps"]] == ["F", "B", "L", "L"]


def test_ladder_keeps_f_when_nothing_beats_it_and_does_not_test_q_or_c():
    wobble = [0.1, -0.1, 0.1, -0.1, 0.1, -0.1, 0.0]
    errors = _errors({"F": BASE, "B": [v + w for v, w in zip(BASE, wobble)], "L": [v - w for v, w in zip(BASE, wobble)],
                      "Q": [v - 0.5 for v in BASE], "C": BASE})
    result = decision_ladder(errors, "HYPERCAR")
    assert result["holder"] == "F"
    assert set(result["not_tested_description_only"]) == {"Q", "C"}
    assert [step["challenger"] for step in result["steps"]] == ["B", "L"]


def test_ladder_defined_when_l_beats_f_and_b_does_not():
    wobble = [0.1, -0.1, 0.1, -0.1, 0.1, -0.1, 0.0]
    errors = _errors({"F": BASE, "B": [v + w for v, w in zip(BASE, wobble)], "L": [v - 0.3 for v in BASE],
                      "Q": [v - 0.3 for v in BASE], "C": [v - 0.3 for v in BASE]})
    result = decision_ladder(errors, "HYPERCAR")
    assert result["holder"] == "L"
    assert result["steps"][1]["against"] == "F"


def test_instability_rule():
    primary = {"mean": 0.05, "t_interval": [0.03, 0.07]}
    assert not is_unstable(primary, 0.06)
    assert is_unstable(primary, 0.08)
    assert is_unstable({"mean": 0.05, "t_interval": [0.01, 0.09]}, -0.02)
    assert not is_unstable({"mean": 0.01, "t_interval": [-0.03, 0.05]}, -0.005)


def _stops(event: str, losses: list[float], car_class: str = "HYPERCAR", changed: bool = False) -> pd.DataFrame:
    return pd.DataFrame({"event_key": event, "NUMBER": [str(i) for i in range(len(losses))], "CLASS": car_class,
                         "status": "eligible", "pit_loss_s": losses, "pit_time_s": 40.0, "driver_changed": changed})


def test_pit_holdout_compares_seven_race_level_errors_per_class():
    fit = pd.concat([_stops(f"2024_{i}", [60.0 + 3 * i] * 9) for i in range(7)] + [_stops(f"2024_{i}", [70.0] * 9, "LMGT3") for i in range(7)], ignore_index=True)
    check = pd.concat([_stops(f"2025_{i}", [60.0 + 3 * i] * 9) for i in range(7)] + [_stops(f"2025_{i}", [70.0] * 9, "LMGT3") for i in range(7)], ignore_index=True)
    result = pit_holdout(fit, check)["HYPERCAR"]
    assert result["circuit_vs_class"]["races"] == 7
    assert result["class_figure_s"] == pytest.approx(69.0)
    assert result["circuit_vs_class"]["mean"] > 0


def test_pit_coverage_counts_the_share_inside_the_earlier_range():
    fit = pd.concat([_stops("2024_X", list(np.linspace(50, 70, 21))), _stops("2024_X", list(np.linspace(50, 70, 21)), "LMGT3")], ignore_index=True)
    check = pd.concat([_stops("2025_X", [60.0] * 8 + [99.0] * 2), _stops("2025_X", [60.0] * 10, "LMGT3")], ignore_index=True)
    result = pit_coverage(fit, check)
    assert result["HYPERCAR"]["race_classes"][0]["share_inside"] == pytest.approx(0.8)
    assert result["HYPERCAR"]["carries_over"] is True
    assert result["LMGT3"]["outside_70_to_90"] == 1
    assert pit_coverage(fit, check, driver_changed=True)["HYPERCAR"]["race_classes"] == []


def test_car_bootstrap_draws_whole_cars():
    stops = pd.concat([pd.DataFrame({"event_key": "2024_X", "NUMBER": str(car), "pit_loss_s": [55.0 + 2 * car] * 6}) for car in range(8)], ignore_index=True)
    low, high = car_bootstrap_median(stops, n_boot=500)
    assert high - low > 3.0  # Six identical stops per car give a wide interval only if whole cars are drawn.


def test_pace_comparisons_refuse_a_race_missing_a_class():
    rows = [{"event_key": "2025_A", "CLASS": c, "P1_abs_error_s": 1.0, "P2_abs_error_s": 1.0, "P3_abs_error_s": 1.0} for c in ("HYPERCAR", "LMGT3")]
    rows.append({"event_key": "2025_B", "CLASS": "HYPERCAR", "P1_abs_error_s": 1.0, "P2_abs_error_s": 1.0, "P3_abs_error_s": 1.0})
    with pytest.raises(ValueError):
        pace_comparisons(pd.DataFrame(rows))


def test_fit_models_refuse_two_races_at_one_circuit_for_the_circuit_model():
    frame = make_stints({"2024_X": 0.1, "2025_X": 0.1})
    with pytest.raises(ValueError):
        _models(frame, 21)
    assert "C" not in fit_age_models(pd.concat([frame, frame.assign(CLASS="LMGT3")], ignore_index=True), {"HYPERCAR": 21, "LMGT3": 21}, circuit_model=False)["HYPERCAR"]


def test_pace_comparisons_use_races_as_the_unit():
    rows = []
    for race in range(7):
        for car_class in ("HYPERCAR", "LMGT3"):
            rows.append({"event_key": f"2025_{race}", "CLASS": car_class, "P1_abs_error_s": 2.0 + 0.1 * race,
                         "P2_abs_error_s": 1.0 + 0.1 * race, "P3_abs_error_s": 2.0 + 0.1 * race})
    result = pace_comparisons(pd.DataFrame(rows))
    assert result["P2_vs_P3"]["races"] == 7
    assert result["P2_vs_P3"]["mean"] == pytest.approx(1.0)
    assert result["P2_vs_P3"]["clear_gap"] is True
    assert result["P1_vs_P3"]["clear_gap"] is False


def test_analysis_laps_removes_garage_stints_and_short_stints():
    frame = make_stints({"2024_X": 0.0}, stints=2, laps=8)
    frame["FLAG_AT_FL"] = "GF"
    for flag in ["is_first_lap", "is_pit_lap", "is_caution_lap", "is_after_caution", "is_missing_data", "is_slow_lap", "is_wet", "is_field_slow"]:
        frame[flag] = False
    frame["is_garage_stop"] = False
    frame.loc[(frame["NUMBER"] == "1") & (frame["stint_lap"] == 2), "is_garage_stop"] = True
    result = analysis_laps(frame)
    assert set(result["NUMBER"]) == {"2"}
    assert result["stint_all_green"].all()
    short = frame[frame["NUMBER"] == "2"].iloc[:3]
    assert analysis_laps(short).empty


def _flagged(frame: pd.DataFrame) -> pd.DataFrame:
    for flag in ["is_first_lap", "is_pit_lap", "is_caution_lap", "is_after_caution", "is_missing_data", "is_slow_lap", "is_wet", "is_field_slow"]:
        frame[flag] = False
    return frame.assign(is_garage_stop=False, FLAG_AT_FL="GF")


def test_loose_rule_keeps_moderately_slow_laps_and_drops_very_slow_ones():
    frame = _flagged(make_stints({"2024_X": 0.0}, stints=3, laps=10))
    frame.loc[frame.index[2], ["LAP_TIME_S", "is_slow_lap"]] = [frame["LAP_TIME_S"].median() * 1.10, True]
    frame.loc[frame.index[5], ["LAP_TIME_S", "is_slow_lap"]] = [frame["LAP_TIME_S"].median() * 1.40, True]
    assert len(analysis_laps(frame)) == 28
    assert len(analysis_laps(frame, slow_lap_rule="loose")) == 29


@pytest.mark.parametrize("flag, all_green", [("FF", True), ("FCY", False), ("SF", False)])
def test_finish_flag_does_not_count_as_a_caution(flag, all_green):
    frame = _flagged(make_stints({"2024_X": 0.0}, stints=1, laps=10))
    frame.loc[frame.index[-1], "FLAG_AT_FL"] = flag
    assert analysis_laps(frame)["stint_all_green"].all() is np.bool_(all_green)
