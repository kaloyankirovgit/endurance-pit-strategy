from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from endurance_strategy.paths import WEC_DIR

WEATHER_DIR = WEC_DIR.parent / "wec_weather"


def weather_url(race_url: str) -> str:
    return race_url.replace("23_Analysis_Race_", "26_Weather_Race_")


def download_weather(seasons: tuple[str, ...] = ("2024", "2025", "2026")) -> list[dict]:
    """Fetch the weather CSV for each race in the race manifest and record provenance."""
    WEATHER_DIR.mkdir(parents=True, exist_ok=True)
    races = json.loads((WEC_DIR / "_manifest.json").read_text())
    records = []
    for race in races:
        if race["season"] not in seasons:
            continue
        url = weather_url(race["url"])
        with urllib.request.urlopen(url, timeout=60) as response:
            content = response.read()
        target = WEATHER_DIR / race["file"]
        target.write_bytes(content)
        records.append({
            "file": race["file"],
            "url": url,
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "downloaded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
    (WEATHER_DIR / "_manifest.json").write_text(json.dumps(records, indent=2))
    return records
