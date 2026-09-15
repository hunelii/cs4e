"""OEE and its three factors.

    OEE = Availability x Performance x Quality

    Availability = run_time / planned_production_time
    Performance  = (ideal_cycle_time_s x total_units) / run_time
    Quality      = good_units / total_units

Every function here takes a frame of per-minute readings and returns one number.
That is the whole contract, and it is what makes the same four functions usable
for a single machine, a single shift, or the entire month.

On undefined results. A metric of nothing is not zero and it is not an error --
an idle night shift produced no units, and asking for its quality is a fair
question with no answer. These functions return `float("nan")` in that case.
NaN propagates through arithmetic, survives aggregation, and prints as an empty
cell in a report, which is exactly the behaviour you want. Returning 0.0 would
quietly drag every average down; raising would make the KPI table impossible to
build.
"""

from __future__ import annotations

import math

import pandas as pd

from factoryflow import config

# ══ THIS SESSION ═══════════════════════════════════════════════════════════
#
#   CORE 1  loading.load_readings()   read the CSV            ~10 min
#   CORE 2  availability()            below                   ~10 min
#   CORE 3  performance()             below                   ~10 min
#   CORE 4  oee()                     below                    ~5 min
#
#   quality() is already written. It is the function the facilitator built on
#   the projector -- read it before you start, the other three follow the same
#   shape.
#
#   Finished early? The BONUS list is at the bottom of this file. Commit the
#   core first, then take one. Do not start a bonus with an unfinished core.
#
#   Every task below has a HINT ladder. Use them in order and use them early --
#   they are there to be used.
# ═══════════════════════════════════════════════════════════════════════════


def _minutes_in_state(readings: pd.DataFrame, states: frozenset[str] | set[str]) -> int:
    """How many readings -- and therefore minutes -- were spent in these states."""
    return int(readings["machine_state"].isin(states).sum())


def availability(readings: pd.DataFrame) -> float:
    """Share of planned production time the machine was actually running.

    Planned production time excludes SETUP: a changeover is planned work, so it
    is not held against the machine. See `config.PLANNED_STATES`.

    Args:
        readings: per-minute readings, cleaned.

    Returns:
        A value in [0, 1], or NaN if there was no planned production time at all.
    """
    # ── CORE 2 ─────────────────────────────────────────── about 10 minutes ──
    #
    # WRITE
    #   Run time divided by planned production time. Three lines.
    #
    # YOU ALREADY HAVE
    #   _minutes_in_state(readings, states)  counts rows, and one row is one
    #                                        minute, so it counts minutes
    #   config.PLANNED_STATES                the states that count as planned
    #   config.PRODUCING_STATE               the one state that counts as running
    #
    # WATCH OUT
    #   No planned production time at all -> return `math.nan`, not 0.0. Zero
    #   claims the machine was available and did not run. NaN says "this bucket
    #   cannot be judged", which is the truth.
    #
    # HINT 1  Count twice, divide once. No time arithmetic anywhere.
    # HINT 2  planned_minutes = _minutes_in_state(readings, config.PLANNED_STATES)
    # HINT 3  run_minutes = _minutes_in_state(readings, {config.PRODUCING_STATE})
    #         ...then the nan check, then `return run_minutes / planned_minutes`.
    #         Note the braces: PRODUCING_STATE is one string, the helper wants a set.
    #
    # DONE WHEN
    #   uv run python -m factoryflow oee
    #   prints availability 0.8772 (M-01) · 0.8349 (M-02) · 0.8559 (M-03).
    #
    # STUCK AFTER 15 MINUTES? Take the finished version, no questions asked:
    #   in the course folder:  git checkout end/s1-4
    #   then copy src/factoryflow/metrics.py over yours, and commit it.
    # TODO(EXPLAIN): Why is SETUP left out of planned production time, and who could
    # reasonably disagree?
    # Two or three sentences, in your own words. Not what the code
    # does line by line -- why it does it that way.
    #
    # Your answer:
    #
    # TODO(L2): write the body here. The brief is above.
    raise NotImplementedError("S1.4")


def performance(readings: pd.DataFrame, ideal_cycle_time_s: float | None = None) -> float:
    """Share of the theoretical output the machine achieved while running.

    A machine that could make one unit every 4 seconds but averaged one every
    5 is performing at 80 %, even though it never stopped.

    Args:
        readings: per-minute readings, cleaned.
        ideal_cycle_time_s: seconds per unit at 100 %. Defaults to
            `config.IDEAL_CYCLE_TIME_S`.

    Returns:
        A value in [0, 1] under normal conditions, or NaN if the machine never
        ran. Values slightly above 1.0 are possible and mean the ideal cycle
        time is wrong, not that the machine is magic.
    """
    # ── CORE 3 ─────────────────────────────────────────── about 10 minutes ──
    #
    # WRITE
    #   The last two lines only. Everything above them is already here.
    #
    #       performance = (ideal_cycle_time_s * total_units) / run_time_IN_SECONDS
    #
    # WATCH OUT -- this is the one trap in the session
    #   `run_minutes` is a count of ROWS, and one row is one MINUTE. The formula
    #   wants SECONDS. Multiply by config.SAMPLE_INTERVAL_S (= 60) first.
    #   Forget it and you get 0.0138 instead of 0.83. Multiply on the wrong side
    #   and you get 49.6. Both are the same mistake, and both look like a typo
    #   rather than a unit error -- which is why unit errors survive to production.
    #
    # HINT 1  Two lines: one that converts minutes to seconds, one that returns.
    # HINT 2  run_seconds = run_minutes * config.SAMPLE_INTERVAL_S
    # HINT 3  return (ideal_cycle_time_s * total_units) / run_seconds
    #
    # DONE WHEN
    #   uv run python -m factoryflow oee
    #   prints performance 0.8274 (M-01) · 0.8396 (M-02) · 0.8308 (M-03).
    #   Anything near 50 or near 0.01 is the unit error above.
    #
    # STUCK AFTER 15 MINUTES?
    #   in the course folder:  git checkout end/s1-4
    #   then copy src/factoryflow/metrics.py over yours, and commit it.
    if ideal_cycle_time_s is None:
        ideal_cycle_time_s = config.IDEAL_CYCLE_TIME_S

    run_minutes = _minutes_in_state(readings, {config.PRODUCING_STATE})
    if run_minutes == 0:
        return math.nan

    total_units = int(readings["units_produced"].sum())
    # TODO(L1): minutes -> seconds, then (ideal_cycle_time_s * total_units) / run_seconds


def quality(readings: pd.DataFrame) -> float:
    """Share of produced units that were not rejected.

    Args:
        readings: per-minute readings, cleaned.

    Returns:
        A value in [0, 1], or NaN if nothing was produced.

        A result above 1.0 is arithmetically impossible and means the input was
        not cleaned: the raw export contains rows where `units_rejected` exceeds
        `units_produced`. That is the bug that reported 104 % for a week.
    """
    # ── WORKED EXAMPLE -- nothing to write here ──────────────────────────────
    #
    #   This is the function the facilitator refactored on the projector, out of
    #   this line of the legacy script:
    #
    #       if a[i][3] > 0.85 and x1 != 0: q = (x1 - a[i][4]) / x1
    #
    #   Read it before you start on the others. Three things to notice, because
    #   the other three functions do all three as well:
    #
    #     1. The names say what the numbers are. `total_units`, not `x1`.
    #     2. The guard comes before the division, not after the crash.
    #     3. The docstring says what comes out, including what comes out when
    #        the answer does not exist.
    #
    #   Rejected units are a SUBSET of produced ones, not an addition to them --
    #   so good units are produced minus rejected, and the denominator is
    #   produced. A result above 1.0 is arithmetically impossible and means the
    #   data was not cleaned. That is the 104 % bug, and it is day 2's job.
    # TODO(EXPLAIN): An idle night shift produced nothing. Why does this return NaN instead
    # of 0.0?
    # Two or three sentences, in your own words. Not what the code
    # does line by line -- why it does it that way.
    #
    # Your answer:
    #
    total_units = int(readings["units_produced"].sum())
    if total_units == 0:
        return math.nan
    rejected_units = int(readings["units_rejected"].sum())
    return (total_units - rejected_units) / total_units


def oee(readings: pd.DataFrame, ideal_cycle_time_s: float | None = None) -> float:
    """Overall Equipment Effectiveness: availability x performance x quality.

    Args:
        readings: per-minute readings, cleaned.
        ideal_cycle_time_s: seconds per unit at 100 %. Defaults to
            `config.IDEAL_CYCLE_TIME_S`.

    Returns:
        A value in [0, 1], or NaN if any factor is undefined. World-class is
        around 0.85; this line runs in the high sixties.
    """
    # ── CORE 4 ──────────────────────────────────────────── about 5 minutes ──
    #
    # WRITE
    #   One line: the three factors above, multiplied.
    #
    #   It is a one-line function on purpose. It exists so that the word "OEE"
    #   appears in the code by name, instead of as an unexplained product buried
    #   somewhere in a report.
    #
    # WATCH OUT
    #   Pass `ideal_cycle_time_s` through to performance(). Forgetting it is the
    #   classic slip: the function silently uses the default and the caller's
    #   argument is quietly ignored -- no error, just a different number.
    #   Do not special-case NaN. NaN times anything is NaN, which is exactly the
    #   right answer for a bucket that cannot be judged.
    #
    # HINT 1  availability(...) * performance(...) * quality(...)
    # HINT 2  Only performance() takes a second argument.
    #
    # DONE WHEN
    #   uv run python -m factoryflow oee
    #   prints oee 0.7032 (M-01) · 0.6723 (M-02) · 0.6853 (M-03).
    #   Those three numbers are the whole point of the tool -- check them.
    #
    # STUCK AFTER 15 MINUTES?
    #   in the course folder:  git checkout end/s1-4
    #   then copy src/factoryflow/metrics.py over yours, and commit it.
    # TODO(L1): the three factors multiplied; pass ideal_cycle_time_s to performance()


# ══ BONUS ══════════════════════════════════════════════════════════════════
#
#   Only once the four core tasks run and are committed. Pick one.
#
#   B1  Guard the inputs. What should availability() do if it is handed a frame
#       with no `machine_state` column at all -- crash, or say something useful?
#       Write the check and the message you would want to read at 03:00.
#
#   B2  Add `def oee_factors(readings) -> dict[str, float]` returning all four
#       numbers at once. The CLI prints them one by one today; make it possible
#       to get them in a single call without computing anything twice.
#
#   B3  SETUP is excluded from planned production time (see config.py). Add an
#       argument that lets a caller include it, keeping today's behaviour as the
#       default. Then run both ways and write down, in a comment, how much
#       availability moves.
#
#   B4  Take the printed table apart in cli.py and make it readable at a glance:
#       percentages instead of four decimals, aligned columns, worst machine
#       first. Show it to another pair before you decide you are done.
# ═══════════════════════════════════════════════════════════════════════════
