import pytest

from endurance_strategy.io.download import check_csv, event_key, missing_files, plan_files

ROOT = "wec/results/15_2026/08_AUTODROMO NAZIONALE DI MONZA"
HOUR = f"{ROOT}/689_FIA WEC/202611081100_Race/06_Hour 6"
EARLY = f"{ROOT}/689_FIA WEC/202611081100_Race/05_Hour 5"
SYNTHETIC_LISTING = [
    f"{EARLY}/23_Analysis_Race_Hour 5.CSV",
    f"{HOUR}/23_Analysis_Race_Hour 6.CSV",
    f"{HOUR}/23_Analysis_Race_Hour 6.PDF",
    f"{HOUR}/26_Weather_Race_Hour 6.CSV",
    f"{HOUR}/03_Classification_Race_Hour 6.CSV",
    f"{HOUR}/99_TrackLimits_Race_Hour 6.CSV",
    f"{ROOT}/689_FIA WEC/202611061030_Free Practice 1/23_Analysis_Free Practice 1.CSV",
    f"{ROOT}/689_FIA WEC/202611071240_Free Practice 3 - HYPERCAR/23_Analysis_Free Practice 3 - HYPERCAR.CSV",
    f"{ROOT}/689_FIA WEC/202611071505_Qualifying HYPERCAR/23_Analysis_Qualifying HYPERCAR.CSV",
    f"{ROOT}/690_Legends of Le Mans/202611071210_Race 1/23_Analysis_Race 1.CSV",
    f"{ROOT}/656_FIA WEC - TEST DAY/202611051030_Free Practice 1/23_Analysis_Free Practice 1.CSV",
]


def by_kind(planned):
    return {p["kind"]: p for p in planned if p["kind"] != "practice"}


def test_event_key_matches_the_existing_file_names():
    assert event_key("2026", "05_CIRCUIT OF THE AMERICAS") == "2026_CIRCUIT_OF_THE_AMERICAS"
    assert event_key("2026", "07_BARCELONA-CATALUNYA") == "2026_BARCELONA_CATALUNYA"


def test_plan_takes_the_last_hour_and_ignores_other_series_and_sessions():
    planned = plan_files(SYNTHETIC_LISTING, "2026")
    race = by_kind(planned)
    assert race["race"]["url"].endswith("23_Analysis_Race_Hour 6.CSV")
    assert race["race"]["hours"] == 6
    assert set(race) == {"race", "weather", "classification"}
    assert sorted(p["file"] for p in planned if p["kind"] == "practice") == [
        "2026_AUTODROMO_NAZIONALE_DI_MONZA__FP1.CSV",
        "2026_AUTODROMO_NAZIONALE_DI_MONZA__FP3_HYPERCAR.CSV",
    ]


def test_final_classification_is_preferred_when_both_exist():
    listing = [f"{HOUR}/23_Analysis_Race_Hour 6.CSV", f"{HOUR}/03_Classification_Race_Hour 6.CSV",
               f"{HOUR}/03_Classification_Race_Hour 6_Final.CSV"]
    assert by_kind(plan_files(listing, "2026"))["classification"]["url"].endswith("_Final.CSV")


def test_a_race_still_running_is_left_out():
    listing = [f"{ROOT}/689_FIA WEC/202611081100_Race/03_Hour 3/23_Analysis_Race_Hour 3.CSV"]
    assert plan_files(listing, "2026") == []


def test_files_already_on_disk_are_not_fetched_again(tmp_path):
    planned = plan_files(SYNTHETIC_LISTING, "2026")
    dirs = {kind: tmp_path / kind for kind in ("race", "weather", "classification", "practice")}
    for directory in dirs.values():
        directory.mkdir()
    (dirs["race"] / "2026_AUTODROMO_NAZIONALE_DI_MONZA.CSV").touch()
    assert all(item["kind"] != "race" for item in missing_files(planned, dirs))
    assert len(missing_files(planned, dirs)) == len(planned) - 1


def test_a_web_page_returned_with_status_200_is_refused():
    with pytest.raises(ValueError, match="not a CSV"):
        check_csv(b"<!doctype html><html></html>", "race", "u")


def test_a_csv_with_the_wrong_columns_is_refused():
    with pytest.raises(ValueError, match="has no"):
        check_csv(b"\xef\xbb\xbfA;B;C\n1;2;3\n", "race", "u")


def test_a_real_header_passes():
    check_csv(b"\xef\xbb\xbfNUMBER; LAP_TIME; ELAPSED;CLASS;\n1;2;3;4\n", "race", "u")
