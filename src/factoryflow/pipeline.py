"""From a raw export to a KPI table.

Three steps, deliberately separate:

    clean()             decide what the messy rows mean
    resample_readings() bucket them in time, per machine
    kpi_table()         turn buckets into the four numbers a supervisor reads

`clean()` is where the judgement calls live. Every one of them is commented with
what was decided and why, because in six months the comment is the only record
of the decision.
"""

from __future__ import annotations

import pandas as pd

from factoryflow import config

#: Machine ids arrive from three different subsystems with three different
#: spellings. Anything shaped like M-1 / m-01 / ' M-01' collapses to M-01.
_MACHINE_ID_PATTERN = r"^M-?(\d+)$"

# ══ THIS SESSION ═══════════════════════════════════════════════════════════
#
#   CORE 1  resample_readings()   two columns, in this file        ~15 min
#   CORE 2  kpi_table()           four columns, in this file       ~25 min
#   CORE 3  stuck_sensor()        one line, in anomalies.py        ~10 min
#
#   clean() is already written -- it is the function that was built on the
#   projector. rolling_zscore() and detect() in anomalies.py are given complete
#   as well; you are meant to read those two, not write them.
#
#   Do the two in this file first, in order. A pair who finishes only CORE 1
#   and CORE 2 has had a good session -- the dashboard tomorrow needs the KPI
#   table, not the detectors.
#
#   Every task has a HINT ladder. Use it early. The BONUS list is at the bottom
#   of anomalies.py.
# ═══════════════════════════════════════════════════════════════════════════


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    """Turn the raw export into something you can compute on.

    The decisions taken here, in order, each answering a real defect in the file:

    1. Machine ids are stripped, upper-cased and zero-padded.
    2. Temperatures written with a decimal comma are re-parsed as floats.
       Anything still unparseable becomes NaN -- an unknown temperature is not
       a zero temperature.
    3. Timestamps are read as UTC. The export writes them without a timezone
       suffix, which makes them look local. They are not. Getting this wrong
       moves every shift boundary by an hour after the DST switch.
    4. Exact duplicate rows are dropped.
    5. Where the same machine-minute appears twice with *different* readings,
       the first is kept.

       There is no correct answer here. Keep first, keep last, average, or drop
       the pair -- each is defensible and each changes the reported number. We
       keep the first because the second write is more likely to be the retry of
       a subsystem that already reported once. It is a guess. It is written down.

    6. Negative unit counts are a rolled-over counter, not negative production.
       They are clipped to zero. The minute itself still happened, so the row
       stays and availability is unaffected.
    7. You cannot reject more units than you made. Rejects are capped at
       production. This is the arithmetic that made the report say 104 %.

    Args:
        raw: the frame returned by `loading.load_readings`.

    Returns:
        A new frame, sorted by machine and time, with a UTC-aware `timestamp`.
        The input is not modified.
    """
    # ── WORKED EXAMPLE -- nothing to write here ──────────────────────────────
    #
    #   This is the function the facilitator wrote on the projector against the
    #   real, dirty export, one defect at a time. You have it complete so that
    #   nobody is blocked on it -- but read the seven numbered decisions in the
    #   docstring above before you go on. Every one of them changes the reported
    #   number, and every one of them is written down for exactly that reason.
    #
    #   Decision 5 is the one to look at twice. Twelve machine-minutes appear
    #   with two different readings. There is no correct answer, so the code
    #   records which guess was made.
    readings = raw.copy()

    # 1. machine ids (F-5)
    machine_ids = readings["machine_id"].astype(str).str.strip().str.upper()
    readings["machine_id"] = machine_ids.str.replace(
        _MACHINE_ID_PATTERN, lambda match: f"M-{int(match.group(1)):02d}", regex=True
    )

    # 2. temperatures (F-11, F-4)
    temperatures = readings["temperature_c"].astype(str).str.replace(",", ".", regex=False)
    readings["temperature_c"] = pd.to_numeric(temperatures, errors="coerce")

    # 3. timestamps are UTC, whatever the file suggests
    readings["timestamp"] = _as_utc(readings["timestamp"])

    # region explain session=S2.2 ask="Twelve machine-minutes have two different readings. We keep the first. Name one situation where that is the wrong call."  # noqa: E501
    # Keeping the first assumes the second write is a retry of a subsystem that
    # already reported. If instead the second write is a correction -- an
    # operator fixing a miskeyed reject count an hour later -- then keeping the
    # first keeps the wrong number, and the report is confidently wrong rather
    # than obviously broken. Twelve rows will not move the monthly figure; the
    # reason to write this down is that the same rule applied to twelve thousand
    # rows would, and nobody would know which choice had been made.
    # 4. and 5. duplicates (F-1, F-2). The sort must be stable, otherwise
    # "keep the first" stops meaning "keep the original".
    readings = readings.drop_duplicates()
    readings = readings.sort_values(["machine_id", "timestamp"], kind="mergesort")
    readings = readings.drop_duplicates(subset=["machine_id", "timestamp"], keep="first")

    # 6. and 7. impossible counts (F-6, F-8)
    readings["units_produced"] = readings["units_produced"].fillna(0).clip(lower=0).astype("int64")
    readings["units_rejected"] = (
        readings[["units_produced", "units_rejected"]].min(axis=1).fillna(0).clip(lower=0)
    ).astype("int64")

    return readings.reset_index(drop=True)
    # endregion


def _as_utc(timestamps: pd.Series) -> pd.Series:
    """Interpret the timestamp column as UTC, whether or not it says so.

    The export writes `2026-03-29T02:00:00` with no offset. Reading that as
    local time is the single most expensive mistake available in this codebase:
    Europe/Berlin has no 02:00 on that date, and every shift boundary after it
    lands an hour off.
    """
    parsed = pd.to_datetime(timestamps, errors="coerce")
    if parsed.dt.tz is None:
        return parsed.dt.tz_localize("UTC")
    return parsed.dt.tz_convert("UTC")


def _validate_freq(freq: str) -> None:
    if freq not in config.ALLOWED_FREQS:
        raise ValueError(
            f"freq must be one of {config.ALLOWED_FREQS}, got {freq!r}. "
            "Buckets shorter than 15 min contain too few readings to mean anything."
        )


def resample_readings(clean_df: pd.DataFrame, freq: str = config.DEFAULT_FREQ) -> pd.DataFrame:
    """Bucket readings in time, per machine.

    Args:
        clean_df: output of `clean()`.
        freq: bucket size, one of `config.ALLOWED_FREQS`.

    Returns:
        One row per (machine, bucket) with the raw ingredients of the KPIs:
        minutes run, minutes of planned production time, units, rejects, and the
        mean of each sensor. Buckets with no readings at all do not appear --
        the machine was offline and inventing zeroes for it would be a lie.

    Raises:
        ValueError: if `freq` is not an allowed bucket size.
    """
    # ── CORE 1 ─────────────────────────────────────────── about 15 minutes ──
    #
    # WRITE
    #   Two lines, marked TODO(L1) below. The groupby underneath them is already
    #   written -- read it, then make the two columns it needs.
    #
    # THE IDEA
    #   You want to know how many minutes of each bucket the machine spent
    #   running. There is one row per minute, so that is a count of rows where
    #   machine_state == "RUN". Counting rows that match a condition, without a
    #   loop, is a two-step move you will use all day:
    #
    #       condition  ->  True/False per row     df["machine_state"].eq("RUN")
    #       .astype("int64")  ->  1/0 per row
    #       ...and now "sum" counts them.
    #
    #   Same again for planned production time, except that is a SET of states,
    #   so `.isin(config.PLANNED_STATES)` instead of `.eq(...)`.
    #
    # WATCH OUT
    #   `clean_df.copy()` is already done for you above and it matters: without
    #   it you would be adding columns to the caller's frame, and pandas would
    #   warn at you in a way that eats twenty minutes.
    #
    # HINT 1  Two lines, both of the shape
    #             readings["<name>"] = <condition>.astype("int64")
    #         The names must be `run_minutes` and `planned_minutes` -- the
    #         .agg() below already refers to them.
    # HINT 2  readings["run_minutes"] = (
    #             readings["machine_state"].eq(config.PRODUCING_STATE).astype("int64"))
    # HINT 3  readings["planned_minutes"] = (
    #             readings["machine_state"].isin(config.PLANNED_STATES).astype("int64"))
    #
    # DONE WHEN
    #   uv run python -m factoryflow kpis --freq 1h
    #   prints 2232 buckets (3 machines x 744 hours).
    #
    # STUCK AFTER 15 MINUTES?
    #   in the course folder:  git checkout end/s2-2
    #   then copy src/factoryflow/pipeline.py over yours, and commit it.
    _validate_freq(freq)

    readings = clean_df.copy()
    # TODO(L1): run_minutes and planned_minutes as 1/0 columns, then .astype('int64')
    readings["run_minutes"] = readings["machine_state"].eq(config.PRODUCING_STATE).astype("int64")
    readings["planned_minutes"] = readings["machine_state"].isin(config.PLANNED_STATES).astype("int64")
    # Group by two things at once: the machine, and the time bucket. pd.Grouper
    # only works on the index, which is why the timestamp is moved there first.
    buckets = (
        readings.set_index("timestamp")
        .sort_index()
        .groupby(["machine_id", pd.Grouper(freq=freq)])
        .agg(
            readings=("machine_state", "size"),
            run_minutes=("run_minutes", "sum"),
            planned_minutes=("planned_minutes", "sum"),
            units_produced=("units_produced", "sum"),
            units_rejected=("units_rejected", "sum"),
            temperature_c=("temperature_c", "mean"),
            vibration_mm_s=("vibration_mm_s", "mean"),
            power_kw=("power_kw", "mean"),
        )
    )

    # A bucket with no readings at all means the machine was offline. Inventing
    # zeroes for it would be a lie, so it does not appear. Note what is NOT
    # here: nothing drops the last bucket of the month for being "incomplete".
    # That temptation is one of Thursday's three bugs.
    buckets = buckets[buckets["readings"] > 0]
    return buckets.reset_index().rename(columns={"timestamp": "bucket_start"})


def kpi_table(
    clean_df: pd.DataFrame,
    freq: str = config.DEFAULT_FREQ,
    ideal_cycle_time_s: float | None = None,
) -> pd.DataFrame:
    """One row per (machine, bucket) with availability, performance, quality and OEE.

    Same four formulas as `metrics.py`, applied to many buckets at once instead
    of one frame at a time. `tests/test_pipeline.py` asserts the two agree; if
    you change a formula in one place, that test is what tells you.

    Args:
        clean_df: output of `clean()`.
        freq: bucket size, one of `config.ALLOWED_FREQS`.
        ideal_cycle_time_s: seconds per unit at 100 %. Defaults to
            `config.IDEAL_CYCLE_TIME_S`.

    Returns:
        Columns: machine_id, bucket_start, availability, performance, quality,
        oee, units_produced, units_rejected, run_minutes, planned_minutes.
        A metric is NaN where its denominator is zero -- see `metrics` for why
        that is not zero and not an error.
    """
    # ── CORE 2 -- this is the session ──────────────────── about 25 minutes ──
    #
    # WRITE
    #   Four lines: availability, performance, quality, oee -- as columns.
    #   Everything around them is set up for you.
    #
    # THE ONLY NEW IDEA
    #   These are the SAME four formulas you wrote yesterday. Yesterday each one
    #   took a frame and gave back one number. Today you write the same formula
    #   once and get 2232 answers, because dividing two COLUMNS divides row by
    #   row, all at once, with no loop:
    #
    #       table["run_minutes"] / table["planned_minutes"]     <- 2232 divisions
    #
    #   That is the whole of vectorisation, and it is why the loop in the legacy
    #   script did not need to exist.
    #
    # WATCH OUT -- the trap that ate a week of reports
    #   Dividing by zero in pandas does not raise. It gives you `inf`, and `inf`
    #   times anything is still `inf`, so one idle night shift poisons the
    #   monthly average without a single error message. Yesterday you wrote
    #   `if total == 0: return nan` -- you cannot write an `if` for 2232 rows at
    #   once, so pandas gives you this instead:
    #
    #       (a / b).where(b > 0)     -> NaN wherever b is zero
    #
    #   Use it on all three factors. `oee` needs no guard: NaN times anything is
    #   already NaN.
    #
    # HINT 1  Four lines of the shape  table["<name>"] = ...
    #         Two variables are already computed for you above: `run_seconds`
    #         and `good_units`. Use them.
    # HINT 2  table["availability"] = (
    #             table["run_minutes"] / table["planned_minutes"]
    #         ).where(table["planned_minutes"] > 0)
    # HINT 3  quality  = good_units / table["units_produced"],  guarded on
    #                    table["units_produced"] > 0
    #         performance = (ideal_cycle_time_s * table["units_produced"])
    #                       / run_seconds,  guarded on table["run_minutes"] > 0
    #         oee = the three columns multiplied, no guard.
    #
    # DONE WHEN
    #   uv run python -m factoryflow kpis --freq 8h --machine M-02
    #   prints a table whose oee column sits mostly between 0.5 and 0.8.
    #   Whole-month sanity check: OEE per machine lands in 0.62-0.71. Above 0.9
    #   or below 0.3 is a bug -- start by looking at PLANNED_STATES.
    #
    # STUCK AFTER 15 MINUTES?
    #   in the course folder:  git checkout end/s2-2
    #   then copy src/factoryflow/pipeline.py over yours, and commit it.
    if ideal_cycle_time_s is None:
        ideal_cycle_time_s = config.IDEAL_CYCLE_TIME_S

    table = resample_readings(clean_df, freq)

    run_seconds = table["run_minutes"] * config.SAMPLE_INTERVAL_S
    good_units = table["units_produced"] - table["units_rejected"]

    # TODO(L1): the 4 metric columns; guard each division with .where(denom > 0)

    return table[
        [
            "machine_id",
            "bucket_start",
            "availability",
            "performance",
            "quality",
            "oee",
            "units_produced",
            "units_rejected",
            "run_minutes",
            "planned_minutes",
        ]
    ]
