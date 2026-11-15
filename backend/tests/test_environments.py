"""Switching the mission's place: same crew, that place's simulated days, delay and alerts."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def setup_function():
    client.post("/demo/reset")


def _go(env: str) -> dict:
    ctx = client.get("/context").json()
    return client.put("/context", json={**ctx, "environment": env}).json()


def test_all_places_are_built_and_mars_is_the_default():
    info = client.get("/mission").json()
    assert info["environment"] == "mars_base"
    assert set(info["environments"]) == {"iss", "transit", "rover", "moon_base", "mars_base"}


def test_switch_keeps_the_crew_and_the_day_but_changes_the_data():
    client.put("/mission/day?day=23")
    mars = client.get("/mission/astronaut/stefan").json()
    ctx = _go("iss")
    assert ctx["gravity_g"] == 0.0 and ctx["comm_delay_s"] == 0
    info = client.get("/mission").json()
    assert info["environment"] == "iss" and info["day"] == 23
    assert [c["name"] for c in info["crew"]] == ["Kenji", "John", "Stefan", "Amara", "Maria"]
    iss = client.get("/mission/astronaut/stefan").json()
    assert "dizziness when standing" in iss["symptoms"]          # deconditioning in 0 g on the station
    assert iss["indicators"] != mars["indicators"]


def test_station_has_a_live_link_and_no_solar_flare_shelter():
    _go("iss")
    ground = client.get("/mission/doctor?role=ground").json()
    assert ground["data_delay_min"] == 0 and ground["guidance"].startswith("Live link")
    alerts = {a for d in client.get("/mission/timeline").json() for a in d["alerts"]}
    assert "solar_flare" not in alerts


def test_transit_flare_and_reset_back_to_mars():
    _go("transit")
    days = {d["day"]: d for d in client.get("/mission/timeline").json()}
    assert "solar_flare" in days[24]["alerts"]
    client.post("/demo/reset")
    assert client.get("/mission").json()["environment"] == "mars_base"
    assert client.get("/context").json()["environment"] == "mars_base"


def test_unknown_place_is_rejected():
    ctx = client.get("/context").json()
    assert client.put("/context", json={**ctx, "environment": "venus"}).status_code == 422
