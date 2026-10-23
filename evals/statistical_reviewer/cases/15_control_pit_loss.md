<!-- SYNTHETIC eval case. The numbers are invented and are not results from this project. -->

# Pit-loss distributions for the simulator

**Data:** 9,746 normal pit stops (garage visits excluded) from 21 races at 9 circuits.

**Method:** pit loss is taken per stop and kept by circuit. The simulator samples from the empirical distribution for that circuit, rather than from a fitted parametric shape, because the distributions are right-skewed.

**Uncertainty:** quantiles are reported with intervals from a bootstrap that resamples whole races within each circuit. Most circuits have only 2 or 3 races, so the upper tail is the least certain part.

**Limitations:** each stop's pit loss includes any queueing behind other cars in the pit lane, which the data can't separate out. Circuits with no history can't be simulated with this method.
