"""Every number in this file used to be a magic number in the legacy script.

A constant with a name is documentation that the compiler checks. If you find
yourself typing a bare number anywhere else in this package, it probably belongs
here instead.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- where the data lives -------------------------------------------------

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]  # src/factoryflow -> src -> project root

# Override with FACTORYFLOW_DATA when running in a container, where the project
# root is not where you think it is.
DEFAULT_DATA_PATH = Path(
    os.environ.get("FACTORYFLOW_DATA", PROJECT_ROOT / "data" / "raw" / "line_a_2026-03.csv")
)

# --- the process ----------------------------------------------------------

#: Seconds per unit at 100 % performance. 4.0 s => 15 units/min.
IDEAL_CYCLE_TIME_S: float = 4.0

#: States that count towards planned production time.
#:
#: SETUP is excluded on purpose: a changeover is planned work, so the line is
#: not expected to be producing during it. This is a modelling choice, not a
#: law of nature, and a shift supervisor may well disagree. If you change it,
#: availability changes and every number downstream changes with it.
PLANNED_STATES: frozenset[str] = frozenset({"RUN", "IDLE", "DOWN"})

#: The only state in which units come off the line.
PRODUCING_STATE: str = "RUN"

MACHINE_STATES: frozenset[str] = frozenset({"RUN", "IDLE", "SETUP", "DOWN"})

#: One row per machine per minute. Everything that converts row counts into
#: durations depends on this.
SAMPLE_INTERVAL_S: int = 60

# --- aggregation ----------------------------------------------------------

DEFAULT_FREQ: str = "1h"
ALLOWED_FREQS: tuple[str, ...] = ("15min", "1h", "8h")

# --- anomaly detection ----------------------------------------------------

#: Spindle vibration above this is worth a look regardless of statistics.
VIBRATION_WARN_MM_S: float = 4.5

#: Rolling window (minutes) and threshold for the z-score detector.
ZSCORE_WINDOW: int = 60
ZSCORE_THRESHOLD: float = 3.0

#: A physical sensor that has not moved for this many minutes is suspicious.
STUCK_WINDOW: int = 30

#: Ignore episodes shorter than this. A single odd minute is noise, not a fault.
MIN_EPISODE_MINUTES: int = 3
