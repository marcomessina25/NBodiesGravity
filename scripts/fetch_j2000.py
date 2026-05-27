"""One-time script: fetch J2000 state vectors for all default bodies.

Run once (requires internet):
    conda run -n nbodiesgravity python scripts/fetch_j2000.py

Writes: nbodiesgravity/data/snapshots/j2000.json
Then commit the file to the repo.

Notes on Horizons IDs
---------------------
- Major planets / satellites: plain number, e.g. "399" (Earth)
- Small bodies (Ceres, Eris): append semicolon for disambiguation, e.g. "1;"
"""
import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from nbodiesgravity.data.horizons import fetch, HorizonsError

J2000 = date(2000, 1, 1)

# (name, horizons_id, mass_kg, radius_km, color_rgb)
BODIES = [
    ("Sun",      "10",       1.989e30,  695700, [1.0, 0.9, 0.2]),
    ("Mercury",  "199",      3.301e23,    2440, [0.7, 0.7, 0.7]),
    ("Venus",    "299",      4.867e24,    6052, [0.9, 0.8, 0.5]),
    ("Earth",    "399",      5.972e24,    6371, [0.2, 0.5, 1.0]),
    ("Mars",     "499",      6.417e23,    3390, [0.9, 0.4, 0.2]),
    ("Jupiter",  "599",      1.898e27,   69911, [0.8, 0.7, 0.5]),
    ("Saturn",   "699",      5.683e26,   58232, [0.9, 0.8, 0.6]),
    ("Uranus",   "799",      8.681e25,   25362, [0.5, 0.8, 0.9]),
    ("Neptune",  "899",      1.024e26,   24622, [0.3, 0.4, 0.9]),
    ("Moon",     "301",      7.342e22,    1737, [0.8, 0.8, 0.8]),
    ("Io",       "501",      8.932e22,    1822, [1.0, 0.8, 0.3]),
    ("Europa",   "502",      4.800e22,    1561, [0.8, 0.7, 0.6]),
    ("Ganymede", "503",      1.482e23,    2634, [0.5, 0.5, 0.5]),
    ("Callisto", "504",      1.076e23,    2410, [0.4, 0.4, 0.4]),
    ("Titan",    "606",      1.345e23,    2575, [0.9, 0.7, 0.4]),
    ("Triton",   "801",      2.139e22,    1354, [0.7, 0.8, 0.9]),
    ("Pluto",    "999",      1.307e22,    1188, [0.8, 0.7, 0.6]),
    ("Charon",   "901",      1.586e21,     606, [0.6, 0.6, 0.6]),
    ("Eris",     "136199;",  1.660e22,    1163, [0.9, 0.9, 0.9]),
    ("Ceres",    "1;",       9.383e20,     473, [0.6, 0.6, 0.6]),
]

OUT = (
    Path(__file__).parent.parent
    / "nbodiesgravity" / "data" / "snapshots" / "j2000.json"
)


def main() -> None:
    entries = []
    for name, body_id, mass_kg, radius_km, color in BODIES:
        print(f"  {name:10s} ({body_id:8s})...", end=" ", flush=True)
        try:
            state = fetch(body_id, J2000)
        except HorizonsError as exc:
            print(f"FAILED: {exc}")
            sys.exit(1)
        entries.append({
            "name": name, "id": body_id,
            "mass_kg": mass_kg, "radius_km": radius_km, "color": color,
            "pos_au": state["pos_au"],
            "vel_au_per_day": state["vel_au_per_day"],
        })
        print("OK")
        time.sleep(0.4)   # be polite to the JPL API

    snapshot = {
        "epoch": "2000-01-01T12:00:00",
        "description": "J2000 state vectors for default solar system bodies",
        "bodies": entries,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
    print(f"\nWrote {len(entries)} bodies to {OUT}")


if __name__ == "__main__":
    main()
