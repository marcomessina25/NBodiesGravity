"""Engine-specific exception classes."""
from __future__ import annotations


class NumericalIntegrityError(ValueError):
    """Raised when numerical calculations produce invalid or unphysical states.

    Examples:
    - NaN or Inf positions, velocities, or accelerations.
    - Non-positive or non-finite integration timesteps.
    - Extreme, unphysical displacements within a single step.
    - Computational budget exceeded due to pathological configurations.
    """
    pass


class ComputationalBudgetExceededError(NumericalIntegrityError):
    """Raised when adaptive stepping requires more substeps than allowed by max_substeps."""
    pass
