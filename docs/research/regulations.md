# Regulations

The 2024, 2025 and 2026 sporting regulations are collected and chunked (D-018). Retrieval over them is measured in E-009.

## Why they matter here

A pit strategy is only useful if it's legal. Before the simulator runs anything, a separate check takes the strategy and returns whether it's allowed and which rules it breaks (D-006). That's also where the LLM layer earns its place later, by pointing to the exact rule that ruled a strategy out, with a citation.

## Ground rules

- **Nothing from memory.** Every rule comes from an actual document, with the revision and page number. That goes for my memory and an LLM's.
- **Rules have dates.** They change by season and sometimes mid-season through event bulletins. A rule with no source document and start date can't be used.

The PDFs stay local and aren't committed. This file keeps the record of what was downloaded and where it came from.

## Documents

| ID | Title | Season | Revision | Published | Effective | SHA-256 (first 16) | Retrieved |
|---|---|---|---|---|---|---|---|
| WEC-SR-2024 | 2024 FIA WEC Sporting Regulations | 2024 | clean v1.9 | 19.10.2023 | 01.01.2024 | `959ce8ff1900da4c` | 2026-10-23 |
| WEC-SR-2025 | 2025 FIA WEC Sporting Regulations | 2025 | clean v1.1 | 18.10.2024 | 01.01.2025 | `3575b64462370d21` | 2026-10-23 |
| WEC-SR-2026 | 2026 FIA WEC Sporting Regulations | 2026 | clean v1.2 (WMSC) | 16.10.2025 | 01.01.2026 | `98ff1454127b5c6d` | 2026-10-23 |

The WEC site links to the FIA, which hosts the PDFs: <https://www.fia.com/regulation/category/118>. The 2026 file is listed there. The 2024 and 2025 files are still hosted under `fia.com/sites/default/files/` and were found by search. Full URLs and hashes are in `io/regulations.py` and the local manifest. The FIA's `robots.txt` allows these paths and asks for 10 seconds between requests, which the downloader respects.

**What the versions don't cover:**

- **Mid-season revisions.** Each file is the revision hosted now, so it's the latest one for that season. If a clause changed mid-season, an early-season race ran under a wording this corpus doesn't hold.
- **Other documents.** WEC Committee decisions, event bulletins, the Le Mans supplementary regulations and Balance of Performance tables aren't collected yet.
- **Bilingual layout.** Only the English column is kept. Tables come out scrambled, the tyre-allocation table in 6.5.4 for example.

What to collect: the sporting regulations first. After that, any technical or balance-of-performance documents that limit what happens in a stop, plus the event bulletins that change the standard rules.

## Questions to put to the regulations

These are things to look up, not rules I'm claiming exist.

- Are there minimum or maximum driving times per driver?
- What has to happen during a driver change?
- What limits the work done in a pit stop, including refuelling?
- How many tyre sets are allowed, and when can they be changed?
- Are there mandatory stops for any class?
- What's allowed under full-course yellow and safety car, especially pit entry?
- Which event bulletins changed the rules at a given race?

The pit-entry question under a caution matters more than it looks. The whole value of pitting under a yellow depends on what's permitted at that moment, and getting it wrong would bias every strategy the optimiser picks.

## How the rules will be stored

One row per rule, with the season, the event (or "all"), the class, the constrained quantity and its value, the dates it applies between, and the document, section and page it came from.
