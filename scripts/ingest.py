#!/usr/bin/env python3
"""One command for new data: fetch any race or practice files not on disk, check them and rebuild the tables."""
from __future__ import annotations

import argparse
from collections import Counter

import pandas as pd

from endurance_strategy.io.download import CLASSIFICATION_DIR, CORPUS_SEASONS, PRACTICE_DIR, download_new
from endurance_strategy.paths import INTERIM_DIR
from endurance_strategy.pipeline import run
from endurance_strategy.validation.classification import compare_to_classification, load_classification_corpus, summarise_by_race


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seasons", nargs="+", default=list(CORPUS_SEASONS))
    parser.add_argument("--dry-run", action="store_true", help="list what's new without downloading")
    args = parser.parse_args()

    new = download_new(tuple(args.seasons), dry_run=args.dry_run)
    print("new files:", dict(Counter(item["kind"] for item in new)) or "none")
    for item in new:
        if item["kind"] == "race":
            print("  new race:", item["event_key"])
    if args.dry_run:
        return
    for name, rows in run(practice_dir=PRACTICE_DIR).items():
        print(f"{name:14s} {rows:>8,}")
    new_races = [item["event_key"] for item in new if item["kind"] == "race"]
    if new_races:
        laps = pd.read_parquet(INTERIM_DIR / "laps.parquet", columns=["event_key", "NUMBER", "LAP_NUMBER", "ELAPSED_S"])
        official = load_classification_corpus(CLASSIFICATION_DIR)
        comparison = compare_to_classification(laps[laps["event_key"].isin(new_races)], official[official["event_key"].isin(new_races)])
        print(summarise_by_race(comparison).to_string())


if __name__ == "__main__":
    main()
