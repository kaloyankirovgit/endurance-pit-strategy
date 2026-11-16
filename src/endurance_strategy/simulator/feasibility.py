"""Legality before simulation (D-006). Every rule cites where it comes from, so a refusal can be explained.

The checks use the deterministic expectation of laps and stint times. They're a planning check, as a
strategist's would be, and the simulator then handles what the race does to the plan.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from endurance_strategy.simulator.types import CarParams, Strategy


@dataclass(frozen=True)
class Rule:
    rule_id: str
    description: str
    source: str
    category: str   # where the number comes from: REGULATION or ASSUMED


RULES = (
    Rule("R1", "No stint longer than the class's energy limit in laps",
         "ASSUMED from the longest caution-free stints run in 2024 and 2025 (E-022 Part A). BoP stint energy isn't collected", "ASSUMED"),
    Rule("R2", "LMGT3: each Bronze and Silver driver drives at least 1h45 (6h), 2h20 (8h) or 2h55 (10h)",
         "WEC Sporting Regulations 2025 v1.1, article 13.2.3, page 42", "REGULATION"),
    Rule("R3", "Every driver drives at least 45 minutes, or the crew scores no points",
         "WEC Sporting Regulations 2025 v1.1, article 13.2.3, page 42", "REGULATION"),
    Rule("R4", "A strategy names a driver for every stint, has at least one stint, and the car has a positive pace",
         "Internal consistency", "ASSUMED"),
    Rule("R5", "No stop while a full-course yellow is out: the stop waits for the pits to open",
         "WEC Sporting Regulations 2025 v1.1, article 12.2.1, page 39 (the Race Director may close the pit entry; "
         "only an emergency stop is allowed then, which isn't modelled). That FCY closes the pits is from race reporting "
         "(Autosport, Fuji 2025), not a clause read in the regulations", "ASSUMED"),
)

MIN_DRIVE_S = {6: 6300.0, 8: 8400.0, 10: 10500.0}   # 1h45, 2h20, 2h55 (R2)
POINTS_DRIVE_S = 2700.0                            # 45 minutes (R3)


@dataclass(frozen=True)
class FeasibilityResult:
    ok: bool
    violations: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def expected_laps(params: CarParams, stops: int) -> float:
    lap = params.base_pace_s + params.expected_traffic_s
    return (params.duration_s - stops * params.pit_loss_s[False]) / lap


def check_strategy(params: CarParams, strategy: Strategy, driver_categories: dict | None = None) -> FeasibilityResult:
    """`driver_categories` maps driver to "Platinum", "Gold", "Silver" or "Bronze". Without it R2 isn't checked."""
    violations, warnings = [], []
    if not strategy.stint_laps or len(strategy.drivers) != len(strategy.stint_laps) or params.base_pace_s <= 0:
        return FeasibilityResult(False, ["R4: a driver is needed for every stint and the pace must be positive"])
    planned = list(strategy.stint_laps[:-1])
    final = expected_laps(params, strategy.stops) - sum(planned)
    for i, laps in enumerate(planned + [final]):
        if laps > params.max_stint_laps:
            violations.append(f"R1: stint {i + 1} plans {laps:.0f} laps, over the limit of {params.max_stint_laps}")
        if laps < 1:
            violations.append(f"R1: stint {i + 1} has {laps:.0f} laps")
    lap_s = params.base_pace_s + params.expected_traffic_s
    drive_s: dict = {}
    for driver, laps in zip(strategy.drivers, planned + [max(final, 0.0)]):
        drive_s[driver] = drive_s.get(driver, 0.0) + laps * lap_s
    hours = round(params.duration_s / 3600)
    if params.car_class == "LMGT3" and driver_categories:
        minimum = MIN_DRIVE_S.get(hours)
        for driver, category in driver_categories.items():
            if minimum and category in ("Bronze", "Silver") and drive_s.get(driver, 0.0) < minimum:
                violations.append(f"R2: {driver} ({category}) drives {drive_s.get(driver, 0.0) / 60:.0f} min, under {minimum / 60:.0f}")
    for driver, seconds in drive_s.items():
        if seconds < POINTS_DRIVE_S:
            warnings.append(f"R3: {driver} drives {seconds / 60:.0f} min, under 45")
    return FeasibilityResult(not violations, violations, warnings)


def even_strategy(params: CarParams, stops: int, drivers: tuple) -> object:
    """Equal planned stints for `stops` stops, with drivers rotating in the order given."""
    total = expected_laps(params, stops)
    length = int(round(total / (stops + 1)))
    stints = tuple([length] * stops + [max(1, int(round(total - length * stops)))])
    return Strategy(stint_laps=stints, drivers=tuple(drivers[i % len(drivers)] for i in range(stops + 1)))
