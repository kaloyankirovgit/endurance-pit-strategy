<!-- SYNTHETIC eval case. The numbers are invented and are not results from this project. -->

# Lap residual under inferred slower-class exposure, Hypercar, 2024 fit races

**Data:** 8 races from 2024, 23 Hypercar entries, 31,204 clean laps.

**Exposure (inferred):** crossing the line less than 2.0 s behind an LMGT3 car. This is inferred from the road gap and is not an observed overtake.

**Method:** residual = lap time minus the median of the car's previous five clean laps in the same stint, so only past laps are used. Each exposed lap is matched to an unexposed lap of the same car and driver, within two laps of stint age, under the same flag state.

**Result:** matched exposed laps are 0.31 s slower, 95% interval [0.12, 0.52], from a bootstrap that resamples races, then cars within races. The effect stays between 0.27 and 0.34 s for thresholds from 1.5 to 2.5 s.

**Limitations:** this is an association between inferred exposure and lap time, from 8 races. Deliberate tyre saving and drivers lifting off aren't observed and may contribute. The 2025 validation races haven't been used yet.
