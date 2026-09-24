# Data sources

Where the data comes from and what I'm allowed to do with it.

## FIA WEC timing (Al Kamel Systems) — the main source

<https://fiawec.alkamelsystems.com/>

Public, no login, and an empty `robots.txt`. The archive covers 121 events from 2011 to 2026. Pages are picked with two URL parameters:

```
https://fiawec.alkamelsystems.com/?season={NN_YYYY}&evvent={NN_EVENT NAME}
```

Each event page links straight to its files. The ones that matter:

| File | What's in it |
|---|---|
| `23_Analysis_*` | Lap-by-lap timing, 29 columns. The core dataset. The highest-hour file covers the whole race. |
| `23_AnalysisEnduranceWithSections_*` | The same, plus 15 timing points per lap. Only Le Mans (2025 and 2026) and COTA 2026. |
| `26_Weather_*` | Weather every minute, for every race from 2023 on. Downloaded for all 21 corpus races with hashes (`io/download.py`). |
| `03_Classification_*` | Hourly classification snapshots. |

Lap charts and pit summaries also exist, but only as PDFs.

### Using it

The site says the data is owned by Al Kamel Systems and can't be distributed without their permission. Downloading it to analyse locally is one thing, republishing it is another. So:

- nothing from the source goes in this repo — raw files or anything derived from them;
- if there's ever a live demo, it shows model outputs, never source rows.

Anyone who wants to reproduce this downloads the files themselves — the README says how.

### A gotcha when downloading

The event selector sometimes serves the **wrong event** — ask for Imola 2026 and occasionally you get Fuji 2026. If you trust it blindly, one race's laps end up labelled as another's, and no later check would notice. My downloader confirms the page's selected season and event match the request, and that the file path has the right event folder, retrying until it does.

### The modern era, audited

I downloaded and parsed every WEC race from 2023 to 2026. All 28 files have **the same 29-column schema**, so one parser covers the lot.

| Season | Event | Hours | Laps | Cars | Pit stops | Classes |
|---|---|---:|---:|---:|---:|---|
| 2023 | Sebring | 8 | 7,417 | 36 | 310 | HC, LMP2, GTE Am |
| 2023 | Algarve | 6 | 7,596 | 37 | 233 | HC, LMP2, GTE Am |
| 2023 | Spa | 6 | 4,817 | 37 | 227 | HC, LMP2, GTE Am |
| 2023 | Le Mans | 24 | 15,030 | 62 | 1,396 | HC, LMP2, GTE Am, Innovative |
| 2023 | Monza | 6 | 6,390 | 36 | 258 | HC, LMP2, GTE Am |
| 2023 | Fuji | 6 | 7,774 | 36 | 225 | HC, LMP2, GTE Am |
| 2023 | Bahrain | 8 | 8,455 | 36 | 313 | HC, LMP2, GTE Am |
| 2024 | Losail | 10 | 11,211 | 37 | 421 | HC, LMGT3 |
| 2024 | Imola | 6 | 6,825 | 37 | 302 | HC, LMGT3 |
| 2024 | Spa | 6 | 4,410 | 37 | 209 | HC, LMGT3 |
| 2024 | Le Mans | 24 | 15,593 | 62 | 1,548 | HC, LMP2, LMGT3 |
| 2024 | São Paulo | 6 | 7,796 | 36 | 219 | HC, LMGT3 |
| 2024 | COTA | 6 | 5,675 | 36 | 221 | HC, LMGT3 |
| 2024 | Fuji | 6 | 7,042 | 36 | 251 | HC, LMGT3 |
| 2024 | Bahrain | 8 | 7,486 | 36 | 288 | HC, LMGT3 |
| 2025 | Losail | 10 | 9,696 | 36 | 373 | HC, LMGT3 |
| 2025 | Imola | 6 | 7,044 | 36 | 244 | HC, LMGT3 |
| 2025 | Spa | 6 | 4,630 | 36 | 261 | HC, LMGT3 |
| 2025 | Le Mans | 24 | 20,182 | 62 | 1,902 | HC, LMP2, LMGT3 |
| 2025 | São Paulo | 6 | 7,930 | 36 | 210 | HC, LMGT3 |
| 2025 | COTA | 6 | 3,964 | 36 | 182 | HC, LMGT3 |
| 2025 | Fuji | 6 | 6,683 | 36 | 220 | HC, LMGT3 |
| 2025 | Bahrain | 8 | 7,795 | 36 | 288 | HC, LMGT3 |
| 2026 | Imola | 6 | 6,758 | 35 | 221 | HC, LMGT3 |
| 2026 | Spa | 6 | 4,831 | 35 | 207 | HC, LMGT3 |
| 2026 | Le Mans | 24 | 20,163 | 62 | 1,849 | HC, LMP2, LMGT3 |
| 2026 | São Paulo | 6 | 8,015 | 35 | 188 | HC, LMGT3 |
| 2026 | COTA | 6 | 5,530 | 35 | 209 | HC, LMGT3 |

"Pit stops" here means in-laps (`B` laps). Fuji 2026 hadn't run at the time of the audit. Support races in the archive (Porsche Carrera Cup and the like) are left out.

The Le Mans 2025 class split (21 Hypercar, 17 LMP2, 24 LMGT3) matches the published entry list exactly, which is a good sign the car and class fields can be trusted.

### It's mostly a two-class championship

LMP2 left the full championship after 2023 and now only races at Le Mans. And 2023's GT class was LMGTE Am, a different set of cars from LMGT3. So:

| Structure | Races | Circuits | Laps |
|---|---:|---:|---:|
| Hypercar + LMGT3 | 18 | 8 | 123,321 |
| Hypercar + LMP2 + LMGTE Am (2023) | 6 | 6 | 42,449 |
| Hypercar + LMP2 + LMGT3 (Le Mans) | 4 | 1 | 70,968 |

This is why the main corpus is 2024 to 2026 (D-010), and why I call it two-class outside Le Mans.

## Other sources, not yet looked at

| Source | Could be useful for | Worry |
|---|---|---|
| Kaggle WEC lap data, 2012–2022 | A longer history | A re-upload doesn't carry the original's status, and it spans big regulation changes |
| IMSA timing data | Testing whether the traffic results transfer to another series | Only worth it once there's a WEC result to test |
| Le Mans Ultimate (sim) | Sensitivity tests, since it exposes fuel and tyre state | It's a game, so anything from it is simulated, not measured |
| iRacing | Similar to LMU | API hassle, and not on the critical path |

## Regulations

The FIA WEC sporting regulations, from <https://www.fiawec.com/en/page/regulations/18>. They're tracked separately in [`regulations.md`](regulations.md), since the version and date matter as much as the wording.

## What I won't use

Results aggregator sites (unclear provenance, inconsistent timing definitions) and anything an LLM "remembers" about the rules. Every regulation claim has to come from an actual document with a page number.
