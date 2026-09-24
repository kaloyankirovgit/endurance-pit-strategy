from __future__ import annotations

import json
from datetime import date

import pandas as pd

from endurance_strategy.paths import WEC_DIR

CIRCUIT_TIMEZONES = {
    "LE_MANS": "Europe/Paris",
    "SPA_FRANCORCHAMPS": "Europe/Brussels",
    "IMOLA": "Europe/Rome",
    "CIRCUIT_OF_THE_AMERICAS": "America/Chicago",
    "SAO_PAULO": "America/Sao_Paulo",
    "FUJI_SPEEDWAY": "Asia/Tokyo",
    "BAHRAIN_INTERNATIONAL_CIRCUIT": "Asia/Bahrain",
    "LOSAIL": "Asia/Qatar",
}


def race_dates_from_manifest() -> dict[str, date]:
    """Local start date of each race, from the session folder in its download URL."""
    races = json.loads((WEC_DIR / "_manifest.json").read_text())
    dates = {}
    for race in races:
        session = race["url"].split("/")[-3]
        dates[race["file"].removesuffix(".CSV")] = pd.to_datetime(session[:8], format="%Y%m%d").date()
    return dates


def add_lap_utc(frame: pd.DataFrame, race_dates: dict[str, date] | None = None) -> pd.DataFrame:
    """Add `lap_end_utc`, the UTC time each lap crossed the line.

    Built from HOUR (local wall clock) rather than ELAPSED, because ELAPSED
    stops during a red flag. A clock earlier than the race's first crossing
    means the race has passed midnight.
    """
    race_dates = race_dates or race_dates_from_manifest()
    out = frame.copy()
    clock = pd.to_timedelta(out["HOUR"])
    first_index = out.groupby("event_key")["ELAPSED_S"].idxmin()
    first_clock = out["event_key"].map(pd.Series(clock.loc[first_index].to_numpy(), index=first_index.index))
    local = pd.to_datetime(out["event_key"].map(race_dates)) + clock
    local = local + pd.to_timedelta((clock < first_clock).astype(int), unit="D")

    utc = pd.Series(pd.NaT, index=out.index, dtype="datetime64[ns, UTC]")
    for event_key, index in out.groupby("event_key").groups.items():
        zone = CIRCUIT_TIMEZONES[event_key.split("_", 1)[1]]
        utc.loc[index] = local.loc[index].dt.tz_localize(zone).dt.tz_convert("UTC")
    out["lap_end_utc"] = utc
    return out
