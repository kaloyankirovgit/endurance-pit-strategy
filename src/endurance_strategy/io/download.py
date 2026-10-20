from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from endurance_strategy.paths import WEC_DIR

WEATHER_DIR = WEC_DIR.parent / "wec_weather"
CLASSIFICATION_DIR = WEC_DIR.parent / "wec_classification"

CORPUS_SEASONS = ("2024", "2025", "2026")


def weather_url(race_url: str) -> list[str]:
    return [race_url.replace("23_Analysis_Race_", "26_Weather_Race_")]


def classification_url(race_url: str) -> list[str]:
    plain = race_url.replace("23_Analysis_Race_", "03_Classification_Race_")
    return [plain, plain.replace(".CSV", "_Final.CSV")]


def _fetch_first(urls: list[str]) -> tuple[str, bytes]:
    for url in urls[:-1]:
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                return url, response.read()
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
    with urllib.request.urlopen(urls[-1], timeout=60) as response:
        return urls[-1], response.read()


def _download_companion(url_for, target_dir: Path, seasons: tuple[str, ...]) -> list[dict]:
    """Fetch the file that sits next to each race file in the race manifest and record provenance."""
    target_dir.mkdir(parents=True, exist_ok=True)
    races = json.loads((WEC_DIR / "_manifest.json").read_text())
    records = []
    for race in races:
        if race["season"] not in seasons:
            continue
        url, content = _fetch_first(url_for(race["url"]))
        (target_dir / race["file"]).write_bytes(content)
        records.append({
            "file": race["file"],
            "url": url,
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "downloaded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
    (target_dir / "_manifest.json").write_text(json.dumps(records, indent=2))
    return records


def download_weather(seasons: tuple[str, ...] = CORPUS_SEASONS) -> list[dict]:
    return _download_companion(weather_url, WEATHER_DIR, seasons)


def download_classification(seasons: tuple[str, ...] = CORPUS_SEASONS) -> list[dict]:
    return _download_companion(classification_url, CLASSIFICATION_DIR, seasons)
