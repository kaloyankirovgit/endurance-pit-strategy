<!-- SYNTHETIC eval case. The numbers are invented and are not results from this project. -->

# Checking the rebuilt race order against the official classification

**Data:** 21 races, 833 cars. The official end-of-race classification files come from the same timing provider.

**Method:** each car's laps and elapsed time at its last crossing, ranked by laps and then time, compared car by car with the official classification.

**Result:** lap counts match for 830 of 833 cars. Among the 654 classified cars whose finishing time and laps match exactly, the order matches in all 654. The 51 cars that differ all have a longer official time: 48 by a whole number of seconds and 3 by one or two laps, which fits post-race penalties.

**Limitations:** the penalties are inferred from the pattern and haven't been checked against the stewards' decisions. Only the final order is checked. The classification comes from the same timing system, so this tests the rebuild logic, not the timing itself.
