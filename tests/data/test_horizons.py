import pytest
import responses as resp_mock
from datetime import date
from urllib.parse import urlparse, parse_qs
from nbodiesgravity.data.horizons import fetch, HorizonsError, HORIZONS_URL

# Minimal realistic Horizons vector-table response
_MOCK_RESULT = (
    "Ephemeris / API_USER\n"
    "$$SOE\n"
    "2451545.000000000 = A.D. 2000-Jan-01 12:00:00.0000 TDB \n"
    " X = 1.068727563E-01 Y =-9.259066609E-01 Z =-4.013741985E-04\n"
    " VX= 1.725849684E-02 VY= 2.067254143E-03 VZ=-2.128408063E-04\n"
    " LT= 5.365027063E-03 RG= 9.274975424E-01 RR= 2.484052831E-03\n"
    "$$EOE\n"
)


@resp_mock.activate
def test_fetch_returns_pos_and_vel():
    resp_mock.add(resp_mock.GET, HORIZONS_URL, json={"result": _MOCK_RESULT}, status=200)
    result = fetch("399", date(2000, 1, 1))
    assert "pos_au" in result and "vel_au_per_day" in result
    assert len(result["pos_au"]) == 3
    assert len(result["vel_au_per_day"]) == 3
    assert abs(result["pos_au"][0] - 1.068727563e-01) < 1e-8
    assert abs(result["vel_au_per_day"][0] - 1.725849684e-02) < 1e-10


@resp_mock.activate
def test_fetch_raises_on_network_error():
    resp_mock.add(resp_mock.GET, HORIZONS_URL, body=ConnectionError("timeout"))
    with pytest.raises(HorizonsError, match="Network error"):
        fetch("399", date(2000, 1, 1))


@resp_mock.activate
def test_fetch_raises_on_api_error_field():
    resp_mock.add(resp_mock.GET, HORIZONS_URL, json={"error": "No match"}, status=200)
    with pytest.raises(HorizonsError, match="Horizons error"):
        fetch("399", date(2000, 1, 1))


@resp_mock.activate
def test_fetch_raises_when_soe_missing():
    resp_mock.add(resp_mock.GET, HORIZONS_URL, json={"result": "no data here"}, status=200)
    with pytest.raises(HorizonsError, match="SOE"):
        fetch("399", date(2000, 1, 1))


@resp_mock.activate
def test_fetch_stop_time_is_one_day_after_start():
    resp_mock.add(resp_mock.GET, HORIZONS_URL, json={"result": _MOCK_RESULT}, status=200)
    fetch("399", date(2000, 1, 1))
    qs = parse_qs(urlparse(resp_mock.calls[0].request.url).query)
    start = qs["START_TIME"][0].strip("'")
    stop = qs["STOP_TIME"][0].strip("'")
    assert start == "2000-01-01"
    assert stop == "2000-01-02"
