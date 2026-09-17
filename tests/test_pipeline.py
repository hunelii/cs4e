"""Tests for cleaning and aggregation.

Three of these exist because of a specific incident. They are marked.
"""

from __future__ import annotations

import pandas as pd
import pytest

from factoryflow import config, metrics, pipeline


def test_clean_normalises_machine_ids() -> None:
    """Four spellings of the same machine must collapse to one."""
    raw = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-03-01", periods=4, freq="1min"),
            "machine_id": ["M-01", "m-01", "M-1", " M-01"],
            "line_id": "A",
            "machine_state": "RUN",
            "units_produced": [10, 10, 10, 10],
            "units_rejected": [0, 0, 0, 0],
            "temperature_c": ["60.0", "60,5", "61.0", "61.5"],
            "vibration_mm_s": [1.0, 1.0, 1.0, 1.0],
            "power_kw": [20.0, 20.0, 20.0, 20.0],
            "operator_shift": "C",
        }
    )
    cleaned = pipeline.clean(raw)
    assert set(cleaned.machine_id) == {"M-01"}


def test_clean_parses_the_decimal_comma() -> None:
    """'60,5' is sixty point five, not a string and not NaN."""
    raw = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-03-01", periods=2, freq="1min"),
            "machine_id": "M-01",
            "line_id": "A",
            "machine_state": "RUN",
            "units_produced": [10, 10],
            "units_rejected": [0, 0],
            "temperature_c": ["60,5", "61.5"],
            "vibration_mm_s": [1.0, 1.0],
            "power_kw": [20.0, 20.0],
            "operator_shift": "C",
        }
    )
    cleaned = pipeline.clean(raw)
    assert cleaned.temperature_c.tolist() == [60.5, 61.5]


def test_clean_makes_impossible_counts_possible(real_readings: pd.DataFrame) -> None:
    """No negative production, and never more rejects than units."""
    assert real_readings.units_produced.min() >= 0
    assert (real_readings.units_rejected <= real_readings.units_produced).all()


def test_clean_leaves_one_row_per_machine_minute(real_readings: pd.DataFrame) -> None:
    duplicated = real_readings.duplicated(subset=["machine_id", "timestamp"])
    assert not duplicated.any(), (
        f"{int(duplicated.sum())} duplicate machine-minutes survived cleaning"
    )


# --- the three that exist because of an incident -------------------------


def test_shift_boundaries_are_utc(real_readings: pd.DataFrame) -> None:
    """INCIDENT: shift B was credited with shift A's units after 29 March.

    The export writes timestamps without a timezone suffix. Read as local time,
    2026-03-29 loses an hour to the DST switch and every shift boundary after it
    lands sixty minutes off.

    Two things are asserted, and both matter: that the column is UTC-aware at
    all, and that the DST day still has a full 1440 minutes. The first alone
    would pass even if the wrong zone were attached.
    """
    assert str(real_readings.timestamp.dt.tz) == "UTC"

    dst_day = real_readings[
        (real_readings.timestamp >= "2026-03-29T00:00:00Z")
        & (real_readings.timestamp < "2026-03-30T00:00:00Z")
    ]
    for machine_id, group in dst_day.groupby("machine_id"):
        minutes = group.timestamp.nunique()
        assert minutes == 1440, (
            f"{machine_id} has {minutes} minutes on the DST day, expected 1440. "
            "Timestamps are probably being parsed as local time."
        )


def test_resample_preserves_total_units(real_readings: pd.DataFrame) -> None:
    """INCIDENT: the monthly total stopped matching the sum of the shifts.

    Bucketing must not lose a row. Any filter, any `[:-1]` to trim an
    'incomplete' last bucket, any closed/label mismatch shows up here as
    missing units.
    """
    expected = int(real_readings["units_produced"].sum())
    for freq in config.ALLOWED_FREQS:
        table = pipeline.kpi_table(real_readings, freq=freq)
        assert int(table.units_produced.sum()) == expected, f"units lost at freq={freq}"


def test_resample_preserves_run_minutes(real_readings: pd.DataFrame) -> None:
    """The same guarantee for time as for units -- a lost bucket lifts availability."""
    expected = int(real_readings.machine_state.eq(config.PRODUCING_STATE).sum())
    for freq in config.ALLOWED_FREQS:
        table = pipeline.kpi_table(real_readings, freq=freq)
        assert int(table.run_minutes.sum()) == expected, f"run time lost at freq={freq}"




def test_clean_caps_rejected_units_at_produced() -> None:
    """Rejected units cannot exceed produced units after cleaning."""
    raw = pd.DataFrame(
        {
            "machine_id": ["M-01"],
            "timestamp": ["2026-01-01 00:00:00"],
            "temperature_c": ["20.0"],
            "units_produced": [50],
            "units_rejected": [52],
        }
    )

    cleaned = pipeline.clean(raw)

    assert int(cleaned.loc[0, "units_rejected"]) == 50











# --- the vectorised table must agree with the scalar functions -----------


def test_kpi_table_agrees_with_metrics(real_readings: pd.DataFrame) -> None:
    """`kpi_table` computes the same four formulas as `metrics`, faster.

    Two implementations of one definition will drift apart unless something
    holds them together. This test is that something. It samples buckets rather
    than checking all 2 232, because a test that takes a minute gets skipped.
    """
    table = pipeline.kpi_table(real_readings, freq="8h").dropna(subset=["oee"])
    sample = table.sample(n=min(12, len(table)), random_state=0)

    for row in sample.itertuples(index=False):
        bucket_end = pd.Timestamp(row.bucket_start) + pd.Timedelta(8, unit="h")
        slice_ = real_readings[
            (real_readings.machine_id == row.machine_id)
            & (real_readings.timestamp >= row.bucket_start)
            & (real_readings.timestamp < bucket_end)
        ]
        assert metrics.availability(slice_) == pytest.approx(row.availability)
        assert metrics.performance(slice_) == pytest.approx(row.performance)
        assert metrics.quality(slice_) == pytest.approx(row.quality)
        assert metrics.oee(slice_) == pytest.approx(row.oee)


def test_resample_rejects_a_freq_nobody_meant(real_readings: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="freq must be one of"):
        pipeline.resample_readings(real_readings.head(100), freq="3h")
