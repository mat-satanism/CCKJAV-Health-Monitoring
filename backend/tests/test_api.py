from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def setup_function():
    client.post("/demo/reset")


def test_health():
    assert client.get("/health").json() == {"ok": True}


def test_status_has_all_systems():
    body = client.get("/status").json()
    assert {s["system"] for s in body["systems"]} == {
        "cardiovascular", "musculoskeletal", "behavioral", "immune", "metabolic", "sleep"}


def test_red_value_escalates_to_ground():
    client.post("/measurements", json=[
        {"ts": "2099-01-01T08:00:00Z", "type": "temp", "value": 39.5, "unit": "°C"}])
    assert client.get("/insights").json()["level"] == "ground"


def test_unknown_indicator_rejected():
    r = client.post("/measurements", json=[
        {"ts": "2099-01-01T08:00:00Z", "type": "nope", "value": 1, "unit": "x"}])
    assert r.status_code == 422


def test_complete_task():
    assert client.post("/tasks/bp/complete").json()["done"] is True
