"""Scientific experiment tracking and deterministic replay execution."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
import numpy as np

from .presets import InitialConditionSet
from .integrator import IntegratorConfig
from .physics import PhysicsConfig, CollisionConfig
from .system import SolarSystem, TimeStepConfig
from .diagnostics import ConservationTracker, DiagnosticReport


@dataclass(frozen=True)
class ExperimentMetadata:
    """Provenance and scientific description of a numerical simulation experiment."""
    experiment_id: str
    name: str
    description: str
    author: str = "NBodiesGravity"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    application_version: str = "0.9.0"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "description": self.description,
            "author": self.author,
            "created_at": self.created_at,
            "application_version": self.application_version,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentMetadata:
        return cls(
            experiment_id=str(data.get("experiment_id", "")),
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            author=str(data.get("author", "NBodiesGravity")),
            created_at=str(data.get("created_at", "")),
            application_version=str(data.get("application_version", "0.9.0")),
            notes=str(data.get("notes", "")),
        )


@dataclass(frozen=True)
class ExperimentConfig:
    """Self-describing experiment specification capable of deterministic replay."""
    metadata: ExperimentMetadata
    initial_conditions: InitialConditionSet
    target_duration: float   # Simulated days to run

    def run_replay(self) -> dict[str, Any]:
        """Execute headless simulation run and produce deterministic results.

        Returns
        -------
        Dictionary containing final body coordinates, velocities, elapsed time,
        and conservation drift metrics.
        """
        system = self.initial_conditions.create_system()
        tracker = ConservationTracker(system.bodies, softening=system.softening)

        step_dt = 1.0
        remaining = self.target_duration
        while remaining > 1e-9:
            dt = min(remaining, step_dt)
            system.step(dt)
            remaining -= dt

        snap = system.snapshot()
        report = tracker.evaluate(snap)

        return {
            "experiment_id": self.metadata.experiment_id,
            "target_duration": float(self.target_duration),
            "final_bodies": [
                {
                    "name": s.name,
                    "pos": s.pos.tolist(),
                    "vel": s.vel.tolist(),
                    "mass": float(s.mass),
                }
                for s in snap
            ],
            "energy_rel_drift": float(report.energy_drift.rel_drift),
            "linear_mom_drift": float(report.linear_momentum_drift.abs_drift),
            "angular_mom_drift": float(report.angular_momentum_drift.rel_drift),
            "com_drift": float(report.center_of_mass_drift.abs_drift),
            "cumulative_substeps": int(system.cumulative_substeps),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "initial_conditions": self.initial_conditions.to_dict(),
            "target_duration": float(self.target_duration),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentConfig:
        return cls(
            metadata=ExperimentMetadata.from_dict(data.get("metadata", {})),
            initial_conditions=InitialConditionSet.from_dict(data.get("initial_conditions", {})),
            target_duration=float(data.get("target_duration", 10.0)),
        )

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> ExperimentConfig:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
