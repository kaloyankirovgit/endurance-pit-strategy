---
name: statistical-review
description: Adversarially review a statistical result before it is reported or put on a CV - clustering, leakage, confounding, identifiability, uncertainty, validation design. Use after fitting a model or before writing up a finding.
---

# Statistical review

Try to break the result. The purpose is to find the weakness before an interviewer does.

Run this **before** a finding is written up, and always before it becomes a CV claim.

---

## 1. What is being claimed?

Write the claim in one sentence. Then ask whether the sentence says more than the evidence supports — an association stated as an effect, an effect stated as a cause, a simulated outcome stated as a prediction.

## 2. Unit of analysis

- What is one observation, and does it match the question?
- Sample size in **every** relevant unit: races, circuits, cars, drivers, stints, pit events, laps, sectors.
- Is any row count being used as though it were independent sample size?

## 3. Clustering

- What is the nesting structure — laps in stints in cars in races in circuits?
- Does the estimator account for it, or does it treat rows as independent?
- Does the interval resample **clusters** or rows?
- How many independent units genuinely inform this estimate? Often far fewer than it appears.

## 4. Leakage

- Could any feature use information unavailable at the decision time?
- Was a baseline (clean pace, driver average) computed over data that includes the laps being evaluated?
- Were tuning and evaluation done on the same races?
- Is the split race-level, or does it place laps from the same race on both sides?

## 5. Confounding

- What else could produce this pattern? Stint age, fuel load, driver error, flag state, weather, deliberate tyre or fuel saving, mechanical issues, in-laps and out-laps.
- Which of these are controlled, and which remain?
- Is any uncontrolled confounder correlated with the treatment? Tyre-saving is the dangerous one: it is invisible in timing data and correlated with exactly the strategic context being modelled.

## 6. Identifiability

- Can the data distinguish these parameters at all, or would the fit produce arbitrary numbers?
- Fuel and tyre both act through stint age — is anything claiming to separate them?
- What would change if a parameter were fixed at a different plausible value?

## 7. Uncertainty

- Is uncertainty reported at all?
- Does the interval account for clustering, or is it too narrow?
- Are parameter uncertainty and outcome randomness distinguished?
- Is a difference being presented as meaningful when its interval spans zero?

## 8. Specification sensitivity

Re-run under reasonable alternatives:

- different exclusion criteria (in-laps, out-laps, FCY laps)
- different thresholds and matching tolerances
- different baseline pace specification
- different seeds
- per-circuit and per-class-pair fits
- leave-one-race-out

Does the conclusion survive? If it flips, **that is the finding**.

## 9. Category check

Every quantity labelled OBSERVED / RECONSTRUCTED / INFERRED / ASSUMED / SIMULATED. Does the write-up preserve the labels, or has an inferred quantity become an observed one in the prose? Check variable names and plot titles, not just the text — that is where conversions start.

## 10. The null alternative

Could this result be produced by noise alone? What would the analysis have shown if there were genuinely no effect? If the answer is "something that looks similar", the result is not established.

---

## Output

- the claim, restated as narrowly as the evidence supports
- weaknesses found, ordered by severity
- what would need to be done to strengthen or retire the claim
- a verdict: supported / supported with stated limitations / not supported / not identifiable

Log it in `docs/EXPERIMENT_LOG.md`.

**A finding of "not identifiable" is a successful review, not a failure.** It is also a legitimate project result and a defensible CV claim in its own right.
