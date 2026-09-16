"""OEE and its three factors.

    OEE = Availability x Performance x Quality

    Availability = run_time / planned_production_time
    Performance  = (ideal_cycle_time_s x total_units) / run_time
    Quality      = good_units / total_units

Every function here takes a frame of per-minute readings and returns one number.
That is the whole contract, and it is what makes the same four functions usable
for a single machine, a single shift, or the entire month.

On undefined results. A metric of nothing is not zero and it is not an error --
an idle night shift produced no units, and asking for its quality is a fair
question with no answer. These functions return `float("nan")` in that case.
NaN propagates through arithmetic, survives aggregation, and prints as an empty
cell in a report, which is exactly the behaviour you want. Returning 0.0 would
quietly drag every average down; raising would make the KPI table impossible to
build.
"""

from __future__ import annotations

import math

import pandas as pd

from factoryflow import config



def _minutes_in_state(readings: pd.DataFrame, states: frozenset[str] | set[str]) -> int:
    """How many readings -- and therefore minutes -- were spent in these states."""
    return int(readings["machine_state"].isin(states).sum())


def availability(readings: pd.DataFrame) -> float:
    """Share of planned production time the machine was actually running.

    Planned production time excludes SETUP: a changeover is planned work, so it
    is not held against the machine. See `config.PLANNED_STATES`.

    Args:
        readings: per-minute readings, cleaned.

    Returns:
        A value in [0, 1], or NaN if there was no planned production time at all.
    """
    # A changeover is scheduled work. The plan already accounts for it, so the
    # machine is not being blamed for time nobody expected it to produce in.
    # Count SETUP as planned and availability drops for a reason no operator can
    # act on. A maintenance planner arguing the other way has a real case: if
    # setups take three hours a day, hiding them makes the line look healthy
    # while the changeover process is what is actually costing output.
    planned_minutes = _minutes_in_state(readings, config.PLANNED_STATES)
    if planned_minutes == 0:
        return math.nan
    run_minutes = _minutes_in_state(readings, {config.PRODUCING_STATE})
    return run_minutes / planned_minutes


def performance(readings: pd.DataFrame, ideal_cycle_time_s: float | None = None) -> float:
    """Share of the theoretical output the machine achieved while running.

    A machine that could make one unit every 4 seconds but averaged one every
    5 is performing at 80 %, even though it never stopped.

    Args:
        readings: per-minute readings, cleaned.
        ideal_cycle_time_s: seconds per unit at 100 %. Defaults to
            `config.IDEAL_CYCLE_TIME_S`.

    Returns:
        A value in [0, 1] under normal conditions, or NaN if the machine never
        ran. Values slightly above 1.0 are possible and mean the ideal cycle
        time is wrong, not that the machine is magic.
    """
    if ideal_cycle_time_s is None:
        ideal_cycle_time_s = config.IDEAL_CYCLE_TIME_S

    run_minutes = _minutes_in_state(readings, {config.PRODUCING_STATE})
    if run_minutes == 0:
        return math.nan

    total_units = int(readings["units_produced"].sum())
    run_seconds = run_minutes * config.SAMPLE_INTERVAL_S
    return (ideal_cycle_time_s * total_units) / run_seconds


def quality(readings: pd.DataFrame) -> float:
    """Share of produced units that were not rejected.

    Args:
        readings: per-minute readings, cleaned.

    Returns:
        A value in [0, 1], or NaN if nothing was produced.

        A result above 1.0 is arithmetically impossible and means the input was
        not cleaned: the raw export contains rows where `units_rejected` exceeds
        `units_produced`. That is the bug that reported 104 % for a week.
    """
    # Zero quality is a claim: it says every unit made was scrap. Nothing was
    # made, so the claim is false. NaN says "no answer", which is the truth.
    # The practical difference shows up on the monthly average: zeroes get
    # averaged in and drag the number down, NaN is skipped, so the report says
    # what the producing hours actually achieved instead of quietly punishing
    # the line for standing still.
    total_units = int(readings["units_produced"].sum())
    if total_units == 0:
        return math.nan
    rejected_units = int(readings["units_rejected"].sum())
    return (total_units - rejected_units) / total_units


def oee(readings: pd.DataFrame, ideal_cycle_time_s: float | None = None) -> float:
    """Overall Equipment Effectiveness: availability x performance x quality.

    Args:
        readings: per-minute readings, cleaned.
        ideal_cycle_time_s: seconds per unit at 100 %. Defaults to
            `config.IDEAL_CYCLE_TIME_S`.

    Returns:
        A value in [0, 1], or NaN if any factor is undefined. World-class is
        around 0.85; this line runs in the high sixties.
    """
    return availability(readings) * performance(readings, ideal_cycle_time_s) * quality(readings)


