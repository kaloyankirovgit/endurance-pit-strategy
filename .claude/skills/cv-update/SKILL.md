---
name: cv-update
description: Assess whether a completed milestone is CV-worthy and draft an evidence-backed bullet. Use at the end of a layer or when a capability becomes genuinely demonstrable.
---

# CV update

Convert completed work into a defensible CV claim — or establish that it is not one yet.

The test throughout: **could this be defended for five minutes against someone who knows the domain?**

---

## 1. What was actually completed?

Not what was attempted or nearly finished. What runs, what was measured, what was validated.

## 2. Evidence check

For the candidate claim:

- **Code / file** — paths in this repository. No path, no claim.
- **Metric** — measured in this repository by code that runs. Not estimated, not from a paper, not plausible.
- **Validation** — how it was checked, which races were held out, what the uncertainty is.
- **Reproducible** — could someone else re-run it from the repository?

Any gap means the status is **IN PROGRESS**, not VERIFIED.

## 3. Status

| Status | Meaning |
|---|---|
| TARGET | Not achieved. Never on a CV. |
| IN PROGRESS | Started. Still not a CV claim. |
| VERIFIED | Reproducible evidence exists in this repository. |
| PORTFOLIO READY | Verified, and a reader can find the evidence themselves. |

Only VERIFIED and PORTFOLIO READY may appear on a CV. Status can move backwards if a result stops replicating.

## 4. Draft the bullet

Shape: **action + specific scale + method + measured outcome**.

- State the unit the number is measured over — "across 8 races and 62 cars", not "across 48,000 laps".
- Keep every qualifier that protects the claim. If it reads less impressively, that is the correct version.
- Prefer the honest limitation. The strongest bullet on the existing CV is the one reporting a null result; it signals judgement that an accuracy figure does not.

Check against the forbidden-claims table in `docs/cv/CV_EVIDENCE.md`.

## 5. Interview check

For each bullet, can the underlying reasoning be explained **without Claude**? The list in `Strategy.md` §35 is the standard — why DuckDB, why exact overtake detection is impossible, why random lap splits leak, why 100k laps is not 100k observations.

If a component cannot be explained, it is a learning target before it is a CV claim.

## 6. Skills ledger

Update `docs/cv/SKILLS_LEDGER.md`. A skill reaches VERIFIED only at depth **Chosen** — used for a real problem, with a defensible reason for choosing it over the alternative.

## 7. Record

- `docs/cv/CV_EVIDENCE.md` — the entry with evidence and status
- `docs/cv/PROJECT_BULLETS.md` — the drafted bullet
- `docs/cv/SKILLS_LEDGER.md` — skills touched
- `docs/PROJECT_STATE.md` — the CV status section

---

## Watch for

**Inflation by degrees.** "Built a pipeline" becoming "built a production data platform"; "estimated" becoming "measured"; "a Streamlit app" becoming "deployed to production".

**Claiming the plan.** The WEC entry on the end-goal CV draft is a TARGET. It stays one until the layers behind it exist.

**Listing tools rather than capabilities.** Importing a library is not a skill. Choosing it over the alternative for a reason you can state is.
