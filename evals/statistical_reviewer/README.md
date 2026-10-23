# Eval: the statistical-reviewer agent

Does the `statistical-reviewer` agent (`.claude/agents/statistical-reviewer.md`) catch the flaws it's meant to catch, and does it leave sound work alone?

## The cases

`cases/` holds 16 short write-ups in the style of this project. **All of them are synthetic. The numbers are invented and are not results from this project.** Each file starts with a comment saying so, and the runner strips it before the reviewer sees the text.

- **12 cases have one planted flaw each**, covering the agent's attack list: clustered data treated as independent, leakage, a random lap split, confounding, a fuel and tyre split that can't be identified, an interval that spans zero, inferred exposure described as measured overtakes, threshold shopping, regression to the mean, a normal fit to skewed data, and laps counted as sample size.
- **4 cases are controls** with no planted flaw. One of them describes the race-order check from E-007.

`labels.json` gives each case its planted category and the categories that count as catching it. Some flaws fit more than one category (a row-level bootstrap is a dependence problem and an uncertainty problem), so a case can accept more than one.

## How a run works

`python scripts/run_reviewer_eval.py` calls the agent headless with `claude -p`:

- from an empty temporary folder, so the project's `CLAUDE.md` and memory don't leak in;
- with the agent's own instructions as the system prompt and no tools;
- with a fixed JSON schema for the answer: weaknesses (category, severity, mechanism) and a verdict.

## Scoring

The scoring is an exact match against the labels, with no LLM judge (`src/endurance_strategy/evals/reviewer.py`):

- **Flawed case caught:** the reviewer reports a weakness in an accepted category at `major` or `critical`.
- **False alarm on a control:** a `critical` weakness, or a verdict of `not supported` or `not identifiable`.

Each case runs 3 times, because the same prompt can give different answers. The results are reported per run, and per case by majority.

## Results

First run, 2026-10-20, `claude-opus-5-5`, 3 runs per case (full write-up in E-008 of `docs/EXPERIMENT_LOG.md`):

- **Planted flaws:** 11 of 12 caught at major or critical by majority. In all 36 flawed runs the planted category came up at some severity.
- **The miss:** the case that calls inferred exposures "measured overtakes". The reviewer noticed it every time but rated it minor.
- **Controls:** no false alarm by majority on any of the 4. Two single runs raised one, and both critiques turned out to be fair. One found a real flaw in the project's own race-order check.

Raw runs and summaries are in `results/`.

## What it can't show

- The same model family wrote the cases and does the reviewing, so the cases may be easier for it than flaws written by someone else.
- 12 flawed cases and 4 controls is a small set. A rate over 12 cases is a rough number, and is reported with its count.
- Picking the category from a fixed list is stricter than a free-text review. A reviewer that explains a flaw well but files it under an unexpected category is scored as a miss.
