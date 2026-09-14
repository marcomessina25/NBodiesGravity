"""Scientific data serialization and export utilities for NBodiesGravity.

Supports exporting conservation time-series and orbital elements to CSV and JSON formats.
"""
from __future__ import annotations
import csv
import json
from pathlib import Path
from typing import Any, Mapping
import numpy as np

from nbodiesgravity.engine.diagnostics import DiagnosticsHistoryBuffer
from nbodiesgravity.engine.orbital_elements import OrbitalElements


def export_conservation_history_csv(
    history: DiagnosticsHistoryBuffer,
    file_path: str | Path,
) -> None:
    """Export time-series conservation data from DiagnosticsHistoryBuffer to a CSV file."""
    data = history.get_data()
    n = len(data["times"])
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "time_days",
        "kinetic_energy",
        "potential_energy",
        "total_energy",
        "energy_rel_drift",
        "momentum_norm_drift",
        "angular_momentum_rel_drift",
        "center_of_mass_drift_au",
        "substeps",
        "adaptive_dt_days",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(fieldnames)
        for i in range(n):
            writer.writerow([
                f"{data['times'][i]:.8e}",
                f"{data['kinetic_energy'][i]:.8e}",
                f"{data['potential_energy'][i]:.8e}",
                f"{data['total_energy'][i]:.8e}",
                f"{data['energy_rel_drift'][i]:.8e}",
                f"{data['momentum_norm_drift'][i]:.8e}",
                f"{data['angular_momentum_rel_drift'][i]:.8e}",
                f"{data['center_of_mass_drift'][i]:.8e}",
                int(data['substeps'][i]),
                f"{data['adaptive_dt'][i]:.8e}",
            ])


def export_conservation_history_json(
    history: DiagnosticsHistoryBuffer,
    file_path: str | Path,
    indent: int = 2,
) -> None:
    """Export time-series conservation data from DiagnosticsHistoryBuffer to a JSON file."""
    data = history.get_data()
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "version": "0.7.0",
        "point_count": len(data["times"]),
        "series": {
            k: [float(x) if isinstance(x, (float, np.floating)) else int(x) for x in v]
            for k, v in data.items()
        },
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=indent)


def orbital_elements_to_dict(elem: OrbitalElements) -> dict[str, Any]:
    """Convert an OrbitalElements dataclass to a JSON-serializable dictionary."""
    return {
        "semi_major_axis_au": float(elem.semi_major_axis),
        "eccentricity": float(elem.eccentricity),
        "inclination_deg": float(elem.inclination_deg),
        "longitude_ascending_node_deg": float(elem.longitude_ascending_node_deg),
        "argument_of_periapsis_deg": float(elem.argument_of_periapsis_deg),
        "true_anomaly_deg": float(elem.true_anomaly_deg),
        "periapsis_au": float(elem.periapsis),
        "apoapsis_au": float(elem.apoapsis) if np.isfinite(elem.apoapsis) else "inf",
        "period_days": float(elem.period) if np.isfinite(elem.period) else "inf",
        "period_years": float(elem.period_years) if np.isfinite(elem.period_years) else "inf",
        "specific_energy": float(elem.specific_energy),
        "is_bound": bool(elem.is_bound),
    }


def export_orbital_elements_csv(
    elements_map: Mapping[str, OrbitalElements],
    file_path: str | Path,
) -> None:
    """Export instantaneous orbital elements for a collection of bodies to CSV."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "body_name",
        "semi_major_axis_au",
        "eccentricity",
        "inclination_deg",
        "longitude_ascending_node_deg",
        "argument_of_periapsis_deg",
        "true_anomaly_deg",
        "periapsis_au",
        "apoapsis_au",
        "period_days",
        "period_years",
        "is_bound",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(fieldnames)
        for name, elem in elements_map.items():
            apo = f"{elem.apoapsis:.8e}" if np.isfinite(elem.apoapsis) else "inf"
            period = f"{elem.period:.8e}" if np.isfinite(elem.period) else "inf"
            period_y = f"{elem.period_years:.8e}" if np.isfinite(elem.period_years) else "inf"
            writer.writerow([
                name,
                f"{elem.semi_major_axis:.8e}",
                f"{elem.eccentricity:.8e}",
                f"{elem.inclination_deg:.4f}",
                f"{elem.longitude_ascending_node_deg:.4f}",
                f"{elem.argument_of_periapsis_deg:.4f}",
                f"{elem.true_anomaly_deg:.4f}",
                f"{elem.periapsis:.8e}",
                apo,
                period,
                period_y,
                elem.is_bound,
            ])


def export_orbital_elements_json(
    elements_map: Mapping[str, OrbitalElements],
    file_path: str | Path,
    indent: int = 2,
) -> None:
    """Export instantaneous orbital elements for a collection of bodies to JSON."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "version": "0.7.0",
        "bodies": {name: orbital_elements_to_dict(elem) for name, elem in elements_map.items()},
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=indent)
