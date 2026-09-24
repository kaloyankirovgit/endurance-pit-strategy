# Rule: statistics

The statistical standards this project holds itself to. These are the questions a competent reviewer will ask, written down so they are answered before they are asked.

---

## Unit of analysis

**Decide what the observation is before choosing an estimator.** The question determines the unit:

| Question | Natural unit |
|---|---|
| How does lap time vary within a stint? | Lap, nested in stint |
| How costly is a traffic encounter? | Candidate exposure window |
| How long is a pit stop? | Pit event |
| How does a driver compare to their teammate? | Driver-race |
| Does the model generalise? | Race, and ideally circuit |

Report sample size in **every** relevant unit: races, circuits, cars, drivers, stints, pit events, laps, sectors. Not just rows.

---

## Clustered observations: the central issue

Laps are not independent. They are nested within stints, within cars, within races, within circuits. Adjacent laps are temporally correlated. A driver who is fast on lap 40 is fast on lap 41 for reasons that have nothing to do with the effect being estimated.

Consequences that must be respected:

- **Row count is not sample size.** 100,000 laps from 8 races carries far less information about a race-level effect than the number suggests. The effective sample size for a between-race effect is closer to 8.
- **Standard errors computed as though rows were independent are too narrow**, often by a large factor. An interval built that way will exclude the truth far more often than its nominal coverage suggests.
- Use hierarchical / mixed-effects models with random intercepts for driver, car and race, or cluster-robust standard errors, or a bootstrap that **resamples clusters rather than rows**.
- State explicitly which level of clustering an interval accounts for.

The published figure of ~99,928 laps in the Sasikumar et al. F1 pit-stop study is a **scale reference, not a sample-size justification**. Do not cite it as evidence that a lap count confers statistical validity.

The question is never "do we have enough laps?" It is:

> Do we have enough independent races, stints and pit events to estimate what we care about with useful uncertainty, and does the model generalise to unseen races?

---

## Leakage

A feature used for a decision at race time may only use information available at that moment.

Leakage patterns specific to this project:

- Using whole-race average pace to characterise a driver when simulating a lap-40 decision.
- Using future lap times to estimate current pace or current tyre state.
- Using finishing position as an input feature.
- Using future pit stops to infer current traffic.
- Computing a "clean pace" baseline over the full race and applying it to laps inside that race.
- Tuning strategy parameters on the same races used to report final performance.

Build explicit "information available at time *t*" logic into feature construction and the simulator. If a feature cannot be computed from the past alone, it cannot be used for a decision.

**Random lap-row train/test splits are prohibited for any generalisation claim.** They place laps from the same race, same car and same stint on both sides of the split, which leaks race-specific structure and inflates apparent performance and apparent sample size simultaneously.

---

## Validation design

- Default split is **race-level**, and where sample size permits, circuit-aware or temporal.
- Options: temporal holdout (train on earlier seasons, test on later); leave-one-race-out; leave-one-circuit-out for transfer.
- Separate the four roles explicitly, and state in every report which races each component saw:
  1. model fitting
  2. parameter tuning / model selection
  3. validation / calibration
  4. final demonstration
- **Never tune and evaluate on the same races.** This is the direct carry-over from the BSE dissertation: parameter optimisation and policy evaluation are different activities with different data.

---

## Confounding

A lap-time residual has many possible causes. Before attributing one to traffic, control for what is observable: circuit, car, driver, stint lap, flag state, in-lap and out-lap status, race phase, and where possible weather.

Then state which confounders remain uncontrolled, next to the result. Deliberate tyre or fuel saving is the hardest: it is a driver decision that is invisible in timing data and correlated with strategic context, which is exactly the thing being modelled.

Matched comparison (same driver, same car, same circuit, similar stint lap, same flag state, similar pre-lap pace) reduces confounding without pretending treatment was randomised. It is a useful first analysis precisely because it is transparent about what it does and does not achieve.

---

## Identifiability

Before fitting, ask whether the data can distinguish the parameters at all.

The standing example: **fuel burn and tyre degradation both act monotonically through stint age.** With timing data alone, no amount of model sophistication separates them. Fitting a model with both terms will produce two numbers, and those two numbers will be arbitrary.

When a quantity is not identified:

1. Say so.
2. Model the aggregate that *is* identified (a stint-age effect).
3. Label the unidentified components ASSUMED.
4. Run sensitivity analysis across their plausible range.

A non-identifiability finding is a legitimate project result. It is also the kind of finding that demonstrates real statistical judgement.

---

## Uncertainty

Report uncertainty with every estimate. Point estimates alone are not results.

- Bootstrap confidence intervals, **resampling at the cluster level** (races or cars), not the row level.
- Empirical distributions and quantiles in preference to a mean where the distribution is skewed: pit losses certainly will be.
- Distinguish *parameter* uncertainty (how well the effect is estimated) from *outcome* randomness (how variable a race is). They compose differently and answer different questions.
- Prediction intervals for simulator output, not just expected values.

A small numerical advantage without an interval is not a finding. In strategy comparison, "Strategy A is 4 seconds faster on average, with a 95% interval of [−38, +46]" is the honest statement, and it is a more useful one for a race engineer than the point estimate alone.

---

## Sensitivity analysis

Part of the result, not an appendix. For any headline claim, vary:

- exclusion criteria (in-laps, out-laps, FCY laps, missing sectors);
- thresholds (what counts as a candidate exposure, matching tolerances);
- baseline pace model specification;
- random seeds;
- ASSUMED parameter values across their plausible range.

If the conclusion flips under a reasonable alternative specification, **that instability is the finding** and must be reported as such.

---

## Testing choice

Choose a test because of the data-generating structure and the question, not because it is familiar. With repeated measures on the same driver, car and race, standard tests assuming independence do not apply: use hierarchical or repeated-measures methods.

Do not report only accuracy or R². For a strategy project, distributional calibration and decision quality matter more than fit statistics: a model with mediocre R² that produces well-calibrated distributions is more useful to an optimiser than a high-R² model that is overconfident.

---

## Honest interpretation

- State what the result does **not** establish, in the same place it is stated.
- Give the alternative explanations that remain open.
- Do not describe an association as an effect, or an effect as a cause.
- Do not describe a simulated outcome as a prediction of reality.
- If the honest version of a sentence is less impressive, use the honest version.
