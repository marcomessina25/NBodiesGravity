"""Milestone 1 smoke test: Sun + Earth + Moon orbits over 60 simulated days.

Run:
    conda run -n nbodiesgravity python scripts/smoke_test_headless.py

Expected: matplotlib window showing Earth arcing around the Sun and the
Moon spiralling around Earth's path (60 days ≈ 1/6th of one Earth orbit).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import matplotlib.pyplot as plt
from nbodiesgravity.data.loader import load_default_system

STEPS, DT = 60, 1.0   # 60 days, 1 day per step

system = load_default_system()
# Keep only the three bodies to speed up the test
for name in [b.name for b in system.bodies]:
    if name not in {"Sun", "Earth", "Moon"}:
        system.remove_body(name)

tracks: dict[str, list] = {b.name: [] for b in system.bodies}
for _ in range(STEPS):
    system.step(DT)
    for s in system.snapshot():
        tracks[s.name].append(s.pos.copy())

fig, ax = plt.subplots(figsize=(8, 8))
ax.set_facecolor("black")
ax.set_aspect("equal")
COLORS = {"Sun": "yellow", "Earth": "dodgerblue", "Moon": "lightgray"}
for name, pts in tracks.items():
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ax.plot(xs, ys, color=COLORS[name], linewidth=1, label=name)
    ax.scatter([xs[-1]], [ys[-1]], color=COLORS[name], s=30, zorder=5)
ax.set_title("Milestone 1 — Sun / Earth / Moon (60 simulated days)", color="white")
ax.tick_params(colors="white")
for s in ax.spines.values():
    s.set_edgecolor("white")
ax.legend(facecolor="black", labelcolor="white")
fig.patch.set_facecolor("black")
plt.tight_layout()
plt.show()
