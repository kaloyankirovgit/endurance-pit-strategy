<!-- SYNTHETIC eval case. The numbers are invented and are not results from this project. -->

# Does changing a struggling driver help?

**Data:** 21 races.

**Selection:** the 120 stints where the car's mean residual over the last five laps before the stop was in the slowest 10% of that race.

**Result:** in the stint after the driver change, residuals improved by 0.65 s per lap on average, 95% interval [0.48, 0.81] from a bootstrap that resamples races.

**Conclusion:** swapping out a struggling driver recovers 0.65 s per lap, and the strategy tool should recommend an early driver change when a stint goes badly.
