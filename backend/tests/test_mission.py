"""The demo mission story, checked through the API (synthetic data, docs/simulation.md)."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def setup_function():
    client.post("/demo/reset")


def _day(n):
    assert client.put("/mission/day", params={"day": n}).status_code == 200


def _task(title):
    return next(t for t in client.get("/mission/tasks").json() if t["title"] == title)


def test_mission_is_labelled_synthetic():
    info = client.get("/mission").json()
    assert info["source"] == "synthetic" and info["days_total"] == 30 and len(info["crew"]) == 5


def test_day_must_be_inside_the_mission():
    assert client.put("/mission/day", params={"day": 0}).status_code == 422
    assert client.put("/mission/day", params={"day": 31}).status_code == 422


def test_johns_eva_goes_to_stefan_because_of_fever():
    _day(19)
    eva = _task("EVA: antenna repair")
    assert eva["status"] == "reassigned" and eva["reassigned_to"] == "stefan"
    assert "fever" in eva["reason"]


def test_planned_eva_stays_with_a_healthy_john():
    _day(12)
    assert _task("EVA: solar panel inspection")["status"] == "planned"


def test_a_prediction_alone_does_not_take_someone_off_a_task():
    _day(19)
    arm = _task("Robotic arm: cargo transfer")
    assert arm["status"] == "planned"          # Kenji keeps it; at most the CMO is asked to confirm


def test_doctors_see_johns_infection_risk_before_the_fever():
    _day(16)
    risks = client.get("/mission/doctor", params={"role": "cmo"}).json()["risks"]
    john = next(r for r in risks if r["astronaut_id"] == "john" and r["event"] == "infection")
    assert john["level"] == "high" and john["signs"]


def test_same_symptoms_in_the_crew_point_to_the_air():
    _day(25)
    alerts = client.get("/mission/alerts").json()
    assert any(a["kind"] == "environment" and "CO2" in a["message"] for a in alerts)


def test_solar_flare_postpones_eva():
    _day(27)
    eva = _task("EVA: sensor replacement")
    assert eva["status"] == "postponed" and "flare" in eva["reason"].lower()


def test_ground_view_knows_about_the_delay():
    ground = client.get("/mission/doctor", params={"role": "ground"}).json()
    assert ground["data_delay_min"] == 20 and ground["reply_round_trip_min"] == 40
    assert client.get("/mission/doctor", params={"role": "nurse"}).status_code == 422


def test_timeline_marks_the_story_days():
    days = {d["day"]: d for d in client.get("/mission/timeline").json()}
    assert len(days) == 30
    assert days[16]["high_risks"] >= 1                 # John's early warning
    assert days[19]["changed_tasks"] >= 1              # EVA moved to Stefan
    assert "environment" in days[25]["alerts"] and "solar_flare" in days[27]["alerts"]
