<!-- SYNTHETIC eval case. The numbers are invented and are not results from this project. -->

# Gradient-boosted pace model

**Data:** 138,884 clean laps from 21 races (2024 to 2026).

**Features:** class, car, driver, stint lap, track temperature, air temperature, race hour.

**Split:** a random 80/20 split of laps, stratified by class.

**Result:** test RMSE 0.62 s, against 1.40 s for a per-car median baseline. Performance is similar across classes.

**Conclusion:** the model generalises to new races and can supply lap times for the race simulator.
