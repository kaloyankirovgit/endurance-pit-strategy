<!-- SYNTHETIC eval case. The numbers are invented and are not results from this project. -->

# Choosing the traffic-exposure threshold

**Data:** 2025 validation races only, 7 races, Hypercar.

**Method:** a lap counts as exposed if the car crosses the line within a threshold of a slower car. We tried thresholds of 0.5, 1.0, 1.5, 2.0, 2.5 and 3.0 s and compared matched residuals each time.

**Result:** only at 1.5 s is the difference significant: 0.22 s, 95% interval [0.03, 0.41] from a bootstrap over races. At the other thresholds the intervals include zero.

**Conclusion:** we adopt 1.5 s as the definition of exposure and report a traffic effect of 0.22 s per exposed lap.
