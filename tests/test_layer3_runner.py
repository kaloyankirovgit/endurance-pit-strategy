"""The whole E-020 runner on synthetic races. Every lap here is generated in the test and is not real timing data."""
from __future__ import annotations

import importlib.util
import json

import numpy as np
import pandas as pd
import pytest

from endurance_strategy.features.clean_laps import EXCLUSION_FLAGS
from endurance_strategy.io.load import CORPUS_V1
from endurance_strategy.models.pace import SealedDataError
from endurance_strategy.paths import PROJECT_ROOT

TRUE_SLOPE = 0.03


def synthetic_laps(event: str, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for car_class, base in (("HYPERCAR", 100.0), ("LMGT3", 110.0)):
        for car in range(5):
            elapsed, lap_number = rng.uniform(0, 5), 0
            number = f"{car_class[0]}{car}"
            for stint in range(1, 5):
                for stint_lap in range(1, 17):
                    lap_number += 1
                    out_lap, in_lap = stint_lap == 1 and stint > 1, stint_lap == 16 and stint < 4
                    time = base + TRUE_SLOPE * stint_lap + rng.normal(0, 0.2) + (0.8 if stint_lap == 2 else 0.0) + (12.0 if in_lap else 0.0) + (48.0 if out_lap else 0.0)
                    elapsed += time
                    rows.append({"event_key": event, "NUMBER": number, "CLASS": car_class, "LAP_NUMBER": lap_number, "stint_number": stint,
                                 "stint_lap": stint_lap, "LAP_TIME_S": time, "ELAPSED_S": elapsed, "S1_S": 30.0, "S2_S": 30.0, "S3_S": 40.0,
                                 "PIT_TIME_S": 40.0 if out_lap else np.nan, "is_in_lap": in_lap, "is_out_lap": out_lap, "is_garage_stop": False,
                                 "FLAG_AT_FL": "GF", "CROSSING_FINISH_LINE_IN_PIT": "B" if in_lap else "", "DRIVER_NUMBER": str(stint % 2),
                                 "DRIVER_NAME": f"{number}-{stint % 2}", "TRACK_TEMP": 30.0 + rng.normal(0, 0.5), "RAIN": 0.0})
    frame = pd.DataFrame(rows)
    for flag in EXCLUSION_FLAGS:
        frame[flag] = False
    frame["is_pit_lap"] = frame["is_in_lap"] | frame["is_out_lap"]
    frame["is_first_lap"] = frame["LAP_NUMBER"].eq(1)
    frame["is_usable_for_pace_model"] = ~frame[EXCLUSION_FLAGS].any(axis=1)
    frame["is_slow_lap_race_ref"] = frame["is_slow_lap"]
    frame["is_field_slow_race_ref"] = frame["is_field_slow"]
    frame["is_usable_race_ref"] = frame["is_usable_for_pace_model"]
    return frame


@pytest.fixture
def runner(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("run_layer3", PROJECT_ROOT / "scripts" / "run_layer3.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rng = np.random.default_rng(5)
    races = [event for event in CORPUS_V1 if event[:4] in ("2024", "2025")]
    laps = pd.concat([synthetic_laps(event, rng) for event in races], ignore_index=True)
    practice = laps[laps["stint_number"] <= 2].assign(session=lambda f: "FP" + f["stint_number"].astype(str))
    interim = tmp_path / "interim"
    interim.mkdir()
    laps.to_parquet(interim / "laps.parquet", index=False)
    practice.to_parquet(interim / "practice_laps.parquet", index=False)
    monkeypatch.setattr(module, "INTERIM_DIR", interim)
    monkeypatch.setattr(module, "CLEAN_RULE", "race")
    monkeypatch.setattr(module, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(module, "FIT_FILE", tmp_path / "fit.json")
    monkeypatch.setattr(module, "CHECK_FILE", tmp_path / "check.json")
    monkeypatch.setattr(module, "REFIT_FILE", tmp_path / "refit.json")
    monkeypatch.setattr(module, "POSTHOC_FILE", tmp_path / "posthoc.json")
    return module


def test_stages_run_in_order_and_recover_the_planted_effects(runner):
    with pytest.raises(SystemExit):
        runner.stage_check()
    with pytest.raises(SystemExit):
        runner.stage_refit(50)

    runner.stage_fit(50)
    fit = json.loads(runner.FIT_FILE.read_text())
    assert all(race.startswith("2024") and "LE_MANS" not in race for race in fit["races"])
    assert fit["part_b"]["primary"]["HYPERCAR"]["s_per_lap"]["races"] == 7
    assert fit["part_b"]["primary"]["HYPERCAR"]["s_per_lap"]["mean"] == pytest.approx(TRUE_SLOPE, abs=0.005)
    assert fit["part_b"]["warm_up_s_median_age2_minus_ages3to7"]["HYPERCAR"] == pytest.approx(0.8 - 2 * TRUE_SLOPE - TRUE_SLOPE, abs=0.1)
    assert fit["part_c"]["class_median_of_race_medians"]["HYPERCAR"]["median_s"] == pytest.approx(60.0, abs=0.5)

    with pytest.raises(SystemExit):  # The frozen fit can't be overwritten.
        runner.stage_fit(50)
    sensitivity = fit["part_b"]["sensitivity"]
    assert set(sensitivity) == {"loose_slow_lap_rule", "include_stint_lap_2", "drop_last_two_laps", "at_least_10_laps_per_stint",
                                "ages_to_median_stint_length", "all_green_stints", "track_temperature", "traffic_count", "other_bootstrap_seed"}
    primary_laps = fit["part_b"]["primary"]["HYPERCAR"]["laps"]
    assert sensitivity["drop_last_two_laps"]["HYPERCAR"]["laps"] < primary_laps
    assert sensitivity["include_stint_lap_2"]["HYPERCAR"]["laps"] > primary_laps
    assert sensitivity["include_stint_lap_2"]["HYPERCAR"]["s_per_lap"]["mean"] < TRUE_SLOPE  # The planted warm-up tilts the line.
    assert sensitivity["ages_to_median_stint_length"]["HYPERCAR"]["laps"] <= primary_laps

    runner.stage_check()
    check = json.loads(runner.CHECK_FILE.read_text())
    assert all(race.startswith("2025") for race in check["races"])
    assert check["part_b"]["ladder"]["HYPERCAR"]["steps"][0]["races"] == 7
    assert check["part_c"]["holdout"]["HYPERCAR"]["circuit_vs_class"]["races"] == 7
    assert check["part_d"]["comparisons"]["P2_vs_P3"]["races"] == 7

    with pytest.raises(SystemExit):  # The 2025 check runs once.
        runner.stage_check()

    runner.stage_refit(50)
    refit = json.loads(runner.REFIT_FILE.read_text())
    assert len(refit["races"]) == 14
    assert refit["support_limits"] == fit["part_a"]["support_limits"]

    runner.stage_posthoc()
    posthoc = json.loads(runner.POSTHOC_FILE.read_text())
    assert posthoc["ladder_without_wet_race"]["HYPERCAR"]["steps"][0]["races"] == 6
    assert posthoc["refit_without_wet_race"]["HYPERCAR"]["s_per_lap"]["races"] == 13
    assert posthoc["long_stops"]["long"] == 0
    assert posthoc["slope_2025_without_wet_race"]["HYPERCAR"]["races"] == 6
    assert posthoc["circuit_level_t_interval_s"]["HYPERCAR"]["races"] == 7
    assert posthoc["lmgt3_p2_vs_p1_leave_one_out"]["all"]["races"] == 7


def test_runner_cannot_load_the_sealed_season(runner):
    with pytest.raises(SealedDataError):
        runner.load(("2025", "2026"))


def test_drop_last_two_removes_the_last_two_laps_of_each_stint(runner):
    frame = pd.DataFrame({"event_key": "2024_X", "NUMBER": "1", "stint_number": [1] * 5 + [2] * 3, "stint_lap": [2, 3, 4, 5, 6, 2, 3, 4]})
    assert runner.drop_last_two(frame.sample(frac=1, random_state=1)).sort_values(["stint_number", "stint_lap"])["stint_lap"].tolist() == [2, 3, 4, 2]


def test_median_stint_limit_counts_the_whole_stint_and_respects_support(runner):
    laps = pd.DataFrame({"event_key": "2024_X", "NUMBER": "1", "stint_number": [1] * 20 + [2] * 30, "stint_lap": list(range(1, 21)) + list(range(1, 31))})
    frame = laps.assign(CLASS="HYPERCAR")[laps["stint_lap"].between(2, 15)]
    lmgt = frame.assign(CLASS="LMGT3", NUMBER="2")
    laps_all = pd.concat([laps, laps.assign(NUMBER="2")], ignore_index=True)
    limits = runner.median_stint_limits(laps_all, pd.concat([frame, lmgt], ignore_index=True), {"HYPERCAR": 40, "LMGT3": 18})
    assert limits == {"HYPERCAR": 25, "LMGT3": 18}


def test_each_run_has_its_own_rule_and_files(runner):
    runner.configure("e021")
    assert runner.CLEAN_RULE == "practice" and runner.FIT_FILE.name == "e021_fit.json"
    runner.configure("e020")
    assert runner.CLEAN_RULE == "race" and runner.CHECK_FILE.name == "e020_check.json"


def test_traffic_refit_runs_both_rules_on_open_seasons(runner):
    spec = importlib.util.spec_from_file_location("run_traffic_refit", PROJECT_ROOT / "scripts" / "run_traffic_refit.py")
    refit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(refit)
    laps = pd.read_parquet(runner.INTERIM_DIR / "laps.parquet")
    laps = laps[laps["event_key"].str[:4].isin(["2024", "2025"])].copy()
    marked = laps["stint_lap"].eq(5)  # The old rule flags these laps and the new one doesn't, so a mix-up shows.
    laps.loc[marked, "is_slow_lap_race_ref"] = True
    laps.loc[marked, "is_usable_race_ref"] = False
    result = refit.run(laps, n_boot=20)
    assert set(result) == {"practice", "race"}
    assert result["race"]["HYPERCAR"]["race_gap_window"]["sizes"]["races"] == 14
    assert result["race"]["HYPERCAR"]["past_window"]["sizes"]["laps"] < result["practice"]["HYPERCAR"]["past_window"]["sizes"]["laps"]
    assert set(result["practice"]["LMGT3"]) == {"race_gap_window", "past_window", "loose_rule_race_gap_window"}
    assert result["practice"]["LMGT3"]["race_gap_window"]["circuit_interval"]["clusters"] == 7


def test_rule_check_gates(runner):
    spec = importlib.util.spec_from_file_location("check_clean_rule", PROJECT_ROOT / "scripts" / "check_clean_rule.py")
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    rows = [{"event_key": e, "CLASS": c, "switched": e == check.WET_RACE} for e in ("2025_CIRCUIT_OF_THE_AMERICAS", "2024_IMOLA") for c in ("HYPERCAR", "LMGT3")]
    table = pd.DataFrame(rows)
    assert check.gates(table, {"2024": 1, "2025": 2}, {"2024": 1, "2025": 2}) == []
    assert len(check.gates(table, {"2024": 1, "2025": 3}, {"2024": 1, "2025": 2})) == 1
    table.loc[table["event_key"] == check.WET_RACE, "switched"] = False
    assert any("doesn't switch" in failure for failure in check.gates(table, {"2024": 1, "2025": 2}, {"2024": 1, "2025": 2}))
    many = pd.DataFrame([{"event_key": f"2024_{i}", "CLASS": "HYPERCAR", "switched": True} for i in range(5)])
    assert any("other race-classes" in failure for failure in check.gates(pd.concat([table.assign(switched=True), many]), {}, {}))
