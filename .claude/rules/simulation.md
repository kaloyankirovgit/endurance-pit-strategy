# Rule: simulation

How the race simulator is built, constrained and validated.

---

## Architecture: five separable parts

Keep these separate. Collapsing them is what makes a simulator impossible to debug or validate:

1. **State transition model** — deterministic, given inputs and noise draws.
2. **Stochastic sampling** — where randomness enters, and only here.
3. **Strategy action** — the decision at each decision point.
4. **Optimisation / search** — chooses among strategies.
5. **Evaluation** — scores outcomes.

Monte Carlo is the *uncertainty-evaluation framework*, not the optimisation algorithm. Conflating them produces a system where you cannot tell whether a strategy looked good because it is good or because of the seed.

---

## Deterministic core first

Build the deterministic lap-discrete simulator before adding any randomness.

- With all noise sources set to zero, the simulator must be exactly reproducible.
- Every stochastic component is added one at a time, with its effect on output distributions inspected before the next is added.
- All randomness flows from explicitly seeded generators. A seeded run reproduces byte-for-byte.
- Pass generators explicitly rather than relying on global random state.

The order in `Strategy.md` §20.2 is deliberate:

```
deterministic baseline → stochastic simulator → exhaustive strategy search
→ optimisation → validation → RL as a stretch goal
```

RL on an unvalidated simulator learns the simulator's mistakes and makes them impossible to attribute.

---

## Explicit state

The simulator state is a declared structure, not a set of loose variables. A minimal target-car state:

```
race_time              lap_number            stint_lap
driver                 current_class         race_position
tyre_state             fuel_state            estimated_gap_ahead
traffic_exposure_state flag_state            laps_since_pit
remaining_race_time
```

Rules:

- Every field carries its provenance category. `tyre_state` and `fuel_state` are **ASSUMED** unless a source identifying them is found (DECISIONS D-005).
- The wider field may use a simplified state. Say which simplifications were made and what they cost — an approximation of the rest of the field directly affects the traffic model, which is the point of a multi-class simulator.
- No hidden state. If a transition depends on a quantity, that quantity is in the state.

---

## Invariants

Invariants are tested, not assumed. At minimum:

- Race time never decreases.
- Lap number never decreases for a car, except where the source explicitly resets.
- Simulated fuel never becomes negative.
- Tyre age cannot decrease without a pit event that resets it.
- A pit event produces a logically valid state transition — entry, stationary, exit, in that order.
- No car occupies two positions at the same event timestamp.
- **If traffic is disabled, traffic loss is exactly zero.**
- **If pit loss is set to zero, pitting helps only through the modelled tyre and fuel benefit.**
- Total race distance and elapsed time remain mutually consistent.
- Every strategy the simulator executes passed the feasibility layer first.

The last two "if X then Y" invariants are the most valuable: they verify that a component does what it claims and nothing else. A traffic model that still affects lap times when disabled is leaking through another path.

---

## Parameter uncertainty versus outcome randomness

Two distinct sources, composed differently:

- **Parameter uncertainty** — the traffic effect, pit-loss distribution and stint degradation are *estimated*, with intervals. The simulator should propagate that uncertainty, not run at a point estimate.
- **Outcome randomness** — even with perfectly known parameters, races vary.

Running many races at a point estimate captures the second and ignores the first, which understates total uncertainty. Where practical, draw parameters from their posterior or bootstrap distribution per simulated race.

---

## Stochastic events

Add a stochastic process only when it can be **estimated from data or sensibly parameterised**. Realism is not a justification on its own; every added process is another thing that can be wrong and another parameter to defend.

| Process | Requirement before inclusion |
|---|---|
| Lap-time noise | Estimated from clean-lap residual distributions |
| Traffic exposure | From the Layer 2 model, with its uncertainty |
| Pit duration variation | Empirical or fitted distribution from real pit events |
| FCY / safety car | See below |
| Incident / retirement | Only if enough events exist to estimate a rate |
| Mechanical failure | Almost certainly not estimable; omit or treat as a clearly labelled sensitivity scenario |

### FCY and safety car

Not "a fixed number of slow laps". Represent at minimum:

- probability of occurrence (a hazard process over race time, not a fixed count);
- duration distribution;
- effect on lap times and on gaps between cars;
- effect on pit-stop opportunity — which is the whole strategic point.

Informed by historical WEC flag data, once flag vocabulary is established in Layer 1. Field compression and ghost-car approaches exist in the literature; keep the implementation as simple as the project's resolution justifies.

---

## Validation against historical races

**A simulator cannot validate itself.** Validation is against independently observed historical data, in five levels:

1. **Component** — do simulated lap-time, stint-length, pit-loss and FCY distributions match observed ones?
2. **Replay** — feed the simulator only information available at each point of a historical race; compare predicted against observed state.
3. **Strategy evaluation** — generate strategies from past information only; evaluate on held-out races.
4. **Hindsight benchmark** — construct a hindsight-constrained optimum under the *same* simulator assumptions. This separates optimiser quality from model quality.
5. **Actual-strategy comparison** — descriptive context only.

Level 5 needs care. The team's real strategy is **not ground truth**: teams act on live tyre condition, fuel state, driver feedback, telemetry and engineering judgement that the public data does not contain. Disagreeing with the real pit lap does not mean the model is wrong; agreeing does not mean it found the optimum.

Ask instead: did the recommendation fall inside a plausible real-world strategic window, and are the differences explained by identifiable assumptions?

**Never claim a counterfactual outcome** — "the team would have won by 14 seconds" — without compelling external validation. The simulator does not have it.

---

## Calibration targets

The simulator is useful when it broadly reproduces:

- lap-time distributions, by class
- stint-length distributions
- pit-stop timing distributions
- pit-loss distributions
- FCY / safety-car count and duration
- relative class pace

Compare distributions, not means. Two distributions with the same mean and different tails produce very different strategy recommendations, because strategy is largely about tails.

---

## Action space

Keep it minimal initially:

```
CONTINUE
PIT
PIT + DRIVER CHANGE
PIT + TYRE / FUEL ACTION    (only where rules and data support the distinction)
```

Do not invent stop types — "fuel-only", "tyres-only", "full service" — that the source data cannot identify. Expand the taxonomy only when a documented source makes the distinction defensible.

---

## Feasibility before simulation

The simulator never executes a strategy that has not passed the regulation-feasibility layer (DECISIONS D-006). Legality is a separate, auditable concern, and burying it inside simulator conditionals makes it impossible to cite.
