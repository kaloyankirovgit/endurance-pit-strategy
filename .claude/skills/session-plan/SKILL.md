---
name: session-plan
description: Open every working session with a plan table (what, who does it, platform, what Kaloyan learns) and close it by updating the CV sections file. Use at the start of any session that will produce work, before writing code.
---

# Session plan

**Run this at the start of every working session, before any code is written.** Kaloyan asked for this format explicitly: it is not optional and it is not a summary written afterwards.

---

## 1. Open with the plan table

Produce a table with exactly these five columns:

| # | What we're doing | Who | Platform | What you'll learn |
|---|---|---|---|---|

Rules for each column:

- **What we're doing:** one concrete, checkable task per row. Not "work on the parser" but "write the loader that handles the leading-space headers and `m:ss.SSS` durations".
- **Who:** `Kaloyan`, `Claude`, or `Both`. This is governed by `CLAUDE.md` §3: Kaloyan implements the analytical core (order reconstruction, gap calculation, traffic logic, statistical features, simulator state, Monte Carlo structure, optimisation formulation, retrieval strategy). Claude writes boilerplate (config, parsers, SQL, Docker, CI, test scaffolding, plotting, logging, API/Streamlit). `Both` means paired review, not vague ownership.
- **Platform:** name the actual software: VS Code, Terminal, Jupyter, DB Browser for SQLite, a browser. Do not write "local machine". If a step needs a tool that is not installed, say so in the row.
- **What you'll learn:** the transferable concept, not the keystrokes. "Why `groupby().diff()` beats a loop for monotonicity checks" is a lesson; "run the script" is not. If a row teaches nothing, question whether Kaloyan should be doing it rather than Claude.

Keep the table to **4–7 rows.** A session with fifteen rows is not a session, it is a roadmap.

Below the table, state:

- the **time estimate** and whether it fits the time Kaloyan has;
- what is **explicitly deferred** to a later session, so scope creep is visible;
- any **decision** the session will need from him.

## 2. Check the plan against the clock

If Kaloyan names a duration, the plan must fit it with room to spare. Reviewing his implementation always takes longer than writing it. When in doubt, cut a row and say which one was cut.

## 3. Work the plan

Follow the teaching sequence in `CLAUDE.md` §3 for anything Kaloyan owns: state the problem, say why it matters, explain the idea, give structure or hints, let him implement, review, name the error, explain the correction, then fix.

Do not silently take over a row assigned to Kaloyan because it would be faster.

## 4. Close by updating the CV sections file

At the end of the session, update `docs/cv/CV_SECTIONS.md`:

- move anything newly evidenced into the correct tier;
- update the paste-ready LaTeX blocks so they reflect what is now true;
- update the skills lines with any tool genuinely used for a real problem.

Then update `docs/PROJECT_STATE.md`, and add to `DECISIONS.md` or `EXPERIMENT_LOG.md` if the session produced a decision or a finding.

**The CV file is a draft.** Keep tiers roughly accurate, but do not police authorship (Kaloyan vs Claude) or block lines for work not yet done: see `CLAUDE.md` §9. Run wording through the `humanizer` skill.

---

## Watch for

**A plan table that is all `Claude`.** Kaloyan is using this project to build ability. If a session has no row he owns, either the session is pure boilerplate (say so) or the split is wrong.

**Learning columns that describe the task.** "Learn how to check monotonicity" restates the row. "Learn why lap-level checks must be done within car, because elapsed time is only monotonic per car" is the actual lesson.

**Plans that assume tools he does not have.** Verified available: **VS Code** (at `~/Downloads/Packages/Visual Studio Code.app`, with the Python, Pylance, Jupyter, rainbow-csv and parquet-viewer extensions), Terminal, Spyder 6, Anaconda/Jupyter, DB Browser for SQLite, Chrome. **Not installed:** `uv`, DuckDB CLI.

VS Code is the default editor for this project. `rainbow-csv` colourises the semicolon-delimited timing files and `parquet-viewer` opens Parquet output directly: use both rather than writing throwaway inspection scripts.
