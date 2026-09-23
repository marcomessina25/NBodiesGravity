"""High-precision simulation checkpoints and deterministic state persistence.

Captures exact floating-point dynamical coordinates, velocities, masses,
configurations, and elapsed simulation time to enable seamless deterministic resume.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
import numpy as np

from .body import CelestialBody
from .integrator import IntegratorConfig
from .physics import PhysicsConfig, CollisionConfig
from .system import SolarSystem, TimeStepConfig


@dataclass(frozen=True)
class SimulationCheckpoint:
    """Complete serialized state snapshot of a simulation at a precise time.

    Enables resuming interrupted simulations with mathematical reproducibility.
    """
    schema_version: int = 2
    checkpoint_version: int = 1
    application_version: str = "0.9.0"
    timestamp_iso: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    epoch: str = "2000-01-01"
    elapsed_days: float = 0.0
    bodies: list[dict[str, Any]] = field(default_factory=list)
    timestep_config: dict[str, Any] = field(default_factory=dict)
    integrator_config: dict[str, Any] = field(default_factory=dict)
    physics_config: dict[str, Any] = field(default_factory=dict)
    collision_config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        system: SolarSystem,
        epoch: datetime,
        elapsed_days: float,
        metadata: dict[str, Any] | None = None,
    ) -> SimulationCheckpoint:
        """Create a checkpoint from an active SolarSystem instance."""
        bodies_data = [
            {
                "name": b.name,
                "label": b.label,
                "mass_kg": float(b.mass),
                "radius_km": float(b.radius),
                "color": list(b.color),
                "pos_au": b.pos.tolist(),
                "vel_au_per_day": b.vel.tolist(),
                "active": bool(b.active),
                "show_trail": bool(b.show_trail),
                "show_name": bool(b.show_name),
            }
            for b in system.bodies
        ]

        return cls(
            epoch=epoch.strftime("%Y-%m-%d"),
            elapsed_days=float(elapsed_days),
            bodies=bodies_data,
            timestep_config=system.timestep_config.to_dict(),
            integrator_config=system.integrator_config.to_dict(),
            physics_config=system.physics_config.to_dict(),
            collision_config=system.collision_config.to_dict(),
            metadata=dict(metadata) if metadata else {},
        )

    def restore(self) -> tuple[SolarSystem, datetime, float, dict[str, Any]]:
        """Reconstruct a SolarSystem, base epoch, and elapsed simulation time.

        Returns
        -------
        (system, epoch, elapsed_days, metadata)
        """
        try:
            epoch = datetime.fromisoformat(self.epoch)
        except ValueError:
            epoch = datetime.strptime(self.epoch, "%Y-%m-%d")

        bodies = [
            CelestialBody(
                name=e["name"],
                mass=float(e["mass_kg"]),
                pos=np.array(e["pos_au"], dtype=float),
                vel=np.array(e["vel_au_per_day"], dtype=float),
                radius=float(e.get("radius_km", 1000.0)),
                color=tuple(e.get("color", [255, 255, 255])),
                label=e.get("label", "planet"),
                active=bool(e.get("active", True)),
                show_trail=bool(e.get("show_trail", True)),
                show_name=bool(e.get("show_name", True)),
            )
            for e in self.bodies
        ]

        system = SolarSystem(
            bodies=bodies,
            timestep_config=TimeStepConfig.from_dict(self.timestep_config) if self.timestep_config else None,
            integrator_config=IntegratorConfig.from_dict(self.integrator_config) if self.integrator_config else None,
            physics_config=PhysicsConfig.from_dict(self.physics_config) if self.physics_config else None,
            collision_config=CollisionConfig.from_dict(self.collision_config) if self.collision_config else None,
        )

        return system, epoch, float(self.elapsed_days), dict(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "checkpoint_version": self.checkpoint_version,
            "application_version": self.application_version,
            "timestamp_iso": self.timestamp_iso,
            "epoch": self.epoch,
            "elapsed_days": self.elapsed_days,
            "timestep_config": self.timestep_config,
            "integrator_config": self.integrator_config,
            "physics_config": self.physics_config,
            "collision_config": self.collision_config,
            "metadata": self.metadata,
            "bodies": self.bodies,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SimulationCheckpoint:
        schema_v = int(data.get("schema_version", 1))
        # Handle format version 1 backward compatibility
        if schema_v < 2 and "bodies" in data:
            epoch_str = str(data.get("epoch", "2000-01-01"))
            return cls(
                schema_version=2,
                checkpoint_version=1,
                application_version=data.get("application_version", "0.8.0"),
                epoch=epoch_str,
                elapsed_days=float(data.get("elapsed_days", 0.0)),
                bodies=data["bodies"],
                metadata=data.get("metadata", {}),
            )

        return cls(
            schema_version=int(data.get("schema_version", 2)),
            checkpoint_version=int(data.get("checkpoint_version", 1)),
            application_version=str(data.get("application_version", "0.9.0")),
            timestamp_iso=str(data.get("timestamp_iso", "")),
            epoch=str(data.get("epoch", "2000-01-01")),
            elapsed_days=float(data.get("elapsed_days", 0.0)),
            timestep_config=dict(data.get("timestep_config", {})),
            integrator_config=dict(data.get("integrator_config", {})),
            physics_config=dict(data.get("physics_config", {})),
            collision_config=dict(data.get("collision_config", {})),
            metadata=dict(data.get("metadata", {})),
            bodies=list(data.get("bodies", [])),
        )

    def save(self, path: str | Path) -> None:
        """Write checkpoint to JSON file."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> SimulationCheckpoint:
        """Read and validate checkpoint from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
