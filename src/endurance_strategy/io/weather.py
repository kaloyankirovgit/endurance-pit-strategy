from __future__ import annotations

from pathlib import Path

import pandas as pd

WEATHER_COLUMNS = ["AIR_TEMP", "TRACK_TEMP", "HUMIDITY", "PRESSURE", "WIND_SPEED", "WIND_DIRECTION", "RAIN"]


def load_weather_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    frame = pd.read_csv(path, sep=";", encoding="utf-8-sig")
    frame = frame.loc[:, [c for c in frame.columns if not c.startswith("Unnamed:")]]
    frame[WEATHER_COLUMNS] = frame[WEATHER_COLUMNS].astype(float)
    frame["weather_utc"] = pd.to_datetime(frame["TIME_UTC_SECONDS"], unit="s", utc=True).astype("datetime64[ns, UTC]")
    frame["event_key"] = path.stem
    return frame


def load_weather_corpus(directory: str | Path, seasons: tuple[str, ...] = ("2024", "2025", "2026")) -> pd.DataFrame:
    paths = sorted(p for p in Path(directory).glob("*.CSV") if p.stem.split("_")[0] in seasons)
    if not paths:
        raise FileNotFoundError(f"no weather CSVs for seasons {seasons} in {directory}")
    return pd.concat([load_weather_csv(p) for p in paths], ignore_index=True)
