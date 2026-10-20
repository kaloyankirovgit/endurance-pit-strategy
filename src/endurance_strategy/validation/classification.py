from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from endurance_strategy.io.load import parse_duration

FINAL_ORDER_SQL = """
SELECT
    event_key,
    NUMBER,
    MAX(LAP_NUMBER) AS rebuilt_laps,
    arg_max(ELAPSED_S, LAP_NUMBER) AS rebuilt_time_s
FROM laps
GROUP BY event_key, NUMBER
"""


def load_classification(path: str | Path) -> pd.DataFrame:
    """Read one end-of-race classification CSV, picking columns by name since the layout varies."""
    path = Path(path)
    frame = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    frame.columns = [column.strip() for column in frame.columns]
    frame = frame[["POSITION", "NUMBER", "STATUS", "LAPS", "CLASS", "TOTAL_TIME"]].apply(lambda column: column.str.strip())
    return pd.DataFrame({
        "event_key": path.stem,
        "NUMBER": frame["NUMBER"],
        "official_position": pd.to_numeric(frame["POSITION"]),
        "official_status": frame["STATUS"],
        "official_laps": pd.to_numeric(frame["LAPS"]),
        "official_class": frame["CLASS"],
        "official_time_s": frame["TOTAL_TIME"].str.replace("'", ":").map(parse_duration),
    })


def load_classification_corpus(directory: str | Path, seasons: tuple[str, ...] = ("2024", "2025", "2026")) -> pd.DataFrame:
    paths = sorted(p for p in Path(directory).glob("*.CSV") if p.stem.split("_")[0] in seasons)
    if not paths:
        raise FileNotFoundError(f"no classification CSVs for seasons {seasons} in {directory}")
    return pd.concat([load_classification(p) for p in paths], ignore_index=True)


def rebuilt_final_order(laps: pd.DataFrame) -> pd.DataFrame:
    """Each car's laps and elapsed time at its last crossing, ranked by laps then time (ties on car number)."""
    con = duckdb.connect()
    con.register("laps", laps[["event_key", "NUMBER", "LAP_NUMBER", "ELAPSED_S"]])
    final = con.execute(FINAL_ORDER_SQL).df()
    con.close()
    final = final.sort_values(["event_key", "rebuilt_laps", "rebuilt_time_s", "NUMBER"],
                              ascending=[True, False, True, True])
    final["rebuilt_position"] = final.groupby("event_key").cumcount() + 1
    return final.reset_index(drop=True)


def compare_to_classification(laps: pd.DataFrame, classification: pd.DataFrame,
                              time_tolerance_s: float = 0.001) -> pd.DataFrame:
    """One row per car in either source, with the checks that say where the rebuild and the official result agree.

    Positions are compared among cars the official result lists as Classified, so retirements
    and disqualifications, which the rules place by status rather than distance, don't count against the rebuild.
    """
    merged = rebuilt_final_order(laps).merge(classification, on=["event_key", "NUMBER"], how="outer", indicator=True)
    merged["in_both"] = merged["_merge"] == "both"
    merged["laps_match"] = merged["in_both"] & (merged["rebuilt_laps"] == merged["official_laps"])
    merged["time_diff_s"] = merged["rebuilt_time_s"] - merged["official_time_s"]
    merged["time_match"] = merged["in_both"] & (merged["time_diff_s"].abs() <= time_tolerance_s)

    whole_seconds = (merged["time_diff_s"].round(3) % 1 == 0) & (merged["time_diff_s"] < 0)
    merged["difference"] = "exact"
    merged.loc[~merged["in_both"], "difference"] = "missing"
    merged.loc[merged["laps_match"] & ~merged["time_match"] & whole_seconds, "difference"] = "time_penalty"
    merged.loc[merged["laps_match"] & ~merged["time_match"] & ~whole_seconds, "difference"] = "unexplained_time"
    merged.loc[merged["in_both"] & ~merged["laps_match"], "difference"] = "fewer_official_laps"

    classified = merged["in_both"] & (merged["official_status"] == "Classified")
    merged["position_match"] = classified & _same_rank(merged, classified)
    unpenalised = classified & (merged["difference"] == "exact")
    merged["unpenalised_order_match"] = unpenalised & _same_rank(merged, unpenalised)
    return merged.drop(columns="_merge").sort_values(["event_key", "official_position"]).reset_index(drop=True)


def _same_rank(frame: pd.DataFrame, subset: pd.Series) -> pd.Series:
    groups = frame[subset].groupby("event_key")
    rebuilt = groups["rebuilt_position"].rank(method="first")
    official = groups["official_position"].rank(method="first")
    return (rebuilt == official).reindex(frame.index, fill_value=False)


def summarise_by_race(comparison: pd.DataFrame) -> pd.DataFrame:
    by_race = comparison.groupby("event_key")
    classified = comparison[comparison["official_status"] == "Classified"].groupby("event_key")
    unpenalised = comparison[(comparison["official_status"] == "Classified") & (comparison["difference"] == "exact")]
    summary = pd.DataFrame({
        "cars": by_race.size(),
        "missing_from_rebuild": comparison[comparison["rebuilt_laps"].isna()].groupby("event_key").size(),
        "missing_from_official": comparison[comparison["official_status"].isna()].groupby("event_key").size(),
        "laps_match": by_race["laps_match"].sum(),
        "time_match": by_race["time_match"].sum(),
        "classified": classified.size(),
        "classified_position_match": classified["position_match"].sum(),
        "unpenalised_classified": unpenalised.groupby("event_key").size(),
        "unpenalised_order_match": unpenalised.groupby("event_key")["unpenalised_order_match"].sum(),
    })
    differences = pd.crosstab(comparison["event_key"], comparison["difference"])
    return summary.join(differences).fillna(0).astype(int)


if __name__ == "__main__":
    from endurance_strategy.io.download import CLASSIFICATION_DIR
    from endurance_strategy.paths import INTERIM_DIR, PROCESSED_DIR

    laps = pd.read_parquet(INTERIM_DIR / "laps.parquet", columns=["event_key", "NUMBER", "LAP_NUMBER", "ELAPSED_S"])
    comparison = compare_to_classification(laps, load_classification_corpus(CLASSIFICATION_DIR))
    comparison.to_parquet(PROCESSED_DIR / "classification_check.parquet", index=False)
    summary = summarise_by_race(comparison)
    print(summary.to_string())
    print(summary.sum().to_string())
