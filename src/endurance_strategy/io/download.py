from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from endurance_strategy.paths import WEC_DIR

WEATHER_DIR = WEC_DIR.parent / "wec_weather"
CLASSIFICATION_DIR = WEC_DIR.parent / "wec_classification"
PRACTICE_DIR = WEC_DIR.parent / "wec_practice"
TARGET_DIRS = {"race": WEC_DIR, "weather": WEATHER_DIR, "classification": CLASSIFICATION_DIR, "practice": PRACTICE_DIR}

CORPUS_SEASONS = ("2024", "2025", "2026")
FILES_ROOT = "https://files.alkamelcloud.com/"
RESULTS_INDEX = FILES_ROOT + "wec/manifests/results.json"
RACE_LENGTHS_HOURS = (6, 8, 10, 24)
REQUEST_GAP_S = 0.5

REQUIRED_HEADERS = {
    "race": ("LAP_TIME", "ELAPSED", "CLASS"),
    "practice": ("LAP_TIME", "ELAPSED", "CLASS"),
    "weather": ("TIME_UTC_SECONDS",),
    "classification": (),
}

_RACE = re.compile(r"/\d+_FIA WEC/(?P<session>\d{12}_Race)/\d+_Hour (?P<hours>\d+)/(?P<kind>23_Analysis|26_Weather|03_Classification)_Race_Hour (?P=hours)(?P<final>_Final)?\.CSV$")
_PRACTICE = re.compile(r"/\d+_FIA WEC/\d{12}_Free Practice (?P<number>\d)(?: - (?P<cls>[A-Z0-9]+))?/23_Analysis_Free Practice \d(?: - [A-Z0-9]+)?\.CSV$")
_KINDS = {"23_Analysis": "race", "26_Weather": "weather", "03_Classification": "classification"}


def _get(url: str) -> bytes:
    request = urllib.request.Request(urllib.parse.quote(url, safe=":/"), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()
    return gzip.decompress(body) if body[:2] == b"\x1f\x8b" else body


def event_key(season: str, event_folder: str) -> str:
    """'2026' and '05_CIRCUIT OF THE AMERICAS' to '2026_CIRCUIT_OF_THE_AMERICAS'."""
    name = event_folder.split("_", 1)[1]
    return f"{season}_{re.sub(r'[ -]+', '_', name)}"


def season_urls(season: str) -> list[str]:
    """Every file the public results listing shows for a season."""
    seasons = json.loads(_get(RESULTS_INDEX))["seasons"]
    manifest = json.loads(_get(FILES_ROOT + next(s["manifestUrl"] for s in seasons if s["name"] == season)))
    urls = []

    def walk(nodes: list[dict]) -> None:
        for node in nodes:
            if node.get("url") and not node.get("children"):
                urls.append(node["url"])
            walk(node.get("children") or [])

    walk(manifest["folders"])
    return urls


def plan_files(urls: list[str], season: str) -> list[dict]:
    """Pick the WEC race and free-practice files from a season's listing, using the last hour of each race.

    A race whose last hour isn't a full race length is still in progress, so it's left out.
    """
    planned = []
    races: dict[str, list[tuple[re.Match, str]]] = {}
    for url in urls:
        event = url.split("/")[3]
        race = _RACE.search(url)
        if race:
            races.setdefault(event, []).append((race, url))
        practice = _PRACTICE.search(url)
        if practice:
            suffix = f"_{practice['cls']}" if practice["cls"] else ""
            key = event_key(season, event)
            planned.append({"kind": "practice", "file": f"{key}__FP{practice['number']}{suffix}.CSV", "url": url, "event_key": key})
    for event, matches in races.items():
        hours = max(int(match["hours"]) for match, _ in matches)
        if hours not in RACE_LENGTHS_HOURS:
            continue
        key = event_key(season, event)
        last_hour = [(match, url) for match, url in matches if int(match["hours"]) == hours]
        for match, url in sorted(last_hour, key=lambda item: item[0]["final"] is not None, reverse=True):
            kind = _KINDS[match["kind"]]
            if not any(p["kind"] == kind and p["event_key"] == key for p in planned):
                planned.append({"kind": kind, "file": f"{key}.CSV", "url": url, "event_key": key, "hours": hours, "season": season})
    return planned


def missing_files(planned: list[dict], target_dirs: dict[str, Path] = TARGET_DIRS) -> list[dict]:
    return [item for item in planned if not (target_dirs[item["kind"]] / item["file"]).exists()]


def check_csv(content: bytes, kind: str, url: str) -> None:
    """Refuse anything that isn't the expected CSV. The site answers a dead link with a web page and status 200."""
    head = content[:2000].decode("utf-8-sig", "replace").lstrip()
    if head[:1] == "<" or ";" not in head.split("\n")[0]:
        raise ValueError(f"not a CSV: {url}")
    missing = [column for column in REQUIRED_HEADERS[kind] if column not in head.split("\n")[0]]
    if missing:
        raise ValueError(f"{url} has no {missing}")


def _append_manifest(directory: Path, record: dict) -> None:
    path = directory / "_manifest.json"
    records = json.loads(path.read_text()) if path.exists() else []
    path.write_text(json.dumps(records + [record], indent=2))


def fetch(item: dict, target_dirs: dict[str, Path] = TARGET_DIRS) -> dict:
    """Download one planned file, check it and record where it came from."""
    url = FILES_ROOT + item["url"]
    content = _get(url)
    check_csv(content, item["kind"], url)
    directory = target_dirs[item["kind"]]
    directory.mkdir(parents=True, exist_ok=True)
    (directory / item["file"]).write_bytes(content)
    record = {
        "file": item["file"],
        "url": url,
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "downloaded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if item["kind"] == "race":
        record = {"season": item["season"], "event": url.split("/")[6], "hours": item["hours"], **record}
    _append_manifest(directory, record)
    return record


def download_new(seasons: tuple[str, ...] = CORPUS_SEASONS, dry_run: bool = False) -> list[dict]:
    """Fetch whatever the listing has that isn't on disk yet. Races come first, since the others depend on them."""
    planned = [item for season in seasons for item in plan_files(season_urls(season), season)]
    new = sorted(missing_files(planned), key=lambda item: (item["kind"] != "race", item["file"]))
    if not dry_run:
        for item in new:
            fetch(item)
            time.sleep(REQUEST_GAP_S)
    return new
