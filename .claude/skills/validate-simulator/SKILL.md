---
name: validate-simulator
description: Validate the race simulator against historical data and its own invariants - component distributions, replay, strategy evaluation, hindsight benchmark. Use after changing simulator components or before reporting any strategy result.
---

# Validate simulator

A simulator cannot validate itself. Validation is against independently observed historical data, plus invariants that must hold for any input.

---

## 1. Invariants first

Cheap, and they catch the errors that would otherwise be misread as modelling failures:

- race time never decreases
- lap number never decreases for a car except at an explicit source reset
- fuel never negative
- tyre age never decreases without a pit event
- pit events produce valid transition sequences (entry → stationary → exit)
- no car in two positions at one timestamp
- **traffic disabled ⇒ traffic loss exactly zero**
- **pit loss zero ⇒ pitting helps only through modelled tyre and fuel benefit**
- every executed strategy passed the feasibility layer
- seeded runs reproduce exactly

The two "disable X" invariants matter most: they confirm a component acts only through its intended path.

## 2. Component validation

Compare simulated against observed **distributions**, not means — two distributions with equal means and different tails give very different strategy recommendations:

- lap times, by class
- stint lengths
- pit-stop timing
- pit losses
- FCY / safety-car count and duration
- relative class pace

Report where they diverge and what that implies for strategy conclusions.

## 3. Replay validation

Feed the simulator only information available at each point of a historical race. Compare predicted against observed state, simulated against actual pace, simulated against actual pit losses.

Check for leakage: is any parameter fitted on the race being replayed?

## 4. Strategy evaluation

Generate strategies using only past or currently available information; evaluate on held-out races. State which races each model component has seen.

## 5. Hindsight benchmark

Construct a hindsight-constrained optimum under the **same** simulator assumptions. This separates optimiser quality from model quality — if the optimiser cannot find a good strategy even with hindsight, the problem is the search, not the model.

## 6. Actual-strategy comparison — descriptive only

The team's real strategy is **not ground truth**. They had live tyre and fuel state, driver feedback and telemetry the model does not.

Ask only: did the recommendation fall inside a plausible real-world window, and are the differences attributable to identifiable assumptions (traffic, FCY, degradation)?

**Never claim a counterfactual outcome.** Not "the team would have gained 14 seconds".

## 7. Uncertainty propagation

- Are parameters drawn from their estimated distributions, or held at point estimates? Point estimates understate total uncertainty.
- Are enough Monte Carlo repetitions run for the reported quantity to be stable? Check convergence rather than picking a round number.
- Are results reported with intervals?

---

## Output

- invariant results (pass/fail per invariant)
- distribution comparisons, with figures
- divergences found and their implications
- an explicit statement of what the simulator is and is not validated for

Log in `docs/EXPERIMENT_LOG.md`; record any resulting decisions in `docs/DECISIONS.md`.

**State the scope of validity.** "Validated against 2025 Le Mans lap-time and pit-loss distributions" is defensible. "Validated" alone is not.
