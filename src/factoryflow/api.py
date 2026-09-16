"""The REST interface.

Four read-only routes. The route table is frozen: `dashboard/app.py` is written
against exactly these paths and parameter names, so inventing a fifth is fine
but renaming one of these four is not.

    GET /health      is the service up, and did it find data
    GET /machines    what is on the line
    GET /metrics     OEE per machine per time bucket
    GET /anomalies   episodes worth looking at

Data loading. The CSV is read once at startup into a module-level DataFrame.
There is no database. That is a deliberate simplification and here is exactly
what it costs: the data is frozen at process start, memory grows with the file,
two workers hold two copies, and nobody can write. For a month of one line that
is a fine trade. For a year of forty lines it is not, and the answer then is a
database, not a bigger machine.
"""

from __future__ import annotations

import math
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query

from factoryflow import anomalies, config, loading, pipeline
from factoryflow.schemas import Anomaly, Health, KpiRow, Machine

#: Populated at startup by the lifespan handler below.
_readings: pd.DataFrame = pd.DataFrame()


# New readings written after the process started are invisible until someone
# restarts it, so the dashboard can show yesterday's number while insisting it
# is live. And every worker process holds its own full copy, so scaling to four
# workers quadruples the memory instead of sharing anything. Neither matters for
# one month of one line on one machine, which is exactly why it is worth writing
# down: the trade is fine today and stops being fine without announcing itself.


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load and clean the export once, before the first request arrives."""
    global _readings
    _readings = pipeline.clean(loading.load_readings())
    yield
    _readings = pd.DataFrame()


app = FastAPI(
    title="FactoryFlow",
    version="0.3.0",
    summary="OEE reporting for production line A",
    lifespan=lifespan,
)


def _clean_value(value: Any) -> Any:
    """NaN and NaT are not JSON. Null is."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if value is pd.NaT:
        return None
    return value


def _records(frame: pd.DataFrame) -> list[dict]:
    """Turn a frame into JSON-safe dicts."""
    return [
        {key: _clean_value(value) for key, value in record.items()}
        for record in frame.to_dict(orient="records")
    ]


def _filter_machine(frame: pd.DataFrame, machine: str | None) -> pd.DataFrame:
    if machine is None:
        return frame
    known = set(frame["machine_id"].unique())
    if machine not in known:
        raise HTTPException(404, f"Unknown machine {machine!r}. Known: {sorted(known)}")
    return frame[frame["machine_id"] == machine]


def _as_utc(moment: datetime) -> pd.Timestamp:
    """Accept a timestamp with or without an offset; treat a bare one as UTC."""
    stamp = pd.Timestamp(moment)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


@app.get("/health", response_model=Health, summary="Liveness and data check")
def health() -> Health:
    """Report that the service is up and how much data it is holding.

    `rows_loaded == 0` means the process started but never found the export --
    which looks identical to a healthy service until someone asks for a number.
    """
    return Health(status="ok", rows_loaded=len(_readings))


@app.get("/machines", response_model=list[Machine], summary="Machines on the line")
def machines() -> list[Machine]:
    """List the machines present in the loaded data."""
    if _readings.empty:
        return []
    pairs = _readings[["machine_id", "line_id"]].drop_duplicates().sort_values("machine_id")
    return [
        Machine(machine_id=row.machine_id, line=row.line_id)
        for row in pairs.itertuples(index=False)
    ]


@app.get("/metrics", response_model=list[KpiRow], summary="OEE per machine per bucket")
def metrics(
    machine: Annotated[str | None, Query(description="e.g. M-01. Omit for all.")] = None,
    from_: Annotated[datetime | None, Query(alias="from", description="inclusive")] = None,
    to: Annotated[datetime | None, Query(description="inclusive")] = None,
    freq: Annotated[str, Query(description=f"one of {config.ALLOWED_FREQS}")] = config.DEFAULT_FREQ,
) -> list[KpiRow]:
    """Return the KPI table, optionally narrowed to a machine and a time window.

    `from` and `to` are both inclusive, because a supervisor asking for
    "the 14th to the 16th" means three days, not two and a bit.
    """
    if freq not in config.ALLOWED_FREQS:
        raise HTTPException(422, f"freq must be one of {config.ALLOWED_FREQS}, got {freq!r}")

    selected = _filter_machine(_readings, machine)

    if from_ is not None:
        selected = selected[selected["timestamp"] >= _as_utc(from_)]
    if to is not None:
        selected = selected[selected["timestamp"] <= _as_utc(to)]

    # An empty selection is a fine answer, not an error. Nobody asked a wrong
    # question; there is simply nothing in that window.
    if selected.empty:
        return []

    return [KpiRow(**record) for record in _records(pipeline.kpi_table(selected, freq))]


@app.get("/anomalies", response_model=list[Anomaly], summary="Episodes worth looking at")
def anomaly_list(
    machine: Annotated[str | None, Query(description="e.g. M-01. Omit for all.")] = None,
    since: Annotated[datetime | None, Query(description="inclusive")] = None,
    min_severity: Annotated[float, Query(ge=0.0, le=1.0)] = 0.0,
) -> list[Anomaly]:
    """Return detected anomaly episodes, most severe first.

    Raising `min_severity` is the intended way to make this list short enough to
    act on. A list nobody reads protects nobody.
    """
    selected = _filter_machine(_readings, machine)
    if selected.empty:
        return []

    # detect() can legitimately find nothing, and an empty frame has no columns
    # to filter or sort on. Check before you touch it.
    found = anomalies.detect(selected)
    if found.empty:
        return []

    if since is not None:
        found = found[found["timestamp"] >= _as_utc(since)]
    found = found[found["severity"] >= min_severity]

    found = found.sort_values(["severity", "timestamp"], ascending=[False, True])
    return [Anomaly(**record) for record in _records(found)]


