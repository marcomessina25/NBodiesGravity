"""NBodiesGravity engine package — physics, integrators, diagnostics, and simulation.

This module provides the stable, frozen public API for the numerical simulation engine.
"""
from __future__ import annotations

from .body import CelestialBody, BodyState, CollisionEvent
from .system import SolarSystem, TimeStepConfig, compute_adaptive_dt
from .integrator import (
    Integrator,
    IntegratorConfig,
    VelocityVerletIntegrator,
    LeapfrogIntegrator,
    create_integrator,
    register_integrator,
    compute_accelerations,
    G_AU_DAY,
    SOFTENING,
    MAX_DISPLACEMENT_PER_STEP,
)
from .physics import PhysicsConfig, CollisionConfig
from .presets import (
    InitialConditionSet,
    get_preset,
    list_presets,
    register_preset,
    create_circular_two_body,
    create_eccentric_two_body,
    create_oriented_two_body,
    create_earth_moon_preset,
    create_binary_star_preset,
    create_restricted_three_body_preset,
)
from .checkpoints import SimulationCheckpoint
from .experiments import ExperimentConfig, ExperimentMetadata
from .diagnostics import (
    ConservationTracker,
    DiagnosticReport,
    ConservationSnapshot,
    DiagnosticsHistoryBuffer,
    compute_kinetic_energy,
    compute_potential_energy,
    compute_total_energy,
    compute_linear_momentum,
    compute_angular_momentum,
    compute_center_of_mass,
)
from .exceptions import (
    NumericalIntegrityError,
    ComputationalBudgetExceededError,
)

__all__ = [
    # Kinematics and state
    "CelestialBody",
    "BodyState",
    "CollisionEvent",
    # System orchestration
    "SolarSystem",
    "TimeStepConfig",
    "compute_adaptive_dt",
    # Numerical integrators
    "Integrator",
    "IntegratorConfig",
    "VelocityVerletIntegrator",
    "LeapfrogIntegrator",
    "create_integrator",
    "register_integrator",
    "compute_accelerations",
    "G_AU_DAY",
    "SOFTENING",
    "MAX_DISPLACEMENT_PER_STEP",
    # Physical configurations
    "PhysicsConfig",
    "CollisionConfig",
    # Presets
    "InitialConditionSet",
    "get_preset",
    "list_presets",
    "register_preset",
    "create_circular_two_body",
    "create_eccentric_two_body",
    "create_oriented_two_body",
    "create_earth_moon_preset",
    "create_binary_star_preset",
    "create_restricted_three_body_preset",
    # Checkpoints and experiments
    "SimulationCheckpoint",
    "ExperimentConfig",
    "ExperimentMetadata",
    # Diagnostics
    "ConservationTracker",
    "DiagnosticReport",
    "ConservationSnapshot",
    "DiagnosticsHistoryBuffer",
    "compute_kinetic_energy",
    "compute_potential_energy",
    "compute_total_energy",
    "compute_linear_momentum",
    "compute_angular_momentum",
    "compute_center_of_mass",
    # Exceptions
    "NumericalIntegrityError",
    "ComputationalBudgetExceededError",
]
