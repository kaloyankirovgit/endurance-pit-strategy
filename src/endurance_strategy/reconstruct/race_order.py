from __future__ import annotations

import duckdb
import pandas as pd

RACE_ORDER_SQL = """
SELECT
    event_key,
    NUMBER,
    LAP_NUMBER,
    ROW_NUMBER() OVER lap_order AS position,
    ELAPSED_S - LAG(ELAPSED_S) OVER lap_order AS gap_ahead_s,
    ROW_NUMBER() OVER class_order AS class_position,
    ELAPSED_S - LAG(ELAPSED_S) OVER class_order AS class_gap_ahead_s,
    ELAPSED_S - LAG(ELAPSED_S) OVER road_order AS road_gap_ahead_s,
    LAG(NUMBER) OVER road_order AS road_car_ahead,
    LAG(CLASS) OVER road_order AS road_class_ahead
FROM laps
WINDOW
    lap_order AS (PARTITION BY event_key, LAP_NUMBER ORDER BY ELAPSED_S, NUMBER),
    class_order AS (PARTITION BY event_key, LAP_NUMBER, CLASS ORDER BY ELAPSED_S, NUMBER),
    road_order AS (PARTITION BY event_key ORDER BY ELAPSED_S, NUMBER)
"""


def add_race_order(frame: pd.DataFrame) -> pd.DataFrame:
    """Add race position and gaps at each crossing of the line.

    Position ranks the cars that completed the same lap by when they did it, so
    a lapped car ranks behind. `gap_ahead_s` is to the car ahead in the race,
    `road_gap_ahead_s` to whichever car crossed the line just before, on any lap.
    Ties break on car number.
    """
    con = duckdb.connect()
    con.register("laps", frame[["event_key", "NUMBER", "CLASS", "LAP_NUMBER", "ELAPSED_S"]])
    order = con.execute(RACE_ORDER_SQL).df()
    con.close()
    return frame.merge(order, on=["event_key", "NUMBER", "LAP_NUMBER"], how="left", validate="one_to_one")
