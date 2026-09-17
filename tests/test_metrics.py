"""Tests for the four metric functions.

A test is not there to prove the code works. It is there to pin down behaviour
so that the next person -- including you, in March -- cannot change it by
accident. Every test below corresponds to a decision somebody made.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from factoryflow import metrics

# ══ THIS SESSION ═══════════════════════════════════════════════════════════
#
#   CORE  Five assertions. Four in this file, one in test_pipeline.py. They
#         are the ones that say `raise AssertionError("not implemented")`.
#
#   Every other test in tests/ is already written. Those are not decoration --
#   they are your reference. Whatever shape you need, one of them has it
#   already, and reading three finished tests is faster than remembering the
#   syntax for one.
#
#   BONUS is at the bottom of this file.
#
# THE WHOLE OF PYTEST, HONESTLY
#   `assert <something true>` -- that is it. There is no framework to learn.
#   `pytest` finds every file called test_*.py and runs every function called
#   test_*. A test passes if it does not raise.
#
# THE FOUR THINGS YOU WILL NEED
#   Floats never compare equal:
#       assert metrics.quality(readings) == pytest.approx(0.9)
#   NaN is not equal to itself, so `== nan` never works:
#       assert math.isnan(result)
#   A fixture is just an argument. `sample_readings` in the signature means
#   "hand me the frame defined under that name in conftest.py". OPEN
#   conftest.py FIRST -- `sample_readings` is ten rows chosen so that every
#   expected value can be worked out on paper in ten seconds.
#   To assert that something is refused:
#       with pytest.raises(ValueError):
#           ...
#
# HOW TO WORK -- the rhythm matters more than the assertions
#   uv run pytest                  run everything
#   uv run pytest -k availability  run just the ones with that in the name
#   uv run pytest -x               stop at the first failure
#
#   Write the assertion, run it, WATCH IT FAIL, then make it pass. A test you
#   have never seen fail is not evidence of anything -- it may be asserting
#   nothing at all. If it passes the first time you run it, break the code on
#   purpose and check that it goes red.
#
# DONE WHEN
#   uv run pytest is green, with nothing left saying "not implemented".
#
# STUCK AFTER 15 MINUTES?
#   in the course folder:  git checkout end/s3-2
#   then copy tests/ over yours, and commit it.
# ═══════════════════════════════════════════════════════════════════════════


def test_availability_ignores_setup(sample_readings: pd.DataFrame) -> None:
    """SETUP is not held against the machine, so it leaves planned time.

    Six run minutes out of nine planned. If this comes out as 0.6, the SETUP
    minute is being counted as planned production time -- which is a defensible
    model, but not this one, and every downstream number moves with it.
    """
    assert metrics.availability(sample_readings) == pytest.approx(2 / 3)

def test_performance_uses_run_time_not_wall_clock(sample_readings: pd.DataFrame) -> None:
    """A machine is only judged on output while it was actually running."""
    assert metrics.performance(sample_readings, ideal_cycle_time_s=4.0) == pytest.approx(2 / 3)


def test_quality_counts_good_units(sample_readings: pd.DataFrame) -> None:
    assert metrics.quality(sample_readings) == pytest.approx(0.9)


def test_oee_is_the_product_of_the_three(sample_readings: pd.DataFrame) -> None:
    assert metrics.oee(sample_readings, ideal_cycle_time_s=4.0) == pytest.approx(0.4)


def test_quality_on_empty_bucket(idle_readings: pd.DataFrame) -> None:
    """Quality of nothing is unknown -- not zero, not infinity.

    This is the bug that put `inf` in a shift report. Dividing by a zero unit
    count gives infinity in floating point, and infinity times anything is still
    infinity, so a single idle night shift poisoned the monthly OEE.
    """
    assert math.isnan(metrics.quality(idle_readings))


def test_metrics_are_undefined_when_the_machine_never_ran(idle_readings: pd.DataFrame) -> None:
    """No run time means no performance figure, and NaN must propagate into OEE."""
    assert math.isnan(metrics.performance(idle_readings))
    assert math.isnan(metrics.oee(idle_readings))
    # Availability is still defined: the machine was available to run and did not.
    assert metrics.availability(idle_readings) == pytest.approx(0.0)


def test_availability_is_undefined_without_planned_time(sample_readings: pd.DataFrame) -> None:
    """A bucket that was entirely changeover has no planned production time."""
    all_setup = sample_readings.assign(machine_state="SETUP")
    assert math.isnan(metrics.availability(all_setup))


@pytest.mark.parametrize(
    ("rejected", "expected"),
    [(0, 1.0), (6, 0.9), (30, 0.5), (60, 0.0)],
)
def test_quality_across_reject_rates(
    sample_readings: pd.DataFrame, rejected: int, expected: float
) -> None:
    """Quality falls linearly with rejects and reaches exactly 0 and 1 at the ends."""
    readings = sample_readings.copy()
    readings.loc[readings.machine_state == "RUN", "units_rejected"] = rejected // 6
    assert metrics.quality(readings) == pytest.approx(expected)


# TODO(EXPLAIN): test_march_numbers_are_stable below hardcodes three numbers. Is that a good
# test or a fragile one?
# Two or three sentences, in your own words. Not what the code
# does line by line -- why it does it that way.
#
# Your answer:
# Hardcoding known-good March numbers is intentional here because the test
# protects important regression values. It is fragile if those numbers are
# legitimately changed, but that is useful because such a change should be reviewed.

def test_quality_never_exceeds_one_on_clean_data(real_readings: pd.DataFrame) -> None:
    """The 104 % bug, pinned down.

    The raw export contains rows where more units were rejected than produced.
    Cleaning caps them. If this ever fails, either cleaning regressed or someone
    fed the metrics raw data.
    """
    assert metrics.quality(real_readings) <= 1.0


def test_march_numbers_are_stable(real_readings: pd.DataFrame) -> None:
    """Regression guard against the known-good March figures.

    These come from facilitator/ground_truth.json, block `expected_after_cleaning`.
    Regenerating the dataset with a different seed will break this test on
    purpose -- the numbers are only meaningful for this exact export.
    """
    expected = {
        "M-01": 0.7032,
        "M-02": 0.6723,
        "M-03": 0.6853,
    }
    for machine_id, group in real_readings.groupby("machine_id"):
        assert metrics.oee(group) == pytest.approx(expected[machine_id], abs=5e-5)


def test_quality_never_exceeds_one_when_rejections_are_high() -> None:
    """Quality must never exceed 1 even when rejected units exceed produced."""
    readings = pd.DataFrame(
        {
            "units_produced": [10],
            "units_rejected": [12],
        }
    )
    assert metrics.quality(readings) <= 1.0


# ══ BONUS ══════════════════════════════════════════════════════════════════
#
#   Only once `uv run pytest` is green. Pick one.
#
#   B1  THE ONE THAT MATTERS MOST. Pick one of this morning's three bugs, put
#       it back into the code on purpose, and write the test that catches it.
#       Watch it go red. Then take the bug out again and watch it go green.
#       That test is now a regression test, and it is the only thing standing
#       between that bug and next March.
#
#   B2  Add a case to test_quality_across_reject_rates. Look at how
#       @pytest.mark.parametrize works there -- one line gives you a whole new
#       test. What is the nastiest pair of numbers you can put in it?
#
#   B3  Test something that should be REFUSED rather than answered. What does
#       resample_readings do with freq="3h"? There is already a test for that
#       in test_pipeline.py -- find it, then write one for another input that
#       ought to be refused and is not yet.
#
#   B4  uv run pytest --durations=5 tells you your five slowest tests. If any
#       one of them takes more than a second, work out why. A suite nobody
#       waits for is a suite nobody runs.
#
#   B5  Install coverage (`uv add --dev pytest-cov`) and run
#       `uv run pytest --cov=factoryflow`. Then find one line that coverage
#       calls tested and you would not call tested. That gap is the whole
#       argument about what coverage does and does not measure.
# ═══════════════════════════════════════════════════════════════════════════
