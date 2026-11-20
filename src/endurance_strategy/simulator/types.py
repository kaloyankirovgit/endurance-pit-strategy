"""The simulator's inputs: car parameters and a strategy. Shared by the engine and the feasibility check."""
from __future__ import annotations

from dataclasses import dataclass, field

CAUTIONS = ("SF", "FCY")  # safety car (pits open) and full-course yellow (pits closed)
GREEN = "GF"


class InfeasibleStrategy(ValueError):
    """Raised when a strategy reaches the simulator without passing the feasibility check (D-006)."""


@dataclass(frozen=True)
class CarParams:
    """One car class at one circuit. Built by `calibrate.car_params` from 2024 and 2025 data."""
    circuit: str
    car_class: str
    duration_s: float                       # OBSERVED race length
    base_pace_s: float                      # INFERRED: a green lap at stint age 3 with no traffic
    max_stint_laps: int                     # ASSUMED: energy limit proxy from observed stints (BoP stint energy isn't collected)
    pit_loss_s: dict = field(default_factory=lambda: {False: 0.0, True: 0.0})   # INFERRED medians, by driver change
    sc_pit_loss_factor: float = 0.3         # ASSUMED: share of the green loss when stopping under a safety car
    age_slope_s: float = 0.0                # ASSUMED (D-032): flat by default, with a sensitivity range
    age_limit_laps: int = 999               # D-032: the slope isn't extrapolated past the supported stint age
    warm_up_s: float = 0.0                  # INFERRED: extra time on stint lap 2 (E-021)
    traffic_rate: float = 0.0               # INFERRED: mean other-class cars met per lap
    traffic_s_per_car: float = 0.0          # INFERRED association (D-004, E-021)
    traffic_on: bool = True
    caution_lap_ratio: dict = field(default_factory=lambda: {"SF": 1.0, "FCY": 1.0})  # INFERRED
    restart_lap_ratio: float = 1.0          # INFERRED (E-022 amendment): the green lap after a caution, part neutralised
    incident_rate: float = 0.0              # INFERRED (E-022 amendment): share of green laps with a mistake, slow zone or local yellow
    incident_extra_s: float = 0.0           # INFERRED (E-022 amendment): mean extra time on such a lap
    caution_progress: dict | None = None    # INFERRED (E-023): share of green speed kept under each caution type. When set,
                                            # cautions are priced by time (a lap straddling an episode is partly slowed) and
                                            # the per-lap caution and restart ratios aren't used
    restart_extra_s: float = 0.0            # INFERRED (E-023): extra time on the lap that starts within one green lap after
                                            # an episode ends (the field restarting), used only with caution_progress

    @property
    def expected_traffic_s(self) -> float:
        return self.traffic_rate * self.traffic_s_per_car if self.traffic_on else 0.0


@dataclass(frozen=True)
class Strategy:
    """Planned laps per stint (counted as `stint_lap`: out-lap 1, in-lap last) and the driver of each stint.

    The last stint runs to the flag, so its planned length is only used by the feasibility check.
    """
    stint_laps: tuple
    drivers: tuple

    @property
    def stops(self) -> int:
        return len(self.stint_laps) - 1
