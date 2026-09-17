"""The face of FactoryFlow: what the shift supervisor actually opens.

This dashboard talks to the API over HTTP. It does not import `factoryflow` and
it does not read the CSV. That separation is the whole point of yesterday's
work: the numbers have one source, and anything that wants them asks for them.

Run it with the API already running:

    uvicorn factoryflow.api:app --port 8000
    streamlit run dashboard/app.py

Set FACTORYFLOW_API to point somewhere else (docker compose does).
"""

from __future__ import annotations

import os
from datetime import date

import httpx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

API_BASE = os.environ.get("FACTORYFLOW_API", "http://localhost:8000")
REQUEST_TIMEOUT_S = 30.0

# ══ THIS LAB ═══════════════════════════════════════════════════════════════
#
#   CORE 1  fetch()      one HTTP GET, below                        ~5 min
#   CORE 2  the KPI frame, further down                            ~15 min
#   THEN    make it YOUR dashboard -- that is the other 45 minutes.
#
#   The two core gaps exist to get numbers on the screen. They are not the
#   lab. The lab is the brief:
#
#       Your supervisor gives this thirty seconds before the shift meeting.
#       FIVE numbers. If a sixth earns its place, say which one it replaces.
#
#   Everything on this page right now is a suggestion, including the charts.
#   Delete what does not earn its place. The BONUS list at the bottom is the
#   menu if you would rather add than subtract.
#
#   YOU NEED TWO TERMINALS. This is the single most common stumble of the
#   afternoon:
#       terminal 1:  uv run uvicorn factoryflow.api:app --port 8000
#       terminal 2:  uv run streamlit run dashboard/app.py
#   If the page shows an API error, terminal 1 is not running. The sidebar
#   says so; read it before you change any code.
# ═══════════════════════════════════════════════════════════════════════════

# TODO(EXPLAIN): Reading the CSV directly here would be fewer moving parts. Why go through the
# API instead?
# Two or three sentences, in your own words. Not what the code
# does line by line -- why it does it that way.
#
# Your answer:
# Going through the API keeps the calculation logic in one place, so the dashboard
# does not create its own version of the metrics. It also means other clients can
# use the same trusted results without needing direct access to the raw CSV.

# --- palette -------------------------------------------------------------
# Validated as a categorical set against this surface. One fixed colour per
# machine, assigned by identity: filtering M-02 out must not repaint M-03.

SURFACE = "#fcfcfb"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
INK_MUTED = "#898781"
INK_SECONDARY = "#52514e"

MACHINE_COLOUR = {"M-01": "#2a78d6", "M-02": "#eb6834", "M-03": "#1baf7a"}
FALLBACK_COLOUR = "#4a3aa7"

# Reserved for state, never for a series.
STATUS_GOOD = "#0ca30c"
STATUS_WARNING = "#fab219"
STATUS_SERIOUS = "#ec835a"
STATUS_CRITICAL = "#d03b3b"

GOOD_UNITS_COLOUR = "#9ec5f4"
REJECT_COLOUR = STATUS_CRITICAL


def colour_for(machine_id: str) -> str:
    return MACHINE_COLOUR.get(machine_id, FALLBACK_COLOUR)


def severity_band(severity: float) -> tuple[str, str]:
    """Map a severity to a reserved status colour and a word.

    The word is not decoration. A status colour never carries meaning on its
    own -- roughly one reader in twelve cannot separate these four hues.
    """
    if severity >= 0.75:
        return STATUS_CRITICAL, "critical"
    if severity >= 0.5:
        return STATUS_SERIOUS, "serious"
    if severity >= 0.25:
        return STATUS_WARNING, "warning"
    return STATUS_GOOD, "minor"


# --- data ----------------------------------------------------------------


@st.cache_data(ttl=60, show_spinner=False)
def fetch(path: str, **params) -> list[dict]:
    """GET a route on the API and hand back its JSON.

    Cached for a minute: a supervisor changing the machine filter should not
    make the service re-read a month of data every click.
    """
    # ── CORE 1 ──────────────────────────────────────────── about 5 minutes ──
    #
    # WRITE
    #   One HTTP GET. Three lines. This is the only networking in the file.
    #
    #   httpx.get(url, params=params, timeout=...)  sends the request
    #   .raise_for_status()   turns a 404 or a 500 into an exception, instead of
    #                         letting a broken response reach your charts as an
    #                         innocent-looking empty table
    #   .json()               gives you plain Python lists and dicts
    #
    # WATCH OUT
    #   Build the URL from API_BASE. Never hardcode localhost -- inside a
    #   container the API is not on localhost, and Friday's docker-compose sets
    #   that variable to something else.
    #
    # HINT 1  response = httpx.get(f"{API_BASE}{path}", params=params,
    #                              timeout=REQUEST_TIMEOUT_S)
    # HINT 2  then response.raise_for_status(), then return response.json()
    #
    # DONE WHEN
    #   The page loads and the sidebar says how many readings the API holds.
    #
    # STUCK AFTER 15 MINUTES?
    #   in the course folder:  git checkout end/s2-5
    #   then copy dashboard/app.py over yours, and commit it.


    response = httpx.get(
        f"{API_BASE}{path}",
        params=params,
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json()


def api_is_up() -> tuple[bool, str]:
    try:
        health = fetch("/health")
    except httpx.HTTPError as error:
        return False, f"{type(error).__name__}: {error}"
    if not health.get("rows_loaded"):
        return False, "The API is running but loaded 0 rows. Check where it is looking for the CSV."
    return True, f"{health['rows_loaded']:,} readings loaded"


# --- charts --------------------------------------------------------------


def _style(figure: go.Figure, y_title: str) -> go.Figure:
    """Recessive chrome. The data is the only thing with contrast."""
    figure.update_layout(
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        margin=dict(l=8, r=96, t=8, b=8),
        height=340,
        hovermode="x unified",
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif', color=INK_SECONDARY),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, bgcolor="rgba(0,0,0,0)"),
    )
    figure.update_xaxes(showgrid=False, linecolor=AXIS, tickcolor=AXIS, tickfont_color=INK_MUTED)
    figure.update_yaxes(
        title=dict(text=y_title, font=dict(color=INK_MUTED, size=12)),
        gridcolor=GRID,
        zerolinecolor=AXIS,
        linecolor="rgba(0,0,0,0)",
        tickfont_color=INK_MUTED,
    )
    return figure


def oee_over_time(kpis: pd.DataFrame) -> go.Figure:
    """One line per machine. Identity is carried by colour, legend AND end label."""
    figure = go.Figure()
    for machine_id in sorted(kpis.machine_id.unique()):
        series = kpis[kpis.machine_id == machine_id].sort_values("bucket_start")
        colour = colour_for(machine_id)
        figure.add_trace(
            go.Scatter(
                x=series.bucket_start,
                y=series.oee,
                name=machine_id,
                mode="lines",
                line=dict(color=colour, width=2),
                connectgaps=False,  # a gap is missing data, not a straight line
                hovertemplate="%{y:.1%}<extra>" + machine_id + "</extra>",
            )
        )
        labelled = series.dropna(subset=["oee"])
        if not labelled.empty:
            figure.add_annotation(
                x=labelled.bucket_start.iloc[-1],
                y=labelled.oee.iloc[-1],
                text=f" {machine_id}",
                showarrow=False,
                xanchor="left",
                font=dict(color=INK_SECONDARY, size=12),
            )

    figure.update_yaxes(tickformat=".0%", rangemode="tozero")
    return _style(figure, "OEE")


def units_per_bucket(kpis: pd.DataFrame) -> go.Figure:
    """Good vs rejected units. Two parts of one whole, so: stacked, not grouped."""
    totals = (
        kpis.groupby("bucket_start", as_index=False)[["units_produced", "units_rejected"]]
        .sum()
        .sort_values("bucket_start")
    )
    good = totals.units_produced - totals.units_rejected

    figure = go.Figure()
    for name, values, colour in (
        ("Good units", good, GOOD_UNITS_COLOUR),
        ("Rejected", totals.units_rejected, REJECT_COLOUR),
    ):
        figure.add_trace(
            go.Bar(
                x=totals.bucket_start,
                y=values,
                name=name,
                marker=dict(color=colour, line=dict(color=SURFACE, width=2)),
                hovertemplate="%{y:,.0f}<extra>" + name + "</extra>",
            )
        )

    figure.update_layout(barmode="stack", bargap=0.15)
    return _style(figure, "Units")


# --- page ----------------------------------------------------------------

st.set_page_config(page_title="FactoryFlow - Line A", page_icon="=", layout="wide")

st.title("Line A")
st.caption("Overall Equipment Effectiveness, from the machine controllers.")

with st.sidebar:
    st.subheader("Filters")
    reachable, status_message = api_is_up()
    (st.success if reachable else st.error)(status_message)
    if not reachable:
        st.caption(f"Trying {API_BASE}. Is the API running?")
        st.stop()

    machine_ids = [machine["machine_id"] for machine in fetch("/machines")]
    chosen = st.multiselect("Machines", machine_ids, default=machine_ids)
    freq = st.select_slider("Time bucket", options=["15min", "1h", "8h"], value="1h")
    window = st.date_input(
        "Period", value=(date(2026, 3, 1), date(2026, 3, 31)), format="YYYY-MM-DD"
    )
    min_severity = st.slider(
        "Minimum anomaly severity",
        0.0,
        1.0,
        0.5,
        0.05,
        help="Raise this until the list is short enough to act on.",
    )

if not chosen:
    st.info("Pick at least one machine.")
    st.stop()

start, end = window if isinstance(window, tuple) and len(window) == 2 else (window[0], window[0])

# ── CORE 2 ─────────────────────────────────────────────── about 15 minutes ──
#
# WRITE
#   Fetch the KPI rows for every selected machine and stack them into one
#   frame called `kpis`. Everything below this block expects that name.
#
#   fetch("/metrics", machine=..., freq=...)  -> a list of dicts
#   pd.DataFrame(that_list)                   -> a frame
#   pd.concat([...], ignore_index=True)       -> the frames stacked
#
# WATCH OUT
#   `from` is a Python keyword, so `from=...` will not parse as an argument.
#   Pass it through a dict instead: `**{"from": str(start), "to": str(end)}`.
#   Skip empty frames before you concatenate, or pandas will warn at you.
#
# HINT 1  A loop or a list comprehension over `chosen`, one fetch each, then
#         one concat. Four lines is plenty.
# HINT 2  frames = [pd.DataFrame(fetch("/metrics", machine=machine_id,
#                                      freq=freq,
#                                      **{"from": str(start), "to": str(end)}))
#                   for machine_id in chosen]
# HINT 3  kpis = pd.concat([f for f in frames if not f.empty],
#                          ignore_index=True)
#
# DONE WHEN
#   The four tiles at the top show percentages, and the OEE chart draws one
#   line per selected machine.
#
# STUCK AFTER 15 MINUTES?
#   in the course folder:  git checkout end/s2-5
#   then copy dashboard/app.py over yours, and commit it.
frames = [
    pd.DataFrame(
        fetch(
            "/metrics",
            machine=machine_id,
            freq=freq,
            **{"from": str(start), "to": str(end)},
        )
    )
    for machine_id in chosen
]

non_empty = [frame for frame in frames if not frame.empty]
kpis = pd.concat(non_empty, ignore_index=True) if non_empty else pd.DataFrame()

if kpis.empty:
    st.warning("No data in that window.")
    st.stop()

kpis["bucket_start"] = pd.to_datetime(kpis.bucket_start)

# --- headline numbers ----------------------------------------------------
# Four stat tiles, not four charts: a single number does not need axes.
# Weighted by minutes and units, never a mean of ratios -- averaging
# percentages over unequal buckets is how a report starts lying quietly.

run_minutes = kpis.run_minutes.sum()
planned_minutes = kpis.planned_minutes.sum()
produced = kpis.units_produced.sum()
rejected = kpis.units_rejected.sum()

availability = run_minutes / planned_minutes if planned_minutes else float("nan")
performance = (4.0 * produced) / (run_minutes * 60) if run_minutes else float("nan")
quality = (produced - rejected) / produced if produced else float("nan")

for column, (label, value, note) in zip(
    st.columns(4),
    [
        ("OEE", availability * performance * quality, "availability x performance x quality"),
        ("Availability", availability, f"{run_minutes:,.0f} of {planned_minutes:,.0f} planned min"),
        ("Performance", performance, f"{produced:,.0f} units"),
        ("Quality", quality, f"{rejected:,.0f} rejected"),
    ],
    strict=True,
):
    column.metric(label, "n/a" if pd.isna(value) else f"{value:.1%}", help=note)
    column.caption(note)

st.subheader("OEE over time")
st.plotly_chart(oee_over_time(kpis), width="stretch")

st.subheader("Output")
st.plotly_chart(units_per_bucket(kpis), width="stretch")

# The table view is not a fallback. It is how anyone who cannot separate three
# hues -- or who needs the exact number -- reads this page.
with st.expander("Show the numbers"):
    st.dataframe(
        kpis.sort_values(["machine_id", "bucket_start"]),
        width="stretch",
        hide_index=True,
    )

# --- anomalies -----------------------------------------------------------

st.subheader("Worth a look")
episodes = pd.DataFrame(fetch("/anomalies", min_severity=min_severity))
episodes = episodes[episodes.machine_id.isin(chosen)] if not episodes.empty else episodes

if episodes.empty:
    st.success(f"Nothing above severity {min_severity:.2f} in the selected machines.")
else:
    st.caption(f"{len(episodes)} episodes. A flag is a request for a human to look, not a fault.")
    episodes = episodes.copy()
    episodes["band"] = [severity_band(value)[1] for value in episodes.severity]
    st.dataframe(
        episodes[["timestamp", "machine_id", "kind", "band", "value", "duration_min", "severity"]],
        width="stretch",
        hide_index=True,
        column_config={
            "severity": st.column_config.ProgressColumn(
                "severity", min_value=0.0, max_value=1.0, format="%.2f"
            ),
            "duration_min": st.column_config.NumberColumn("duration", format="%d min"),
        },
    )

# ══ BONUS ══════════════════════════════════════════════════════════════════
#
#   Commit the working page first. Then pick ONE and finish it, rather than
#   three and none. Anything you build here is what you demo on Friday.
#
#   B1  THE SUPERVISOR'S ONE SCREEN. Delete everything that is not one of the
#       five numbers. No scrolling, no tabs, readable from two metres away.
#       This is the hardest one on the list and the best one to demo.
#
#   B2  A RED LINE. Draw the target OEE across the chart so the number has
#       something to be compared against. A percentage on its own is trivia;
#       a percentage against a target is information.
#
#   B3  WORST HOUR FIRST. Add a small table: the three worst buckets in the
#       window, with what dragged each one down -- availability, performance
#       or quality. That is the answer to "so what do I do about it?".
#
#   B4  FRESHNESS. Show how old the newest reading is, and turn the indicator
#       amber past an hour. A dashboard confidently showing yesterday is worse
#       than one that is visibly down.
#
#   B5  DOWNLOAD. `st.download_button` with the current selection as CSV. Two
#       lines, and it is the feature real users ask for first.
#
#   B6  SHOW IT TO ANOTHER PAIR. No explaining, no pointing. Ask them what the
#       line did last Tuesday and watch where they look first. Fix whatever
#       made them hesitate. This counts as a bonus, and it is worth more than
#       any chart on this list.
# ═══════════════════════════════════════════════════════════════════════════
