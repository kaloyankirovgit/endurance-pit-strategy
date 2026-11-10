"""Clean practice laps and a weekend's practice pace, as registered in E-020.

Practice pace is the reference for the slow-lap rule from E-021, and one of E-020's predictors of race pace.
"""
from __future__ import annotations

import pandas as pd

from endurance_strategy.features.clean_laps import FIELD_SLOW_RATIO, SLOW_LAP_RATIO


def clean_practice_mask(practice: pd.DataFrame) -> pd.Series:
    """Green, not a pit lap, not a car's first lap of the run, fully timed, and within 1.07 of the session's class median.

    No wet filter at lap level, because no weather is joined to practice. `practice_pace` drops wet-looking sessions.
    """
    green = practice["FLAG_AT_FL"].eq("GF")
    running = ~(practice["is_in_lap"] | practice["is_out_lap"])
    timed = practice[["LAP_TIME_S", "S1_S", "S2_S", "S3_S"]].notna().all(axis=1)
    reference = (practice["LAP_TIME_S"].where(green & running)
                 .groupby([practice["event_key"], practice["session"], practice["CLASS"]]).transform("median"))
    return green & running & timed & practice["stint_lap"].ge(2) & practice["LAP_TIME_S"].le(SLOW_LAP_RATIO * reference)


def practice_pace(practice: pd.DataFrame, fastest_session_only: bool = False, wet_session_ratio: float = FIELD_SLOW_RATIO) -> pd.Series:
    """Class median of clean practice laps, indexed by (event_key, CLASS).

    A session whose class median is over `wet_session_ratio` times the fastest session's is dropped,
    because no weather is joined to practice and a wet session would pass the per-session lap rule whole.
    """
    clean = practice[clean_practice_mask(practice)]
    session_median = clean.groupby(["event_key", "CLASS", "session"])["LAP_TIME_S"].transform("median")
    fastest = session_median.groupby([clean["event_key"], clean["CLASS"]]).transform("min")
    if fastest_session_only:
        return clean[session_median == fastest].groupby(["event_key", "CLASS"])["LAP_TIME_S"].median()
    return clean[session_median <= wet_session_ratio * fastest].groupby(["event_key", "CLASS"])["LAP_TIME_S"].median()


def practice_reference_table(practice: pd.DataFrame) -> pd.DataFrame:
    """Per event and class: practice pace as in `practice_pace`, with the cars, laps and sessions behind it.

    E-021 uses practice as a reference only when it has enough cars and laps (see `features.clean_laps`).
    """
    clean = practice[clean_practice_mask(practice)]
    session_median = clean.groupby(["event_key", "CLASS", "session"])["LAP_TIME_S"].transform("median")
    fastest = session_median.groupby([clean["event_key"], clean["CLASS"]]).transform("min")
    kept = clean[session_median <= FIELD_SLOW_RATIO * fastest]
    grouped = kept.groupby(["event_key", "CLASS"])
    table = pd.DataFrame({"pace": grouped["LAP_TIME_S"].median(), "cars": grouped["NUMBER"].nunique(), "laps": grouped.size()})
    sessions = clean.groupby(["event_key", "CLASS"])["session"].nunique()
    table["sessions_dropped"] = (sessions.reindex(table.index) - grouped["session"].nunique()).astype(int)
    return table
