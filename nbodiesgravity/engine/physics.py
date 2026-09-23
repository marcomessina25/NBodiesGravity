"""Physical model configurations and collision settings for N-body simulation."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from .integrator import G_AU_DAY, SOFTENING


@dataclass(frozen=True)
class PhysicsConfig:
    """Explicit configuration for gravitational physics models.

    Parameters
    ----------
    gravitational_constant : float
        Gravitational constant G in AU³ kg⁻¹ day⁻². Default is G_AU_DAY.
    softening_length : float
        Plummer softening scale ε in AU. Default is 1e-4 AU.
    gravity_model : str
        Gravitational law identifier. Default is "newtonian".
    softening_model : str
        Softening model identifier. Default is "plummer".
    """
    gravitational_constant: float = G_AU_DAY
    softening_length: float = SOFTENING
    gravity_model: str = "newtonian"
    softening_model: str = "plummer"

    def __post_init__(self) -> None:
        if self.gravitational_constant <= 0 or not np.isfinite(self.gravitational_constant):
            raise ValueError(f"gravitational_constant must be positive and finite, got {self.gravitational_constant}")
        if self.softening_length < 0 or not np.isfinite(self.softening_length):
            raise ValueError(f"softening_length must be non-negative and finite, got {self.softening_length}")
        if self.gravity_model not in ("newtonian",):
            raise ValueError(f"Unsupported gravity_model: {self.gravity_model}")
        if self.softening_model not in ("plummer",):
            raise ValueError(f"Unsupported softening_model: {self.softening_model}")

    def to_dict(self) -> dict:
        return {
            "gravitational_constant": float(self.gravitational_constant),
            "softening_length": float(self.softening_length),
            "gravity_model": self.gravity_model,
            "softening_model": self.softening_model,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PhysicsConfig:
        return cls(
            gravitational_constant=float(data.get("gravitational_constant", G_AU_DAY)),
            softening_length=float(data.get("softening_length", SOFTENING)),
            gravity_model=str(data.get("gravity_model", "newtonian")),
            softening_model=str(data.get("softening_model", "plummer")),
        )


@dataclass(frozen=True)
class CollisionConfig:
    """Explicit configuration for collision detection and merger policy.

    Parameters
    ----------
    enabled : bool
        Whether collision detection and handling is active. Default is True.
    model : str
        Collision outcome policy: "merge" (inelastic mass/momentum conserving)
        or "ignore". Default is "merge".
    """
    enabled: bool = True
    model: str = "merge"

    def __post_init__(self) -> None:
        if self.model not in ("merge", "ignore"):
            raise ValueError(f"Unsupported collision model: {self.model}")

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "model": self.model,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CollisionConfig:
        return cls(
            enabled=bool(data.get("enabled", True)),
            model=str(data.get("model", "merge")),
        )
