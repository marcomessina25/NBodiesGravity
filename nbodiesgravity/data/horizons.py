"""JPL Horizons REST API client.

Fetches state vectors (position + velocity) for a solar-system body
at a given date, relative to the Solar System Barycenter (SSB).

API docs: https://ssd.jpl.nasa.gov/horizons/app.html
"""
from __future__ import annotations
import re
from datetime import date
from pathlib import Path
import requests

HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
_LOG_FILE = Path.home() / ".nbodiesgravity" / "horizons_error.log"


class HorizonsError(Exception):
    """Raised on network failure or unparseable Horizons response."""


def _log_error(body_id: str, text: str) -> None:
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"--- body_id={body_id} ---\n{text}\n\n")


def fetch(body_id: str, epoch_date: date) -> dict:
    """Fetch state vectors from JPL Horizons.

    Parameters
    ----------
    body_id    : JPL COMMAND identifier, e.g. "399" (Earth), "1;" (Ceres)
    epoch_date : the date for which to retrieve vectors

    Returns
    -------
    dict with "pos_au" (list[float]) and "vel_au_per_day" (list[float])

    Raises
    ------
    HorizonsError on network failure, API error, or unparseable response.
    """
    date_str = epoch_date.strftime("%Y-%m-%d")
    params = {
        "format": "json",
        "COMMAND": f"'{body_id}'",
        "OBJ_DATA": "NO",
        "MAKE_EPHEM": "YES",
        "EPHEM_TYPE": "VECTORS",
        "CENTER": "'500@0'",
        "START_TIME": f"'{date_str}'",
        "STOP_TIME": f"'{date_str}'",
        "STEP_SIZE": "'1 d'",
        "VEC_TABLE": "'2'",
        "OUT_UNITS": "'AU-D'",
        "REF_PLANE": "ECLIPTIC",
        "REF_SYSTEM": "J2000",
        "CSV_FORMAT": "NO",
    }
    try:
        resp = requests.get(HORIZONS_URL, params=params, timeout=30)
        resp.raise_for_status()
    except (requests.RequestException, OSError) as exc:
        raise HorizonsError(f"Network error fetching body {body_id}: {exc}") from exc

    data = resp.json()
    if "error" in data:
        _log_error(body_id, str(data))
        raise HorizonsError(f"Horizons error for body {body_id}: {data['error']}")

    return _parse_vectors(body_id, data.get("result", ""))


def _parse_vectors(body_id: str, result_text: str) -> dict:
    match = re.search(r"\$\$SOE(.*?)\$\$EOE", result_text, re.DOTALL)
    if not match:
        raise HorizonsError(
            f"Could not find $$SOE/$$EOE block in Horizons response for body {body_id}"
        )
    block = match.group(1)
    return {
        "pos_au": [_val(body_id, block, k) for k in ("X", "Y", "Z")],
        "vel_au_per_day": [_val(body_id, block, k) for k in ("VX", "VY", "VZ")],
    }


def _val(body_id: str, text: str, key: str) -> float:
    m = re.search(rf"{re.escape(key)}\s*=\s*([-+]?\d+\.\d+[Ee][+-]?\d+)", text)
    if not m:
        raise HorizonsError(
            f"Could not parse '{key}' from Horizons response for body {body_id}"
        )
    return float(m.group(1))
