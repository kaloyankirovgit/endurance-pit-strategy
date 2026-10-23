<!-- SYNTHETIC eval case. The numbers are invented and are not results from this project. -->

# A pace-deficit feature for in-race pit decisions

**Goal:** a feature the strategy tool can use at lap *t* to decide whether a car's pace has dropped off enough to pit.

**Feature:** pace deficit = current lap time minus the car's clean-pace baseline, where the baseline is the median of all the car's clean laps in that race.

**Validation:** the feature model was fitted on 2024 races, tuned on 2025, and tested once on the 2026 races. Using the pace deficit, next-lap time is predicted with MAE 0.31 s, against 0.48 s for a no-change baseline (bootstrap over test races, 95% CI on the improvement [0.11, 0.22] s).

**Conclusion:** the pace deficit is ready to drive pit decisions in the live tool.
