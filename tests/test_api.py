"""Smoke tests for the four routes.

These do not re-test the arithmetic -- `test_metrics.py` does that. They test
the things that only break at the boundary: status codes, field names, and
whether the response is actually valid JSON.
"""

from __future__ import annotations

import pytest


def test_health_reports_loaded_rows(client) -> None:
    """A service that is up but holding no data is not healthy, it is misleading."""
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["rows_loaded"] > 100_000


def test_machines_lists_the_line(client) -> None:
    machines = client.get("/machines").json()
    assert [machine["machine_id"] for machine in machines] == ["M-01", "M-02", "M-03"]
    assert {machine["line"] for machine in machines} == {"A"}


def test_metrics_returns_the_agreed_fields(client) -> None:
    """The dashboard is written against these names. Renaming one breaks it silently."""
    rows = client.get("/metrics", params={"machine": "M-01", "freq": "8h"}).json()
    assert rows
    assert set(rows[0]) == {
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
    }


def test_metrics_window_is_inclusive_at_both_ends(client) -> None:
    """ "The 14th to the 15th" means two days, not one and a bit."""
    rows = client.get(
        "/metrics",
        params={"machine": "M-01", "freq": "8h", "from": "2026-03-14", "to": "2026-03-15"},
    ).json()
    days = {row["bucket_start"][:10] for row in rows}
    assert days == {"2026-03-14", "2026-03-15"}


def test_undefined_metrics_serialise_as_null_not_nan(client) -> None:
    """NaN is not JSON. A browser refuses to parse it, and the page just stays blank."""
    response = client.get("/metrics", params={"freq": "1h"})
    assert "NaN" not in response.text
    assert response.json()  # parses at all


def test_unknown_machine_is_a_404(client) -> None:
    response = client.get("/metrics", params={"machine": "M-99"})
    assert response.status_code == 404
    assert "M-99" in response.json()["detail"]


@pytest.mark.parametrize("freq", ["3h", "1d", "", "1H "])
def test_a_bucket_size_nobody_meant_is_a_422(client, freq: str) -> None:
    assert client.get("/metrics", params={"freq": freq}).status_code == 422


def test_anomalies_are_sorted_by_severity(client) -> None:
    rows = client.get("/anomalies", params={"min_severity": 0.5}).json()
    assert rows
    severities = [row["severity"] for row in rows]
    assert severities == sorted(severities, reverse=True)
    assert all(row["severity"] >= 0.5 for row in rows)


def test_raising_min_severity_shortens_the_list(client) -> None:
    """The intended way to make the list actionable."""
    many = client.get("/anomalies", params={"min_severity": 0.0}).json()
    few = client.get("/anomalies", params={"min_severity": 0.9}).json()
    assert len(few) < len(many)


def test_the_real_breakdown_is_reported(client) -> None:
    """M-02 stopped for six hours on 14 March. If that is not in the list, the
    detector is tuned so tight it would miss the one event of the month."""
    rows = client.get("/anomalies", params={"machine": "M-02", "min_severity": 0.9}).json()
    downtime = [row for row in rows if row["kind"] == "downtime"]
    assert any(row["timestamp"].startswith("2026-03-14") for row in downtime)
