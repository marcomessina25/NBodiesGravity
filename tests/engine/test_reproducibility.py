"""Unit tests for experiment reproducibility and deterministic replay."""
from __future__ import annotations
import tempfile
from pathlib import Path
import numpy as np

from nbodiesgravity.engine.presets import get_preset
from nbodiesgravity.engine.experiments import ExperimentMetadata, ExperimentConfig


def test_deterministic_experiment_replay():
    preset = get_preset("circular_two_body")
    meta = ExperimentMetadata(
        experiment_id="EXP-001",
        name="Circular Two-Body Replay Test",
        description="Verify deterministic replay output",
        author="Automated Tester",
    )
    exp = ExperimentConfig(
        metadata=meta,
        initial_conditions=preset,
        target_duration=30.0,
    )

    # First run
    res1 = exp.run_replay()

    # Second run from serialized config
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "experiment.json"
        exp.save(path)
        loaded_exp = ExperimentConfig.load(path)
        res2 = loaded_exp.run_replay()

    assert res1["experiment_id"] == "EXP-001"
    assert res1["target_duration"] == res2["target_duration"]
    assert res1["cumulative_substeps"] == res2["cumulative_substeps"]

    for b1, b2 in zip(res1["final_bodies"], res2["final_bodies"]):
        assert b1["name"] == b2["name"]
        np.testing.assert_allclose(b1["pos"], b2["pos"], atol=1e-14, rtol=1e-14)
        np.testing.assert_allclose(b1["vel"], b2["vel"], atol=1e-14, rtol=1e-14)

    assert np.isclose(res1["energy_rel_drift"], res2["energy_rel_drift"], atol=1e-14)
