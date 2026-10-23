<!-- SYNTHETIC eval case. The numbers are invented and are not results from this project. -->

# Pit loss at Le Mans for the simulator

**Data:** 412 normal pit stops (garage visits excluded) across the 2024, 2025 and 2026 races.

**Summary:** mean 71.2 s, SD 18.4 s. The distribution is strongly right-skewed: median 64.8 s, 95th percentile 109 s, with a long tail from slow stops behind other cars in the pit lane.

**Decision:** the simulator will draw each Le Mans pit loss from Normal(71.2, 18.4).
