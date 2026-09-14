"""Tests for scientific data export (CSV and JSON)."""
import csv
import json
import numpy as np
import pytest
from pathlib import Path

from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.diagnostics import ConservationTracker, DiagnosticsHistoryBuffer
from nbodiesgravity.engine.orbital_elements import compute_orbital_elements
from nbodiesgravity.data.export import (
    export_conservation_history_csv,
    export_conservation_history_json,
    export_orbital_elements_csv,
    export_orbital_elements_json,
)


@pytest.fixture
def sample_history():
    buf = DiagnosticsHistoryBuffer(max_points=10)
    b1 = CelestialBody("Sun", 1.989e30, np.zeros(3), np.zeros(3), 1.0, (1, 1, 0))
    b2 = CelestialBody("Earth", 5.972e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0172, 0.0]), 1.0, (0, 0, 1))
    tracker = ConservationTracker([b1, b2])

    for day in range(3):
        rep = tracker.evaluate([b1, b2])
        buf.append(time=float(day), report=rep, substeps=2, adaptive_dt=0.5)

    return buf


@pytest.fixture
def sample_elements():
    mu = 2.959122082855911e-4
    elem_circ = compute_orbital_elements(np.array([1.0, 0.0, 0.0]), np.array([0.0, np.sqrt(mu), 0.0]), mu)
    elem_hyp = compute_orbital_elements(np.array([1.0, 0.0, 0.0]), np.array([0.0, 3.0 * np.sqrt(mu), 0.0]), mu)
    return {
        "Earth": elem_circ,
        "Comet": elem_hyp,
    }


def test_export_conservation_history_csv(sample_history, tmp_path):
    csv_file = tmp_path / "history.csv"
    export_conservation_history_csv(sample_history, csv_file)

    assert csv_file.exists()
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # 1 header row + 3 data rows
    assert len(rows) == 4
    header = rows[0]
    assert header[0] == "time_days"
    assert header[4] == "energy_rel_drift"
    assert float(rows[1][0]) == 0.0
    assert float(rows[2][0]) == 1.0
    assert float(rows[3][0]) == 2.0


def test_export_conservation_history_json(sample_history, tmp_path):
    json_file = tmp_path / "history.json"
    export_conservation_history_json(sample_history, json_file)

    assert json_file.exists()
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

    assert data["version"] == "0.7.0"
    assert data["point_count"] == 3
    assert len(data["series"]["times"]) == 3
    assert data["series"]["times"] == [0.0, 1.0, 2.0]


def test_export_orbital_elements_csv_and_json(sample_elements, tmp_path):
    csv_file = tmp_path / "elements.csv"
    json_file = tmp_path / "elements.json"

    export_orbital_elements_csv(sample_elements, csv_file)
    assert csv_file.exists()

    with open(csv_file, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    # Header + 2 bodies
    assert len(rows) == 3
    assert rows[1][0] == "Earth"
    assert rows[2][0] == "Comet"
    # Comet apoapsis should be 'inf'
    assert rows[2][8] == "inf"

    export_orbital_elements_json(sample_elements, json_file)
    assert json_file.exists()

    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

    assert data["version"] == "0.7.0"
    assert "Earth" in data["bodies"]
    assert "Comet" in data["bodies"]
    assert data["bodies"]["Earth"]["is_bound"] is True
    assert data["bodies"]["Comet"]["is_bound"] is False
    assert data["bodies"]["Comet"]["apoapsis_au"] == "inf"
