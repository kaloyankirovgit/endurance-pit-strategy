"""Load FIA WEC race analysis CSVs into a standard dataframe.

The only place in the project that touches the raw file format. Five source
quirks are handled here so they are not rediscovered elsewhere: UTF-8 BOM,
leading spaces on the first 15 headers, two different duration formats, car
number as a string ("007"), and an empty trailing column. See `docs/GUIDE.md`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Identifiers, not quantities: read as strings so leading zeros survive.
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

# Converted to float seconds alongside the original. S1/S2/S3 are excluded:
# the source already provides S1_SECONDS etc.
_DURATION_COLUMNS = ["LAP_TIME", "PIT_TIME", "ELAPSED"]


def parse_duration(value: object) -> float:
    """Convert a WEC duration string to seconds.

    Handles every format the source uses, by splitting on ":" and weighting
    from the right, so "51.908", "3:54.555" and "0:01:15.964" all work without
    the caller needing to know which it has.

    Returns NaN for blanks and unparseable values rather than raising: a single
    malformed cell in 236,000 rows should be flagged by a quality check, not
    abort the load.
    """
    if value is None:
        return float("nan")
    text = str(value).strip()
    if not text:
        return float("nan")

    parts = text.split(":")
    try:
        numbers = [float(part) for part in parts]
    except ValueError:
        return float("nan")

    seconds = 0.0
    for power, number in enumerate(reversed(numbers)):
        seconds += number * (60.0**power)
    return seconds


def load_race_csv(path: str | Path) -> pd.DataFrame:
    """Read one race analysis CSV into a standardised dataframe.

    The frame keeps every source column unchanged and *adds* parsed columns
    suffixed ``_S`` (seconds). Nothing is dropped, renamed or corrected --
    that belongs to the interim layer, and the raw shape has to stay
    inspectable for the quality checks to mean anything.

    Two columns are added for provenance: ``source_file`` and ``event_key``,
    so that rows keep their origin once several races are concatenated.
    """
    path = Path(path)

    frame = pd.read_csv(
        path,
        sep=";",
        encoding="utf-8-sig",
        dtype=str,
        keep_default_na=False,
    )

    frame.columns = [column.strip() for column in frame.columns]

    # The trailing ";" produces an empty column, which pandas names "Unnamed: 29".
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
    frame["event_key"] = path.stem  # e.g. "2025_LE_MANS"

    return frame


def load_corpus(directory: str | Path, seasons: tuple[str, ...] = ("2024", "2025", "2026")) -> pd.DataFrame:
    """Load every race file for the given seasons into one dataframe.

    Defaults to the 2024-2026 primary corpus fixed by DECISIONS D-010. The 2023
    files sit in the same directory but are a different championship (LMGTE Am
    rather than LMGT3, LMP2 full-season), so they are excluded unless asked for.
    """
    directory = Path(directory)
    paths = sorted(
        path
        for path in directory.glob("*.CSV")
        if path.stem.split("_")[0] in seasons
    )
    if not paths:
        raise FileNotFoundError(f"no race CSVs for seasons {seasons} in {directory}")

    return pd.concat([load_race_csv(path) for path in paths], ignore_index=True)
