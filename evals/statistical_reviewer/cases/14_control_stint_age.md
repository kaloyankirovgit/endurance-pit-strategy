<!-- SYNTHETIC eval case. The numbers are invented and are not results from this project. -->

# Combined stint-age effect on pace

**Data:** 21 races, 10,577 stints, clean laps only.

**Identification:** fuel burn and tyre wear both act through laps since the stop, so timing data can't separate them. Only the combined stint-age effect is estimated, and any split is treated as an assumption.

**Model:** mixed model of lap time on stint lap, with random intercepts for race and car. Fitted on 2024, checked on 2025.

**Result:** 0.042 s slower per stint lap in 2024, 95% interval [0.031, 0.055] from a bootstrap that resamples races. On 2025 the slope is 0.039 s, inside that interval.

**Limitations:** deliberate tyre saving flattens the slope and can't be seen in the data. The effect is assumed linear over the stint lengths observed, which run up to 45 laps.
