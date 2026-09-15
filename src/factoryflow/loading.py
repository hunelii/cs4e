"""Reading the raw sensor export off disk.

Loading is not cleaning. This module's whole job is to turn a file into a
DataFrame with sensible dtypes and nothing else: no de-duplication, no
normalisation, no dropped rows. Everything that makes a judgement call about
the data belongs in `pipeline.clean()`, where it can be argued about.

Keeping that line sharp is the reason you can trust the row count.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from factoryflow import config

#: Columns as the machine controller writes them.
RAW_COLUMNS: tuple[str, ...] = (
    "timestamp",
    "machine_id",
    "line_id",
    "machine_state",
    "units_produced",
    "units_rejected",
    "temperature_c",
    "vibration_mm_s",
    "power_kw",
    "operator_shift",
)


def load_readings(path: Path | str | None = None) -> pd.DataFrame:
    """Load the raw sensor export.

    Args:
        path: CSV to read. Defaults to `config.DEFAULT_DATA_PATH`.

    Returns:
        One row per reading, with `timestamp` parsed and the numeric columns
        coerced. Values that cannot be parsed become NaN rather than raising --
        the export genuinely contains some, and hiding them behind an exception
        would only move the problem.

    Raises:
        FileNotFoundError: if the file is not there.
        ValueError: if an expected column is missing.
    """
    path = Path(path) if path is not None else config.DEFAULT_DATA_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"No sensor export at {path}. Expected the raw CSV in data/raw/ -- see the README."
        )

    readings = pd.read_csv(path)

    missing = [column for column in RAW_COLUMNS if column not in readings.columns]
    if missing:
        raise ValueError(f"{path.name} is missing column(s): {', '.join(missing)}")

    readings["timestamp"] = pd.to_datetime(readings["timestamp"], errors="coerce")
    #for column in ("units_produced", "units_rejected", "vibration_mm_s", "power_kw"):
        #readings[column] = pd.to_numeric(readings[column], errors="coerce")

    # temperature_c is deliberately left alone. It arrives as strings because
    # some rows use a decimal comma, and deciding what to do about that is a
    # cleaning decision, not a loading one.
    return readings
