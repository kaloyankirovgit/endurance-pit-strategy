"""The simulator core: the race state, one lap's transition, and the run of a race.

One car with a simplified field: traffic is an expected cost per lap, not cars on track, so there are no
positions, gaps or undercuts (D-034). Flag convention, shared with the replay: a lap runs at the pace of
the flag at its start, and a stop is decided at pit entry, the end of the in-lap. So a stop can't be made
while a full-course yellow (FCY) has the pits closed, and a stop under a safety car (SC) is charged at the
SC rate.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from endurance_strategy.simulator.feasibility import check_strategy
from endurance_strategy.simulator.types import CAUTIONS, GREEN, CarParams, InfeasibleStrategy, Strategy  # noqa: F401  (re-exported)

MAX_STOPS_DRAWN = 64


@dataclass(frozen=True)
class State:
    """Everything a lap's transition depends on. No hidden state (simulation.md)."""
    race_time_s: float = 0.0
    lap_number: int = 0
    stint_number: int = 1
    stint_lap: int = 0
    green_laps_in_stint: int = 0  # the energy limit counts green laps; caution laps use far less (D-034)
    plan_index: int = 0           # which planned stint the car is on
    driver: str = ""
    pitting_now: bool = False     # the last lap was an in-lap, so this lap is an out-lap
    last_stop_driver_change: bool = False
    last_stop_flag: str = GREEN   # the flag at pit entry of the last stop
    previous_flag: str = GREEN    # the flag the last lap ran under, so a restart lap can be priced
    stops: int = 0
    extra_stops: int = 0          # forced by the energy limit
    deferred_laps: int = 0        # laps a wanted stop waited for the pits to open


@dataclass(frozen=True)
class Draws:
    """The random inputs for one lap. Zero in the deterministic simulator."""
    lap_noise_s: float = 0.0
    pit_loss_scale: float = 1.0   # a sampled stop as a multiple of the median, so zero pit loss stays zero
    incident_s: float | None = None  # a sampled incident (0 or its extra time); None uses the expected value


@dataclass(frozen=True)
class Randomness:
    """Where randomness enters, and only here. Each source can be switched off on its own."""
    lap_residuals_s: np.ndarray | None = None          # INFERRED: within-stint residuals of clean laps
    pit_loss_samples_s: dict | None = None             # INFERRED: eligible stops, by driver change
    caution_rate_per_green_s: dict | None = None       # INFERRED: episodes per second of green running, by type
    caution_durations_s: dict | None = None            # INFERRED: observed episode lengths, by type
    caution_rate_shape: dict | None = None             # INFERRED (E-023): gamma shape of each race's own rate, by type;
                                                       # None or a missing type keeps the rate constant across races
    incident_extra_samples_s: np.ndarray | None = None # INFERRED: extra time on observed incident laps
    age_slope_draw: tuple | None = None                # ASSUMED: (mean, sd) to draw the stint-age slope once per race


@dataclass(frozen=True)
class RaceDraws:
    """Every random number for one race, drawn up front from separate streams, so two strategies run on
    the same seed see the same cautions, the same noise on lap n and the same draw for stop k."""
    cautions: list
    lap_noise_s: np.ndarray
    pit_loss_scale: dict
    age_slope_s: float | None
    incident_s: np.ndarray | None = None   # per lap number: 0, or the extra time of an incident on that lap

    @classmethod
    def none(cls) -> "RaceDraws":
        return cls([], np.zeros(0), {False: np.ones(0), True: np.ones(0)}, None, None)


def draw_cautions(randomness: Randomness, duration_s: float, rng: np.random.Generator) -> list[tuple[float, float, str]]:
    """Caution episodes (start, end, type): starts follow a Poisson process in green time, so the gaps
    between episodes are exponential and the rate is per second of green running.

    With `caution_rate_shape` (E-023), each race first draws its own rate for that type: the calibrated rate
    times a gamma multiplier with mean 1 and shape k. Counts per race are then overdispersed (variance
    mu + mu^2/k), so some races have no safety car and some have many, as observed."""
    rates = {kind: rate for kind, rate in (randomness.caution_rate_per_green_s or {}).items() if rate > 0}
    shapes = randomness.caution_rate_shape or {}
    for kind in sorted(rates):
        shape = shapes.get(kind)
        if shape:
            rates[kind] *= float(rng.gamma(shape, 1.0 / shape))
    total = sum(rates.values())
    if total <= 0:
        return []
    kinds, weights = list(rates), np.array(list(rates.values())) / total
    episodes, t = [], 0.0
    while True:
        t += rng.exponential(1 / total)
        if t >= duration_s:
            return episodes
        kind = kinds[rng.choice(len(kinds), p=weights)]
        length = float(rng.choice(randomness.caution_durations_s[kind]))
        episodes.append((t, t + length, kind))
        t += length


def draw_race(randomness: Randomness | None, params: CarParams, seed: int | None) -> RaceDraws:
    if randomness is None:
        return RaceDraws.none()
    streams = [np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(5)]
    max_laps = int(params.duration_s / (params.base_pace_s * 0.8)) + 10
    noise = (streams[1].choice(randomness.lap_residuals_s, max_laps) if randomness.lap_residuals_s is not None
             else np.zeros(max_laps))
    scale = {False: np.ones(MAX_STOPS_DRAWN), True: np.ones(MAX_STOPS_DRAWN)}
    if randomness.pit_loss_samples_s is not None:
        for key, samples in randomness.pit_loss_samples_s.items():
            scale[key] = streams[2].choice(samples, MAX_STOPS_DRAWN) / np.median(samples)
    slope = None
    if randomness.age_slope_draw is not None:
        mean, sd = randomness.age_slope_draw
        slope = float(streams[3].normal(mean, sd))
    cautions = draw_cautions(randomness, params.duration_s, streams[0]) if randomness.caution_rate_per_green_s else []
    incidents = None
    if randomness.incident_extra_samples_s is not None:
        hit = streams[4].random(max_laps) < params.incident_rate
        incidents = np.where(hit, streams[4].choice(randomness.incident_extra_samples_s, max_laps), 0.0)
    return RaceDraws(cautions, noise, scale, slope, incidents)


def time_to_cover(work_s: float, start_s: float, episodes: list, progress: dict) -> float:
    """Seconds needed, from `start_s`, to cover `work_s` seconds of green running when each second inside a
    caution episode covers only `progress[kind]` of a green second (E-023). Episodes don't overlap."""
    t, left = start_s, work_s
    for start, end, kind in sorted(episodes):
        if end <= t:
            continue
        if start > t:
            if left <= start - t:
                return t + left - start_s
            left -= start - t
            t = start
        rate = progress[kind]
        if rate > 0 and rate * (end - t) >= left:
            return t + left / rate - start_s
        left -= max(rate, 0.0) * (end - t)
        t = end
    return t + left - start_s


def flag_at(time_s: float, episodes: list[tuple[float, float, str]]) -> str:
    for start, end, kind in episodes:
        if start <= time_s < end:
            return kind
    return GREEN


def lap_time(state: State, params: CarParams, flag: str, draws: Draws, slope_s: float, start_s: float = 0.0,
             episodes: list | None = None) -> tuple[float, dict]:
    """Deterministic given its inputs. Returns the lap time and its parts, so each component can be checked.
    The replay calls this too (E-022 Part B, E-023).

    Two ways to price a caution. Per lap (E-022): a lap started under a caution runs at the class's caution-lap
    ratio, and the green lap after one at the restart ratio. By time (E-023, when `params.caution_progress` is
    set): the car's full green lap (base, age, warm-up, traffic, noise) is covered at full speed outside the
    episodes and at the caution's share of that speed inside them, so a lap straddling a caution's start or
    end is only partly slowed. The share is fitted in the same unit, the car's full clean lap. The green parts
    keep their values under a caution and the `caution` part is the extra time the slowing adds."""
    stint_lap = state.stint_lap + 1
    parts = {"base": params.base_pace_s, "age": 0.0, "warm_up": 0.0, "traffic": 0.0, "pit": 0.0, "noise": 0.0, "caution": 0.0,
             "incident": 0.0}
    if params.caution_progress is not None:
        parts["age"] = slope_s * (min(max(stint_lap, 3), params.age_limit_laps) - 3)
        parts["warm_up"] = params.warm_up_s if stint_lap == 2 else 0.0
        parts["traffic"] = params.expected_traffic_s
        parts["noise"] = draws.lap_noise_s
        work = sum(parts.values())   # the car's full green lap, the unit the caution share is fitted in
        parts["caution"] = time_to_cover(work, start_s, episodes or [], params.caution_progress) - work
        if flag not in CAUTIONS:     # like a pit loss, an incident is time on top, not slowed by a caution
            parts["incident"] = params.incident_rate * params.incident_extra_s if draws.incident_s is None else draws.incident_s
            if any(start_s - params.base_pace_s < end <= start_s for _, end, _ in episodes or []):
                parts["caution"] += params.restart_extra_s   # the restart lap, fitted the same way (calibrate.caution_progress)
    elif flag in CAUTIONS:
        parts["caution"] = params.base_pace_s * (params.caution_lap_ratio[flag] - 1.0)
    elif state.previous_flag in CAUTIONS:   # a restart lap: green at the line, partly run under the caution
        parts["caution"] = params.base_pace_s * (params.restart_lap_ratio - 1.0)
    else:
        parts["incident"] = params.incident_rate * params.incident_extra_s if draws.incident_s is None else draws.incident_s
        parts["age"] = slope_s * (min(max(stint_lap, 3), params.age_limit_laps) - 3)
        parts["warm_up"] = params.warm_up_s if stint_lap == 2 else 0.0
        parts["traffic"] = params.expected_traffic_s
        parts["noise"] = draws.lap_noise_s
    if state.pitting_now:
        loss = params.pit_loss_s[state.last_stop_driver_change] * draws.pit_loss_scale
        parts["pit"] = loss * (params.sc_pit_loss_factor if state.last_stop_flag == "SF" else 1.0)
    return sum(parts.values()), parts


def decide(state: State, strategy: Strategy, params: CarParams, entry_flag: str, lap_is_green: bool) -> tuple[bool, bool, bool]:
    """The action at pit entry, the end of the lap just run: (stop, forced by the energy limit, deferred)."""
    final = state.plan_index >= len(strategy.stint_laps) - 1
    planned = not final and state.stint_lap + 1 >= strategy.stint_laps[state.plan_index]
    forced = state.green_laps_in_stint + int(lap_is_green) >= params.max_stint_laps
    want = planned or forced
    if want and entry_flag == "FCY":  # the pits are closed under a full-course yellow (feasibility R5)
        return False, False, True
    return want, forced and not planned, False


def step(state: State, strategy: Strategy, params: CarParams, flag: str, entry_flag: str, draws: Draws,
         slope_s: float, episodes: list | None = None) -> tuple[State, dict]:
    """One lap: the state transition. Pure: the same inputs always give the same output."""
    seconds, parts = lap_time(state, params, flag, draws, slope_s, state.race_time_s, episodes)
    green = flag not in CAUTIONS
    stop, forced, deferred = decide(state, strategy, params, entry_flag, green)
    stint_lap = state.stint_lap + 1
    record = {"lap": state.lap_number + 1, "stint": state.stint_number, "stint_lap": stint_lap, "driver": state.driver,
              "flag": flag, "entry_flag": entry_flag, "lap_time_s": seconds, "in_lap": stop, "out_lap": state.pitting_now,
              "forced_stop": forced, "green_laps_in_stint": state.green_laps_in_stint + int(green),
              "race_time_s": state.race_time_s + seconds, **{f"{k}_s": v for k, v in parts.items()}}
    new = replace(state, race_time_s=state.race_time_s + seconds, lap_number=state.lap_number + 1, stint_lap=stint_lap,
                  green_laps_in_stint=state.green_laps_in_stint + int(green), pitting_now=False, previous_flag=flag,
                  deferred_laps=state.deferred_laps + int(deferred))
    if stop:
        final = state.plan_index >= len(strategy.stint_laps) - 1
        next_index = state.plan_index if (forced or final) else state.plan_index + 1
        driver = strategy.drivers[next_index] if next_index != state.plan_index else state.driver
        new = replace(new, stint_number=state.stint_number + 1, stint_lap=0, green_laps_in_stint=0, plan_index=next_index,
                      driver=driver, pitting_now=True, last_stop_driver_change=driver != state.driver, last_stop_flag=entry_flag,
                      stops=state.stops + 1, extra_stops=state.extra_stops + int(forced))
    return new, record


@dataclass(frozen=True)
class RaceResult:
    laps: int
    finish_time_s: float
    stops: int
    extra_stops: int
    deferred_laps: int
    cautions: list
    age_slope_s: float
    records: pd.DataFrame

    def time_at_lap(self, lap: int) -> float:
        """Elapsed time when the car completed `lap`. NaN if it didn't get that far."""
        rows = self.records[self.records["lap"] == lap]
        return float(rows["race_time_s"].iloc[0]) if len(rows) else float("nan")


def simulate(params: CarParams, strategy: Strategy, randomness: Randomness | None = None, seed: int | None = None,
             check: bool = True) -> RaceResult:
    """Run one race. With no `randomness` it's the deterministic simulator. The race ends at the first
    crossing after `duration_s`, as at the chequered flag. A stop decided on the final lap isn't charged,
    because its out-lap never happens."""
    if check:
        result = check_strategy(params, strategy)
        if not result.ok:
            raise InfeasibleStrategy("; ".join(result.violations))
    race = draw_race(randomness, params, seed)
    slope = params.age_slope_s if race.age_slope_s is None else race.age_slope_s
    state = State(driver=strategy.drivers[0])
    records = []
    while state.race_time_s < params.duration_s:
        flag = flag_at(state.race_time_s, race.cautions)
        lap_index = state.lap_number
        draws = Draws(
            lap_noise_s=float(race.lap_noise_s[lap_index]) if lap_index < len(race.lap_noise_s) else 0.0,
            pit_loss_scale=float(race.pit_loss_scale[state.last_stop_driver_change][state.stops - 1])
            if state.pitting_now and 0 < state.stops <= len(race.pit_loss_scale[state.last_stop_driver_change]) else 1.0,
            incident_s=float(race.incident_s[lap_index]) if race.incident_s is not None and lap_index < len(race.incident_s) else None,
        )
        seconds, _ = lap_time(state, params, flag, draws, slope, state.race_time_s, race.cautions)
        entry_flag = flag_at(state.race_time_s + seconds, race.cautions)
        state, record = step(state, strategy, params, flag, entry_flag, draws, slope, race.cautions)
        records.append(record)
    frame = pd.DataFrame(records)
    return RaceResult(laps=state.lap_number, finish_time_s=state.race_time_s, stops=state.stops, extra_stops=state.extra_stops,
                      deferred_laps=state.deferred_laps, cautions=race.cautions, age_slope_s=slope, records=frame)
