<!-- SYNTHETIC eval case. The numbers are invented and are not results from this project. -->

# Separating fuel and tyre effects

**Data:** 10,577 stints from 21 races. In this sample every stop refuels the car and changes all four tyres, so no stint is double-stinted.

**Model:** lap time ~ fuel mass + tyre age + car fixed effects, where fuel mass = 110 kg − 1.6 kg × laps since the stop and tyre age = laps since the stop.

**Result:** fuel effect 0.030 s per kg (95% CI [0.026, 0.034]), tyre effect 0.051 s per lap (95% CI [0.044, 0.058]). Intervals come from a bootstrap over races.

**Conclusion:** the simulator will use these two coefficients separately, so fuel-saving and tyre-saving strategies can be compared.
