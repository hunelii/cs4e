"""Flagging things a human should look at.

Two statistical detectors and two rules. No machine learning, on purpose: every
flag this module raises can be explained to a shift supervisor in one sentence,
and a flag nobody can explain is a flag nobody acts on.

The design constraint that matters is not sensitivity, it is volume. A flag is
not a fault -- it is a request for a human to look. Four thousand requests a day
is worse than none, so `detect()` collapses consecutive flagged minutes into
episodes and drops anything shorter than `config.MIN_EPISODE_MINUTES`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from factoryflow import config

#: Kinds of anomaly this module can report.
ANOMALY_KINDS: tuple[str, ...] = (
    "temperature_spike",
    "vibration_spike",
    "vibration_high",
    "stuck_sensor",
    "downtime",
)

_ANOMALY_COLUMNS = ["timestamp", "machine_id", "kind", "value", "severity", "duration_min"]

#: A DOWN stretch shorter than this is an ordinary micro-stop, not a breakdown.
#:
#: Tuned against the data, not guessed: stops on this line average around half
#: an hour, so a 30-minute threshold reports roughly every second stop and
#: buries the one that matters. Two hours is the point at which a stop stops
#: being production noise and becomes something a supervisor plans around.
_DOWNTIME_MIN_MINUTES = 120


def rolling_zscore(
    series: pd.Series,
    window: int = config.ZSCORE_WINDOW,
    threshold: float = config.ZSCORE_THRESHOLD,
) -> pd.Series:
    """Flag readings that are unusual compared with the recent past.

    The z-score of each reading is measured against the mean and standard
    deviation of the preceding `window` readings.

    What this assumes, and where it is wrong: that the signal is roughly normal
    and roughly stationary. Both assumptions break at a shift change, when the
    machine goes from RUN to SETUP and the temperature drops 25 degrees on
    purpose. `detect()` handles that by only comparing a running machine with
    itself while running.

    Why the window must be full. Spindle temperature is strongly
    autocorrelated: each minute looks a lot like the one before it. Estimate the
    spread from a half-empty window and you get a spread that is far too small,
    which makes ordinary drift look like a spike -- and because the drift lasts
    several minutes, it survives episode filtering and reaches the report. On
    this dataset, allowing half-full windows produces eight times as many
    temperature flags, all of them noise. So `min_periods` is the full window,
    and the first `window` readings of each stretch are simply not judged.

    Args:
        series: a numeric sensor column, in time order.
        window: how many readings back to compare against.
        threshold: how many standard deviations count as unusual.

    Returns:
        A boolean Series aligned to `series`. False wherever there is not enough
        history yet, which is never a claim that the reading was fine.
    """
    rolling = series.rolling(window=window, min_periods=window)
    deviation = series - rolling.mean()
    spread = rolling.std(ddof=0)

    # A perfectly flat window has zero spread, which would make every next
    # reading infinitely unusual. That case is the stuck-sensor detector's job.
    zscore = deviation / spread.replace(0.0, np.nan)
    return (zscore.abs() > threshold).fillna(False)


def stuck_sensor(series: pd.Series, window: int = config.STUCK_WINDOW) -> pd.Series:
    """Flag stretches where a physical sensor has not moved at all.

    Real spindle temperature drifts by a few tenths of a degree from minute to
    minute. A reading that is byte-identical for half an hour is not a calm
    machine, it is a dead sensor or a cached value.

    Args:
        series: a numeric sensor column, in time order.
        window: how many identical consecutive readings count as stuck.

    Returns:
        A boolean Series aligned to `series`, True from the point the stretch is
        long enough until it ends.
    """
    rolling = series.rolling(window=window, min_periods=window)
    unchanged = (rolling.max() - rolling.min()).abs() < 1e-9
    # "not enough history yet" is not a claim that the sensor was fine, but it
    # is not a flag either.
    return unchanged.fillna(False)


def _episodes(flags: pd.Series) -> list[tuple[int, int]]:
    """Collapse a boolean Series into (start, end) positional slices of True runs."""
    values = flags.to_numpy(dtype=bool)
    if not values.any():
        return []
    padded = np.concatenate(([False], values, [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return list(zip(edges[0::2], edges[1::2], strict=True))


def _summarise(
    machine_readings: pd.DataFrame,
    flags: pd.Series,
    kind: str,
    value_column: str,
    severity_scale: float,
) -> list[dict]:
    """Turn flagged minutes into one record per episode."""
    records = []
    for start, end in _episodes(flags):
        duration = end - start
        if duration < config.MIN_EPISODE_MINUTES:
            continue
        window = machine_readings.iloc[start:end]
        peak = window[value_column].abs().max()
        records.append(
            {
                "timestamp": window["timestamp"].iloc[0],
                "machine_id": window["machine_id"].iloc[0],
                "kind": kind,
                "value": None if pd.isna(peak) else round(float(peak), 2),
                "severity": round(min(1.0, duration / severity_scale), 2),
                "duration_min": int(duration),
            }
        )
    return records


def detect(clean_df: pd.DataFrame) -> pd.DataFrame:
    """Find everything in this frame that a human should look at.

    Args:
        clean_df: output of `pipeline.clean()`.

    Returns:
        One row per episode, sorted by time. Columns: timestamp, machine_id,
        kind, value, severity, duration_min. Severity is in [0, 1] and is driven
        by how long the episode lasted, not by how extreme the peak was -- a
        two-minute spike is noise, a two-hour one is a maintenance job.

        Empty (but correctly shaped) if nothing is worth reporting.
    """
    # They read the first day's worth, notice that most of them resolve
    # themselves, and stop reading. After that the detector is worse than having
    # none, because the organisation now believes something is watching. Ninety
    # flagged minutes inside one long vibration episode is one thing to look at,
    # not ninety, and reporting it as ninety is how you train people to ignore
    # the one that mattered.
    records: list[dict] = []

    for _, machine_readings in clean_df.sort_values(["machine_id", "timestamp"]).groupby(
        "machine_id", sort=True
    ):
        machine_readings = machine_readings.reset_index(drop=True)
        temperature = machine_readings["temperature_c"]
        vibration = machine_readings["vibration_mm_s"]

        # Compare a running machine only against itself while running. A spindle
        # that cools 25 degrees because the operator started a changeover is not
        # an anomaly, it is a changeover -- and a detector that cannot tell the
        # difference will report one every shift until nobody reads it any more.
        while_running = machine_readings["machine_state"].eq(config.PRODUCING_STATE)

        records += _summarise(
            machine_readings, stuck_sensor(temperature), "stuck_sensor", "temperature_c", 60
        )
        records += _summarise(
            machine_readings,
            rolling_zscore(temperature.where(while_running)),
            "temperature_spike",
            "temperature_c",
            30,
        )
        records += _summarise(
            machine_readings,
            rolling_zscore(vibration.where(while_running)),
            "vibration_spike",
            "vibration_mm_s",
            30,
        )
        records += _summarise(
            machine_readings,
            vibration > config.VIBRATION_WARN_MM_S,
            "vibration_high",
            "vibration_mm_s",
            120,
        )

        downtime = machine_readings["machine_state"].eq("DOWN")
        records += [
            record
            for record in _summarise(machine_readings, downtime, "downtime", "power_kw", 360)
            if record["duration_min"] >= _DOWNTIME_MIN_MINUTES
        ]

    if not records:
        return pd.DataFrame(columns=_ANOMALY_COLUMNS)

    return pd.DataFrame(records)[_ANOMALY_COLUMNS].sort_values("timestamp").reset_index(drop=True)


