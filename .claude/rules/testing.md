# Rule: testing

Testing is not about whether functions execute. It is about whether the analytical claims hold.

---

## What must be tested before it feeds a model

Any deterministic transformation gets a test **before** its output becomes an input to something else. Specifically, before the traffic model runs:

- time parsing and conversion to seconds
- lap-number sequence handling
- race-order sorting
- gap calculation
- stint boundary detection
- pit-event identification
- in-lap and out-lap classification

An error here propagates silently into every downstream result, and it will be indistinguishable from a modelling failure. A misparsed lap time produces a plausible-looking traffic effect that is entirely an artefact.

---

## Unit tests

Deterministic functions, on synthetic fixtures with known answers. Construct cases deliberately rather than sampling real data:

- cars on the same lap
- a car a lap down
- cars crossing the line at different times
- a pit stop producing a large gap
- an FCY changing lap-time patterns
- a driver change mid-stint
- a car retiring mid-race
- a lap with missing sector times
- the first and last lap of a race
- a duplicate timing row

Edge cases first. The interesting bugs are at boundaries — the first lap of a stint, the transition into a pit sequence, a car that does not finish.

---

## Property and invariant tests

Properties that must hold for any input, not just the chosen examples. For the simulator:

- race time never decreases
- lap number never decreases for a car except at an explicit source reset
- simulated fuel never becomes negative
- tyre age cannot decrease without a pit event
- a pit event produces a valid transition sequence
- no car occupies two positions at the same timestamp
- **traffic disabled ⇒ traffic loss exactly zero**
- **pit loss zero ⇒ pitting helps only via modelled tyre and fuel benefit**
- every executed strategy passed the feasibility layer

The two "disable X, observe Y" properties are the most useful tests in the suite: they confirm a component's effect flows only through the intended path. A traffic model that still moves lap times when switched off is leaking.

For reconstruction:

- ordering is a total order — no ties without a documented tie-break
- gaps are non-negative where defined
- stint laps within a stint are contiguous from 1

Property-based testing (Hypothesis) is worth considering for the simulator once its state model stabilises.

---

## Data-quality tests

Quality checks live in `tests/`, not in notebook cells. Per ingested file:

- schema conformance — names, dtypes, nullability
- missingness within expected bounds
- no unexpected duplicates
- values within plausible ranges
- monotonicity where expected
- categorical vocabulary matches the known set
- referential integrity between tables

**Verify each check actually fires.** A quality check that has never failed has not been tested — run it against a deliberately corrupted fixture and confirm it raises.

---

## Statistical tests

Tests of the statistical machinery itself, distinct from the analysis:

- fitted distributions behave sensibly at their boundaries
- confidence intervals achieve approximately their nominal coverage in synthetic experiments where the truth is known
- a known effect injected into synthetic data is recovered by the estimator
- model outputs are stable under small input perturbations
- bootstrap procedures resample at the cluster level, verified by a test that would fail under row-level resampling

The synthetic-recovery test is worth the effort: generate data with a known traffic effect, run the full pipeline, and confirm the estimated effect matches. It validates the estimator, and it is the only way to know whether a null result on real data means "no effect" or "broken estimator".

---

## Regression tests

When a bug is found, write the failing test first, then fix it. When a result is established, pin it — if a refactor changes a reported number, that must fail loudly rather than quietly changing the finding.

---

## Reproducibility as a test target

- Seeded runs produce identical output. Test it.
- The pipeline produces the same tables from the same raw files. Test it on a fixture.
- No test depends on wall-clock time, filesystem ordering or network access.

---

## Integration test

A small synthetic fixture runs the whole chain:

```
parse → clean → features → simulate → optimise
```

without the real dataset. This is what makes CI possible, and it catches interface breakage that unit tests miss.

---

## Fixtures

- Committed fixtures are **synthetic only**, in `tests/fixtures/`, labelled as synthetic in a header.
- Small enough to read by eye. A fixture whose expected output you cannot verify manually is not doing its job.
- A real timing extract must never be placed under `tests/` to evade the data rules.
- If a fixture grows too large to commit, commit a generator script instead.

---

## CI

CI runs without the proprietary dataset — that is a hard constraint, not a convenience. It should run:

- the unit and property test suite
- data-contract tests against fixtures
- import and build checks
- a simulator smoke test once one exists
- formatting and linting if adopted

CI that requires the real data would never run, and a test suite that never runs is documentation.
