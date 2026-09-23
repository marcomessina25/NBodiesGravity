"""Unit tests for simulation checkpoints and deterministic resume."""
from __future__ import annotations
import tempfile
from pathlib import Path
from datetime import datetime
import numpy as np

from nbodiesgravity.engine.presets import get_preset
from nbodiesgravity.engine.checkpoints import SimulationCheckpoint
from nbodiesgravity.engine.system import SolarSystem


def test_checkpoint_creation_and_restore():
    preset = get_preset("circular_two_body")
    sys = preset.create_system()
    epoch = datetime(2000, 1, 1)

    # Advance 10 days
    sys.step(10.0)

    chk = SimulationCheckpoint.create(sys, epoch, elapsed_days=10.0, metadata={"test": "v09"})
    d = chk.to_dict()
    assert d["schema_version"] == 2
    assert d["elapsed_days"] == 10.0
    assert d["metadata"]["test"] == "v09"

    # Restore from dict
    chk_restored = SimulationCheckpoint.from_dict(d)
    restored_sys, restored_epoch, restored_elapsed, meta = chk_restored.restore()

    assert restored_epoch == epoch
    assert restored_elapsed == 10.0
    assert meta["test"] == "v09"
    assert len(restored_sys.bodies) == len(sys.bodies)

    np.testing.assert_allclose(restored_sys.bodies[0].pos, sys.bodies[0].pos)
    np.testing.assert_allclose(restored_sys.bodies[1].vel, sys.bodies[1].vel)


def test_checkpoint_file_io():
    preset = get_preset("earth_moon")
    sys = preset.create_system()
    sys.step(5.0)

    chk = SimulationCheckpoint.create(sys, datetime(2025, 1, 1), 5.0)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "checkpoint.json"
        chk.save(path)
        assert path.exists()

        loaded_chk = SimulationCheckpoint.load(path)
        assert loaded_chk.elapsed_days == 5.0
        sys2, epoch, elapsed, _ = loaded_chk.restore()
        assert epoch == datetime(2025, 1, 1)
        assert elapsed == 5.0
        np.testing.assert_allclose(sys2.bodies[0].pos, sys.bodies[0].pos)


def test_deterministic_checkpoint_resume():
    """Verify that a checkpoint-interrupted run produces identical trajectory to continuous run."""
    preset = get_preset("eccentric_two_body", a=1.0, e=0.4)
    epoch = datetime(2000, 1, 1)

    # Run A: Continuous 50 steps of 0.2 days (= 10 days total)
    sys_a = preset.create_system()
    dt = 0.2
    for _ in range(50):
        sys_a.step(dt)

    # Run B: 25 steps -> Checkpoint -> Restore -> 25 steps
    sys_b = preset.create_system()
    for _ in range(25):
        sys_b.step(dt)

    chk = SimulationCheckpoint.create(sys_b, epoch, elapsed_days=5.0)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "chk.json"
        chk.save(path)
        chk_loaded = SimulationCheckpoint.load(path)
        resumed_sys, _, _, _ = chk_loaded.restore()

    for _ in range(25):
        resumed_sys.step(dt)

    # Verify positions and velocities match within machine precision
    for ba, bb in zip(sys_a.bodies, resumed_sys.bodies):
        np.testing.assert_allclose(ba.pos, bb.pos, atol=1e-14, rtol=1e-14)
        np.testing.assert_allclose(ba.vel, bb.vel, atol=1e-14, rtol=1e-14)
