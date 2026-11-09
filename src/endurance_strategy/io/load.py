from __future__ import annotations

from pathlib import Path

import pandas as pd

_STRING_COLUMNS = [
    "NUMBER",
    "DRIVER_NUMBER",
    "CLASS",
    "GROUP",
    "TEAM",
    "MANUFACTURER",
    "DRIVER_NAME",
    "FLAG_AT_FL",
    "CROSSING_FINISH_LINE_IN_PIT",
]

_DURATION_COLUMNS = ["LAP_TIME", "PIT_TIME", "ELAPSED"]

# The races behind every result reported up to E-019. New races join the tables but not these figures.
CORPUS_V1 = tuple(
    f"{season}_{circuit}"
    for season, circuits in {
        "2024": ("BAHRAIN_INTERNATIONAL_CIRCUIT", "CIRCUIT_OF_THE_AMERICAS", "FUJI_SPEEDWAY", "IMOLA", "LE_MANS", "LOSAIL",
                 "SAO_PAULO", "SPA_FRANCORCHAMPS"),
        "2025": ("BAHRAIN_INTERNATIONAL_CIRCUIT", "CIRCUIT_OF_THE_AMERICAS", "FUJI_SPEEDWAY", "IMOLA", "LE_MANS", "LOSAIL",
                 "SAO_PAULO", "SPA_FRANCORCHAMPS"),
        "2026": ("CIRCUIT_OF_THE_AMERICAS", "IMOLA", "LE_MANS", "SAO_PAULO", "SPA_FRANCORCHAMPS"),
    }.items()
    for circuit in circuits
)


def parse_duration(value: object) -> float:
    """Seconds from "51.908", "3:54.555" or "0:01:15.964". NaN if blank or bad."""
    if value is None:
        return float("nan")
    text = str(value).strip()
    if not text:
        return float("nan")

    try:
        numbers = [float(part) for part in text.split(":")]
    except ValueError:
        return float("nan")

    return sum(number * 60.0**power for power, number in enumerate(reversed(numbers)))


def load_race_csv(path: str | Path) -> pd.DataFrame:
    """Read one race CSV. Source columns are kept as-is; parsed ones are added."""
    path = Path(path)

    frame = pd.read_csv(
        path,
        sep=";",
        encoding="utf-8-sig",
        dtype=str,
        keep_default_na=False,
    )

    frame.columns = [column.strip() for column in frame.columns]
    frame = frame.loc[
        :,
        [
            column
            for column in frame.columns
            if column != "" and not column.startswith("Unnamed:")
        ],
    ]

    for column in _STRING_COLUMNS:
        if column in frame.columns:
            frame[column] = frame[column].str.strip()

    if "LAP_NUMBER" in frame.columns:
        frame["LAP_NUMBER"] = pd.to_numeric(frame["LAP_NUMBER"], errors="coerce")

    for column in _DURATION_COLUMNS:
        if column in frame.columns:
            frame[f"{column}_S"] = frame[column].map(parse_duration)

    for sector in ("S1", "S2", "S3"):
        source_column = f"{sector}_SECONDS"
        if source_column in frame.columns:
            frame[f"{sector}_S"] = pd.to_numeric(
                frame[source_column].str.strip(), errors="coerce"
            )

    for column in ("KPH", "TOP_SPEED"):
        if column in frame.columns:
            frame[column + "_N"] = pd.to_numeric(frame[column], errors="coerce")

    frame["source_file"] = path.name
    frame["event_key"] = path.stem

    return frame


def load_corpus(directory: str | Path, seasons: tuple[str, ...] = ("2024", "2025", "2026")) -> pd.DataFrame:
    """Load every race file for the given seasons into one frame."""
    directory = Path(directory)
    paths = sorted(
        path
        for path in directory.glob("*.CSV")
        if path.stem.split("_")[0] in seasons
    )
    if not paths:
        raise FileNotFoundError(f"no race CSVs for seasons {seasons} in {directory}")

    return pd.concat([load_race_csv(path) for path in paths], ignore_index=True)
