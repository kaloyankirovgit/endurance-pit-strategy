from __future__ import annotations

import pandera.pandas as pa

CLASSES = ["HYPERCAR", "LMP2", "LMGT3"]
FLAGS = ["GF", "SF", "FCY", "FF", "RF"]

positive = pa.Check.gt(0)

INTERIM_LAPS = pa.DataFrameSchema(
    {
        "event_key": pa.Column(str),
        "NUMBER": pa.Column(str),
        "CLASS": pa.Column(str, pa.Check.isin(CLASSES)),
        "LAP_NUMBER": pa.Column(int, pa.Check.ge(1)),
        "LAP_TIME_S": pa.Column(float, positive, nullable=True),
        "ELAPSED_S": pa.Column(float, positive),
        "PIT_TIME_S": pa.Column(float, positive, nullable=True),
        "FLAG_AT_FL": pa.Column(str, pa.Check.isin(FLAGS)),
        "stint_number": pa.Column(int, pa.Check.ge(1)),
        "stint_lap": pa.Column(int, pa.Check.ge(1)),
        "position": pa.Column(int, pa.Check.ge(1)),
        "class_position": pa.Column(int, pa.Check.ge(1)),
        "gap_ahead_s": pa.Column(float, pa.Check.ge(0), nullable=True),
        "road_gap_ahead_s": pa.Column(float, pa.Check.ge(0), nullable=True),
        "lap_end_utc": pa.Column("datetime64[ns, UTC]"),
        "RAIN": pa.Column(float, pa.Check.ge(0), nullable=True),
        "is_in_lap": pa.Column(bool),
        "is_out_lap": pa.Column(bool),
        "is_garage_stop": pa.Column(bool),
        "is_usable_for_pace_model": pa.Column(bool),
    },
    unique=["event_key", "NUMBER", "LAP_NUMBER"],
    strict=False,
    coerce=False,
)
