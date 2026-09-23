"""Data-quality checks for WEC race data.

Each check returns the ROWS THAT VIOLATE it, not a boolean. Two reasons:

1. A count alone tells you something is wrong but not what. The violating rows
   are the evidence, and they usually explain themselves -- a broken lap
   sequence is often a retirement, not a parsing bug.
2. The project flags rather than deletes (`.claude/rules/data-engineering.md`).
   You cannot flag a row you did not identify.

An empty returned frame means the check passed.

TO IMPLEMENT: the three functions below. See the session brief for the idea
behind each. Signatures and docstrings are fixed; the bodies are yours.
"""

from __future__ import annotations

import pandas as pd


def find_duplicate_laps(frame: pd.DataFrame) -> pd.DataFrame:
    """Rows where the same car appears twice on the same lap of the same event.

    A car cannot complete lap 42 twice. If it appears to, either the source
    repeated a row or our idea of what identifies a lap is wrong -- and both
    matter before anything is grouped by lap.

    Returns every row involved in a duplicate (all copies, not just the extras),
    so the duplicates can be compared against each other.
    """
    raise NotImplementedError


def find_elapsed_time_regressions(frame: pd.DataFrame) -> pd.DataFrame:
    """Rows where a car's ELAPSED_S is not greater than its previous lap's.

    Elapsed race time must increase monotonically for a given car. A decrease
    means the rows are out of order, the parse is wrong, or rows from two cars
    have been merged -- any of which would corrupt race-order reconstruction,
    which is built directly on elapsed time.

    Returns the offending rows (the later row of each bad pair).
    """
    raise NotImplementedError


def find_lap_number_breaks(frame: pd.DataFrame) -> pd.DataFrame:
    """Rows where a car's LAP_NUMBER does not increase by exactly 1.

    Gaps and repeats both matter. A gap may be genuine (a lap not recorded) or
    a sign of missing data; either way, stint reconstruction counts laps within
    a stint, so an unnoticed gap silently shortens a stint.

    Returns the rows where the step from the previous lap is not 1.
    """
    raise NotImplementedError
