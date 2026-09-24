# Regulations

Nothing collected yet. This is the plan for when I do.

## Why they matter here

A pit strategy is only useful if it's legal. Before the simulator runs anything, a separate check takes the strategy and returns whether it's allowed and which rules it breaks (D-006). That's also where the LLM layer earns its place later — pointing to the exact rule that ruled a strategy out, with a citation.

## Ground rules

- **Nothing from memory.** Every rule comes from an actual document, with the revision and page number. That goes for my memory and an LLM's.
- **Rules have dates.** They change by season and sometimes mid-season through event bulletins. A rule with no source document and start date can't be used.

The PDFs stay local and aren't committed. This file keeps the record of what was downloaded and where it came from.

## Documents

| ID | Title | Season | Revision | Effective | Source | Retrieved |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — |

Source: <https://www.fiawec.com/en/page/regulations/18>

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
