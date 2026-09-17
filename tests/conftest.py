"""Shared fixtures.

Handed out complete. Two kinds of test data live here, and the difference
matters:

`sample_readings` is ten rows written by hand, chosen so that every expected
value is a number you can work out on paper in ten seconds. When a test built on
it fails, the test is telling you about your code, not about the dataset.

`real_readings` is the actual March export. Tests built on it catch the things
small fixtures never do -- a defect class you forgot, a dtype that only appears
in row 90 000. It is loaded once per session because that takes a second.
"""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from factoryflow import loading, pipeline


@pytest.fixture
def sample_readings() -> pd.DataFrame:
    """Ten minutes on one machine, with metrics that come out round.

    planned production time = 9 min (everything but SETUP)
    run time                = 6 min
    units                   = 60, of which 6 rejected

    availability = 6 / 9              = 2/3
    performance  = (4.0 x 60) / 360 s = 2/3
    quality      = 54 / 60            = 0.9
    oee          = 2/3 x 2/3 x 0.9    = 0.4
    """
    states = ["RUN"] * 6 + ["IDLE", "IDLE", "DOWN", "SETUP"]
    produced = [10] * 6 + [0, 0, 0, 0]
    rejected = [1] * 6 + [0, 0, 0, 0]

    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-03-01", periods=10, freq="1min", tz="UTC"),
            "machine_id": "M-01",
            "line_id": "A",
            "machine_state": states,
            "units_produced": produced,
            "units_rejected": rejected,
            "temperature_c": [60.0 + index * 0.1 for index in range(10)],
            "vibration_mm_s": [1.5] * 10,
            "power_kw": [20.0] * 6 + [3.0, 3.0, 0.5, 5.0],
            "operator_shift": "C",
        }
    )


@pytest.fixture
def idle_readings(sample_readings: pd.DataFrame) -> pd.DataFrame:
    """A bucket in which the machine was powered but produced nothing.

    An idle night shift is not an error and not a zero. Several metrics are
    undefined here, and that is the correct answer.
    """
    idle = sample_readings.copy()
    idle["machine_state"] = "IDLE"
    idle["units_produced"] = 0
    idle["units_rejected"] = 0
    return idle


@pytest.fixture(scope="session")
def real_readings() -> pd.DataFrame:
    """The whole March export, cleaned. Loaded once."""
    return pipeline.clean(loading.load_readings())


@pytest.fixture(scope="session")
def client():
    """A test client for the API, with the real data loaded.

    The `with` block matters: it runs the startup handler. Without it the API
    answers every request from an empty DataFrame and the tests pass while
    proving nothing.
    """
    from factoryflow.api import app

    with TestClient(app) as test_client:
        yield test_client
