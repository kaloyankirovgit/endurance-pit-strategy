<!-- SYNTHETIC eval case. The numbers are invented and are not results from this project. -->

# Traffic exposure and lap time, Hypercar, 2024 fit races

**Data:** 8 races from 2024, 23 Hypercar entries, 41,612 clean laps (green flag, no in-laps or out-laps, no rain).

**Exposure (inferred):** a lap counts as exposed if the car crossed the line less than 2.0 s behind an LMGT3 car. This is inferred from the road gap, not an observed overtake.

**Method:** residual = lap time minus the median of the car's previous five clean laps in the same stint. I compared the mean residual of exposed and unexposed laps within the same car and stint.

**Result:** exposed laps are 0.41 s slower on average, 95% CI [0.39, 0.43], from 2,000 bootstrap resamples of laps.

**Limitations:** this is an association. Deliberate tyre saving isn't observed and isn't controlled.
