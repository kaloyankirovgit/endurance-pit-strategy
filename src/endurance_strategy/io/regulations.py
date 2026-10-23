from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone

from endurance_strategy.paths import RAW_DIR

REGULATIONS_DIR = RAW_DIR / "regulations"
CRAWL_DELAY_S = 10

DOCUMENTS = [
    {
        "document_id": "WEC-SR-2024",
        "title": "2024 FIA World Endurance Championship Sporting Regulations",
        "season": "2024",
        "revision": "clean v1.9",
        "url": "https://www.fia.com/sites/default/files/2024_fia_world_endurance_championship_sporting_regulations_clean-v1.9_0.pdf",
    },
    {
        "document_id": "WEC-SR-2025",
        "title": "2025 FIA World Endurance Championship Sporting Regulations",
        "season": "2025",
        "revision": "clean v1.1",
        "url": "https://www.fia.com/sites/default/files/2025_fia_world_endurance_championship_sporting_regulations_clean_v1.1.pdf",
    },
    {
        "document_id": "WEC-SR-2026",
        "title": "2026 FIA World Endurance Championship Sporting Regulations",
        "season": "2026",
        "revision": "clean v1.2 (WMSC)",
        "url": "https://www.fia.com/system/files/documents/2026_fia_world_endurance_championship_sporting_regulations_clean_v1.2wmsc.pdf",
    },
]


def download_regulations() -> list[dict]:
    """Fetch each regulation PDF, respecting the FIA site's crawl delay, and record provenance."""
    REGULATIONS_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for index, document in enumerate(DOCUMENTS):
        if index:
            time.sleep(CRAWL_DELAY_S)
        request = urllib.request.Request(document["url"], headers={"User-Agent": "endurance-strategy research download"})
        with urllib.request.urlopen(request, timeout=120) as response:
            content = response.read()
        target = REGULATIONS_DIR / f"{document['document_id']}.pdf"
        target.write_bytes(content)
        records.append({
            **document,
            "file": target.name,
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "downloaded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
    (REGULATIONS_DIR / "_manifest.json").write_text(json.dumps(records, indent=2))
    return records
