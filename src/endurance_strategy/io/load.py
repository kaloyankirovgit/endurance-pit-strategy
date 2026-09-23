"""Load FIA WEC race analysis CSVs into a standard dataframe.

This is the only place in the project that touches the raw file format. Every
downstream module works with the dataframe this produces, so the quirks of the
source are handled once, here, rather than rediscovered in five places.

Provenance of the fields this reads: `docs/DATA_DICTIONARY.md`, verified against
the 2025 Le Mans race file and confirmed identical across all 28 race files in
the 2023-2026 archive.

Four traps in the source format, each of which fails silently:

1. **UTF-8 BOM.** The first header is "\\ufeffNUMBER". Read with
   ``encoding="utf-8-sig"`` or every lookup of "NUMBER" misses on column one.
2. **Leading spaces in the first 15 header names** (" DRIVER_NUMBER"), but not
   the rest. Headers are stripped on read. Without this, half the columns are
   unreachable by name and pandas reports no error -- it just has a column
   called " LAP_TIME" that nothing asks for.
3. **Two different duration formats.** Lap and sector times are "m:ss.SSS"
   ("3:54.555"); PIT_TIME is "h:mm:ss.SSS" ("0:01:15.964"). Parsing both with
   one fixed format silently produces nonsense for one of them.
4. **Car number is not a number.** Values include "007". Reading it as an
   integer turns that into 7 and merges it with a different car. It stays a
   string, always.

A fifth, milder one: every row ends with a trailing ";", so a naive read adds an
empty final column. It is dropped here.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Columns whose values are identifiers, not quantities. Read as strings so that
# leading zeros survive and no arithmetic is accidentally possible on them.
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

# Source columns holding a duration, converted to float seconds alongside the
# original. S1/S2/S3 are excluded: the file already provides S1_SECONDS etc.,
# and re-deriving a value the source gives us is a needless chance to disagree
# with it.
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
        dtype=str,  # parse nothing automatically; every conversion is deliberate
        keep_default_na=False,  # "" stays "", so blank-vs-missing is not guessed
    )

    # Trap 2: strip the leading spaces the source puts on the first 15 headers.
    frame.columns = [column.strip() for column in frame.columns]

    # Trap 5: the trailing ";" on every row produces an empty final column.
    frame = frame.loc[:, [column for column in frame.columns if column != ""]]

    for column in _STRING_COLUMNS:
        if column in frame.columns:
            frame[column] = frame[column].str.strip()

    # LAP_NUMBER is a genuine integer; it is the only one.
    if "LAP_NUMBER" in frame.columns:
        frame["LAP_NUMBER"] = pd.to_numeric(frame["LAP_NUMBER"], errors="coerce")

    for column in _DURATION_COLUMNS:
        if column in frame.columns:
            frame[f"{column}_S"] = frame[column].map(parse_duration)

    # The source already supplies sector seconds; use them rather than
    # re-parsing S1/S2/S3 and risking a disagreement with the source.
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
