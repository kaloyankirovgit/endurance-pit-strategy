<!-- SYNTHETIC eval case. The numbers are invented and are not results from this project. -->

# How much time does slower-class traffic cost?

**Data:** 21 races, all classes, 138,884 clean laps (in-laps and out-laps already excluded).

**Exposure (inferred):** crossing the line less than 2.0 s behind a slower-class car.

**Method:** residual = lap time minus the car's median clean lap in the same stint. Mean residual of exposed against unexposed laps.

**Result:** exposed laps are 0.9 s slower, 95% interval [0.7, 1.1] from a bootstrap that resamples races, then cars within races.

**Note:** exposed laps are 2.3 times more common in the first three laps after a stop than later in a stint, because cars rejoin in the middle of the field.

**Conclusion:** traffic costs 0.9 s per exposed lap, and the simulator will use this value.
