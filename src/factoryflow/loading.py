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
    # ── CORE 1 -- start here ───────────────────────────── about 10 minutes ──
    #
    # WRITE
    #   Two small gaps, marked TODO(L1) below. The error handling around them is
    #   already written -- read it, do not rewrite it.
    #
    #   Gap 1: read the file.
    #   Gap 2: give five columns the right type.
    #
    # YOU NEED TWO FUNCTIONS
    #   pd.read_csv(path)                        file -> DataFrame
    #   pd.to_numeric(series, errors="coerce")   text -> numbers, and anything
    #                                            unparseable becomes NaN instead
    #                                            of blowing up. The export
    #                                            genuinely contains some.
    #   pd.to_datetime(series, errors="coerce")  the same for the timestamp.
    #
    # THE LINE THIS FUNCTION DOES NOT CROSS
    #   Loading is not cleaning. Do not drop duplicates, do not fix the machine
    #   ids, do not touch `temperature_c`. It arrives as text because some rows
    #   use a decimal comma, and what to do about that is a judgement call that
    #   belongs in pipeline.clean() on day 2. Keeping this line sharp is the
    #   reason you can trust the row count.
    #
    # HINT 1  Gap 1 is one line and the variable must be called `readings`,
    #         because the code underneath already uses that name.
    # HINT 2  readings = pd.read_csv(path)
    # HINT 3  Gap 2, for the timestamp:
    #             readings["timestamp"] = pd.to_datetime(
    #                 readings["timestamp"], errors="coerce")
    #         The numeric columns are the same shape with pd.to_numeric. Write
    #         it four times, or write a `for column in (...)` loop -- both are
    #         fine, and noticing that they are the same line four times over is
    #         the point of this afternoon.
    #
    # DONE WHEN
    #   uv run python -c "import factoryflow.loading as l; print(len(l.load_readings()))"
    #   prints 134176.
    #
    # STUCK AFTER 15 MINUTES? Take the finished version, no questions asked:
    #   in the course folder:  git checkout end/s1-4
    #   then copy src/factoryflow/loading.py over yours, and commit it.
    path = Path(path) if path is not None else config.DEFAULT_DATA_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"No sensor export at {path}. Expected the raw CSV in data/raw/ -- see the README."
        )

    # TODO(L1): read the CSV into a frame called `readings`

    missing = [column for column in RAW_COLUMNS if column not in readings.columns]
    if missing:
        raise ValueError(f"{path.name} is missing column(s): {', '.join(missing)}")

    # TODO(L1): pd.to_datetime the timestamp, pd.to_numeric the 4 number columns

    # temperature_c is deliberately left alone. It arrives as strings because
    # some rows use a decimal comma, and deciding what to do about that is a
    # cleaning decision, not a loading one.
    return readings
