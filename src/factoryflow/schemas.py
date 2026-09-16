"""The shapes that cross the network boundary.

Handed out complete. This file is the contract between the API and the
dashboard: the dashboard is written against these field names, so changing one
breaks something you cannot see from here.

Note the `float | None` on every metric. Inside pandas an undefined metric is
NaN, which is convenient and correct. On the wire it is not: `NaN` is not valid
JSON, and a browser will refuse to parse a response containing it. So the API
converts NaN to null at the boundary, and the models say so.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Health(BaseModel):
    """Is the service up, and did it actually find any data?"""

    status: str = Field(examples=["ok"])
    rows_loaded: int = Field(description="Readings held in memory after cleaning.")


class Machine(BaseModel):
    """A machine on the line."""

    machine_id: str = Field(examples=["M-01"])
    line: str = Field(examples=["A"])


class KpiRow(BaseModel):
    """OEE and its factors for one machine over one time bucket.

    A metric is null when its denominator is zero -- an hour in which the
    machine produced nothing has no quality, which is different from a quality
    of zero.
    """

    machine_id: str
    bucket_start: datetime
    availability: float | None
    performance: float | None
    quality: float | None
    oee: float | None
    units_produced: int
    units_rejected: int
    run_minutes: int
    planned_minutes: int


class Anomaly(BaseModel):
    """One episode worth a human looking at it."""

    timestamp: datetime
    machine_id: str
    kind: str = Field(examples=["vibration_high"])
    value: float | None = Field(description="Peak value reached during the episode.")
    severity: float = Field(ge=0.0, le=1.0)
    duration_min: int
