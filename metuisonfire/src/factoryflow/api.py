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


# ══ THIS SESSION ═══════════════════════════════════════════════════════════
#
#   CORE 1  /health      one line, with the facilitator            ~5 min
#   CORE 2  /machines    three lines, with the facilitator        ~10 min
#   CORE 3  /metrics     two small gaps, on your own              ~20 min
#   CORE 4  /anomalies   two small gaps, on your own              ~15 min
#
#   The four routes are already declared with their decorators, their
#   parameters and their return types. Nothing about FastAPI itself is your
#   problem today -- you are filling in bodies.
#
#   BONUS is at the bottom of this file.
#
# THE WHOLE MENTAL MODEL, IN FOUR LINES
#   A route is a normal Python function with a decorator above it.
#   Whatever you return, FastAPI turns into JSON.
#   `response_model=` in the decorator is a promise about the shape -- return
#   something else and you get a clear error instead of a wrong response.
#   `_readings` is the whole cleaned export, already loaded at startup. It is
#   an ordinary DataFrame; treat it as one.
#
# THREE HELPERS ARE ALREADY WRITTEN FOR YOU
#   _filter_machine(frame, machine)  narrows to one machine, 404 if unknown
#   _records(frame)                  DataFrame -> JSON-safe list of dicts
#   _as_utc(moment)                  a query parameter -> a UTC timestamp
#   raise HTTPException(404, "msg")  is how you refuse a request
#
# HOW TO SEE WHAT YOU ARE DOING
#   uv run uvicorn factoryflow.api:app --reload --port 8000
#   Then open http://localhost:8000/docs -- FastAPI generates a page from your
#   own code where every route has a "Try it out" button. No curl, no second
#   tool. `--reload` restarts the server every time you save.
#   Port already in use? Add --port 8001. It is not a problem, just a port.
#
# DONE WHEN
#   http://localhost:8000/metrics?machine=M-01&freq=1h  returns real numbers
#   http://localhost:8000/docs                          loads and works
#
# STUCK AFTER 15 MINUTES ON ANY ONE ROUTE?
#   in the course folder:  git checkout end/s2-3
#   then copy src/factoryflow/api.py over yours, and commit it.
# TODO(EXPLAIN): The whole export is loaded into a variable at startup and never reloaded. Name
# two things that breaks.
# Two or three sentences, in your own words. Not what the code
# does line by line -- why it does it that way.
#
# Your answer:
#


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
    # TODO(L1): CORE 1 -- return Health(status=..., rows_loaded=len(_readings))


@app.get("/machines", response_model=list[Machine], summary="Machines on the line")
def machines() -> list[Machine]:
    """List the machines present in the loaded data."""
    # TODO(L1): CORE 2 -- drop_duplicates on machine_id/line_id, one Machine per row


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
    # ── CORE 3 ─────────────────────────────────────────── about 20 minutes ──
    #
    # WRITE
    #   Two gaps. The rejected-freq check and the empty-selection check are
    #   already here; you write the narrowing and the return.
    #
    #   Gap 1: keep only rows inside the requested time window.
    #   Gap 2: hand the selection to pipeline.kpi_table() and return the rows.
    #
    # WATCH OUT
    #   `from_` has a trailing underscore because `from` is a Python keyword.
    #   In the URL it is still `from` -- the `alias=` in the signature does
    #   that, and you do not have to do anything about it.
    #   Both ends of the window are INCLUSIVE. A supervisor asking for "the
    #   14th to the 15th" means two days. Use >= and <=, not > and <.
    #   `from_` and `to` may each be None. None means "no limit", not "no rows".
    #
    # HINT 1  Gap 1 is two `if ... is not None:` blocks, each narrowing
    #         `selected` by one end of the window.
    # HINT 2  if from_ is not None:
    #             selected = selected[selected["timestamp"] >= _as_utc(from_)]
    #         ...and the mirror image for `to`, with <=.
    # HINT 3  Gap 2 is one line. Read it right to left:
    #             kpi_table gives a DataFrame
    #             _records() turns it into JSON-safe dicts
    #             KpiRow(**record) turns each dict into the response model
    #         return [KpiRow(**record)
    #                 for record in _records(pipeline.kpi_table(selected, freq))]
    #
    # DONE WHEN
    #   http://localhost:8000/metrics?machine=M-01&freq=1h returns 744 rows of
    #   real numbers, and /docs still loads.
    if freq not in config.ALLOWED_FREQS:
        raise HTTPException(422, f"freq must be one of {config.ALLOWED_FREQS}, got {freq!r}")

    selected = _filter_machine(_readings, machine)

    # TODO(L1): narrow to timestamp >= from_ and <= to, where each one was given

    # An empty selection is a fine answer, not an error. Nobody asked a wrong
    # question; there is simply nothing in that window.
    if selected.empty:
        return []

    # TODO(L1): one KpiRow per record in _records(pipeline.kpi_table(selected, freq))


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
    # ── CORE 4 ─────────────────────────────────────────── about 15 minutes ──
    #
    # WRITE
    #   Two gaps, and the second one is the interesting half of this route.
    #
    #   Gap 1: drop episodes before `since` and below `min_severity`.
    #   Gap 2: sort, and return.
    #
    #   Same shape as /metrics -- narrow, compute, return -- so if /metrics
    #   works you already know how this ends.
    #
    # WATCH OUT -- gap 2 is a design decision, not plumbing
    #   Nobody scrolls an alert list. If the six-hour breakdown is not in the
    #   first three rows, for practical purposes it is not in the response at
    #   all. So: most severe FIRST, and within equal severity, earliest first.
    #   `sort_values` takes two lists -- the columns, and the directions.
    #
    # HINT 1  Gap 1: one `if since is not None:` narrowing, then one
    #         unconditional narrowing on severity (min_severity defaults to
    #         0.0, so the unconditional version is already correct).
    # HINT 2  found = found[found["severity"] >= min_severity]
    # HINT 3  Gap 2: found = found.sort_values(
    #                    ["severity", "timestamp"], ascending=[False, True])
    #         return [Anomaly(**record) for record in _records(found)]
    #
    # DONE WHEN
    #   http://localhost:8000/anomalies?min_severity=0.9 puts the M-02
    #   breakdown of 14 March at or near the top.
    selected = _filter_machine(_readings, machine)
    if selected.empty:
        return []

    # detect() can legitimately find nothing, and an empty frame has no columns
    # to filter or sort on. Check before you touch it.
    found = anomalies.detect(selected)
    if found.empty:
        return []

    # TODO(L1): drop episodes before `since`, then those below min_severity

    # TODO(L1): sort most severe first, earliest first; return one Anomaly per record


# ══ BONUS ══════════════════════════════════════════════════════════════════
#
#   Only once all four routes answer and are committed. Pick one.
#
#   B1  Add GET /machines/{machine_id}/summary -- one object with the machine's
#       OEE for the whole month and its three worst hours. This is the route a
#       dashboard actually wants, and noticing that is the point.
#
#   B2  Break something on purpose. Ask for freq=3h, machine=M-99, and
#       from=not-a-date. Three different failures come back. Decide whether
#       each response would tell a stranger what to do differently, and fix the
#       one that would not.
#
#   B3  /metrics recomputes the whole KPI table on every single request. Time
#       it. Then cache it -- `functools.lru_cache` on a small helper is enough.
#       Then write down, in a comment, what your cache is now wrong about.
#
#   B4  Add `?limit=` and `?offset=` to /metrics. A month at 15min is 8928 rows
#       per machine, which is not a response, it is a download.
#
#   B5  Give /health something worth having: how old the newest reading is. A
#       service that is up and serving three-day-old numbers is the failure
#       mode that health checks are supposed to catch and usually do not.
# ═══════════════════════════════════════════════════════════════════════════
