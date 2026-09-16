"""Command line entry point.

    factoryflow oee                     the headline number per machine
    factoryflow kpis --freq 1h          the full KPI table
    factoryflow anomalies --min-severity 0.5

Also reachable as `python -m factoryflow`, which is what the session material
uses because it works without the package scripts being on PATH.

Every command takes `--data` so you can point it at a different export without
editing anything. That is the whole reason the legacy script's hardcoded
`C:\\Users\\mstudent\\Desktop\\production_data.csv` was a problem.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from factoryflow import anomalies, config, loading, metrics, pipeline


def _load(path: Path | None) -> pd.DataFrame:
    return pipeline.clean(loading.load_readings(path))


def _print_frame(frame: pd.DataFrame) -> None:
    if frame.empty:
        print("(nothing to show)")
        return
    with pd.option_context("display.max_rows", 40, "display.width", 160):
        print(frame.to_string(index=False))


def command_oee(args: argparse.Namespace) -> int:
    """One line per machine: the number the shift supervisor actually reads."""
    readings = _load(args.data)
    rows = []
    for machine_id, group in readings.groupby("machine_id", sort=True):
        rows.append(
            {
                "machine_id": machine_id,
                "availability": metrics.availability(group),
                "performance": metrics.performance(group),
                "quality": metrics.quality(group),
                "oee": metrics.oee(group),
                "units_produced": int(group["units_produced"].sum()),
                "units_rejected": int(group["units_rejected"].sum()),
            }
        )
    _print_frame(pd.DataFrame(rows).round(4))
    return 0


def command_kpis(args: argparse.Namespace) -> int:
    """The time-bucketed table the dashboard draws."""
    table = pipeline.kpi_table(_load(args.data), args.freq)
    if args.machine:
        table = table[table["machine_id"] == args.machine]
    _print_frame(table.round(4))
    print(f"\n{len(table)} buckets at freq={args.freq}")
    return 0


def command_anomalies(args: argparse.Namespace) -> int:
    """Episodes worth a human looking at, most severe first."""
    found = anomalies.detect(_load(args.data))
    if not found.empty:
        found = found[found["severity"] >= args.min_severity]
        found = found.sort_values(["severity", "timestamp"], ascending=[False, True])
    _print_frame(found)
    print(f"\n{len(found)} episodes at min-severity {args.min_severity}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="factoryflow", description="OEE reporting for production line A"
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        metavar="CSV",
        help=f"sensor export to read (default: {config.DEFAULT_DATA_PATH})",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("oee", help="headline OEE per machine").set_defaults(handler=command_oee)

    kpis = subcommands.add_parser("kpis", help="KPI table per machine per time bucket")
    kpis.add_argument("--freq", default=config.DEFAULT_FREQ, choices=config.ALLOWED_FREQS)
    kpis.add_argument("--machine", default=None, metavar="M-01")
    kpis.set_defaults(handler=command_kpis)

    found = subcommands.add_parser("anomalies", help="episodes worth looking at")
    found.add_argument("--min-severity", type=float, default=0.0)
    found.set_defaults(handler=command_anomalies)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (FileNotFoundError, ValueError) as error:
        # A stack trace is for a bug. A wrong path is not a bug, it is a typo,
        # and the person who made it should get a sentence, not sixty lines.
        print(f"factoryflow: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
