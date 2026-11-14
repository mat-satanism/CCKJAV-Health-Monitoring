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


def _post(type_, value, unit):
    return client.post("/measurements", json=[
        {"ts": "2099-01-01T08:00:00Z", "type": type_, "value": value, "unit": unit}])


def test_skipped_workout_is_not_a_ground_emergency():
    _post("exercise_min", 0, "min")
    status = {i["type"]: i["status"] for i in client.get("/status").json()["indicators"]}
    assert status["exercise_min"] == "yellow"
    assert client.get("/insights").json()["level"] != "ground"


def test_lowest_mood_is_yellow_not_red():
    _post("mood", 1, "1-5")
    status = {i["type"]: i["status"] for i in client.get("/status").json()["indicators"]}
    assert status["mood"] == "yellow"


def test_impossible_value_rejected():
    assert _post("heart_rate", -50, "bpm").status_code == 422
    assert _post("mood", 7, "1-5").status_code == 422


def test_forecast_stays_in_range():
    values = client.get("/forecast/mood").json()["values"]
    assert all(1 <= v <= 5 for v in values)


def test_complete_task():
    assert client.post("/tasks/bp/complete").json()["done"] is True


def test_demo_is_real_where_data_exists_and_grey_elsewhere():
    status = {i["type"]: i for i in client.get("/status").json()["indicators"]}
    assert status["heart_rate"]["source"] == "sensor"
    assert status["mood"]["source"] == "manual"
    assert status["bp_sys"]["status"] == "grey"
    assert status["glucose"]["status"] == "grey"
    assert status["temp"]["status"] == "grey"


def test_blood_reference_keeps_flagged_samples_with_a_note():
    rows = client.get("/reference/blood", params={"crew": "C003"}).json()
    r45 = [r for r in rows if r["analyte"] == "glucose" and r["timepoint"] == "R+45"]
    assert r45 and r45[0]["value"] == 36.0
    assert "delayed" in r45[0]["quality_note"]
    assert client.get("/reference/blood", params={"crew": "C009"}).status_code == 404
