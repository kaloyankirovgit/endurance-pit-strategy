from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
WEC_DIR = RAW_DIR / "wec"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"

FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"


def race_path(event_key: str) -> Path:
    path = WEC_DIR / f"{event_key}.CSV"
    if not path.exists():
        raise FileNotFoundError(
            f"no race file for {event_key!r} at {path}. "
            "Raw timing data is not committed, see data/README.md."
        )
    return path
