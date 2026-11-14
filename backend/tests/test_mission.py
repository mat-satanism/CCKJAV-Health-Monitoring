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


def test_first_week_has_no_yellow_only_red_can_fire():
    from app.mission import MISSION
    for day in range(1, 7):            # 6 days of calibration
        for aid in MISSION.ids:
            for i in MISSION.astronaut(aid, day)["indicators"]:
                assert i["status"] in ("green", "red"), (aid, day, i["type"])


def test_personal_card_has_body_systems_history_and_medication():
    _day(19)
    card = client.get("/mission/astronaut/john").json()
    assert {s["system"] for s in card["systems"]} >= {"cardiovascular", "immune", "sleep"}
    assert "Penicillin (skin rash)" in card["anamnesis"]["allergies"]
    assert any(m["drug"] == "Paracetamol" for m in card["medication_today"])
    amara = client.get("/mission/astronaut/amara").json()
    assert amara["medication_today"][0]["drug"] == "Levothyroxine"     # daily medicine shows every day
    assert client.get("/mission/astronaut/nobody").status_code == 404


def test_history_has_every_day_with_a_norm_band_after_the_first_week():
    hist = client.get("/mission/astronaut/lena/history").json()
    hr = hist["heart_rate"]
    assert len(hr) == 30 and hr[0]["norm"] is None
    assert all(r["low"] < r["norm"] < r["high"] for r in hr[8:])


def test_entered_value_replaces_the_simulated_one_and_can_take_someone_off_a_task():
    _day(19)
    r = client.post("/mission/astronaut/stefan/entries", json={"values": {"temp": 39.4}})
    temp = next(i for i in r.json()["indicators"] if i["type"] == "temp")
    assert temp["value"] == 39.4 and temp["status"] == "red" and temp["entered"]
    assert not r.json()["fit_for_high_demand"]
    eva = _task("EVA: antenna repair")
    assert eva["status"] == "needs decision"            # John is ill and Stefan now too
    assert client.post("/mission/astronaut/stefan/entries", json={"values": {"temp": 50}}).status_code == 422


def test_reset_restores_the_simulated_day():
    _day(19)
    client.post("/mission/astronaut/stefan/entries", json={"values": {"temp": 39.4}})
    client.post("/demo/reset")
    _day(19)
    temp = next(i for i in client.get("/mission/astronaut/stefan").json()["indicators"] if i["type"] == "temp")
    assert temp["value"] != 39.4


def test_readiness_check_answers_kindly():
    r = client.post("/mission/astronaut/kenji/readiness", json={"ready": True}).json()
    assert r["ready"] and r["reply"]
    assert client.get("/mission/astronaut/kenji").json()["readiness"]["ready"] is True
    r = client.post("/mission/astronaut/kenji/readiness", json={"ready": False, "note": "headache"}).json()
    assert "CMO will check in" in r["reply"]


def test_card_and_entries_use_the_day_the_screen_shows():
    _day(15)                                    # e.g. the backend restarted and went back to day 15
    r = client.post("/mission/astronaut/lena/entries", params={"day": 20}, json={"values": {"sleep_hours": 7.5}})
    assert r.json()["day"] == 20
    sleep = next(i for i in client.get("/mission/astronaut/lena", params={"day": 20}).json()["indicators"]
                 if i["type"] == "sleep_hours")
    assert sleep["value"] == 7.5 and sleep["entered"]
    assert client.get("/mission/astronaut/lena", params={"day": 40}).status_code == 422


def test_crew_has_hrv_and_reaction_time():
    _day(22)                                     # Lena's sleep is disrupted from day 21
    lena = client.get("/mission/astronaut/lena").json()
    types = {i["type"]: i for i in lena["indicators"]}
    assert {"hrv_ms", "reaction_ms"} <= set(types)
    hist = client.get("/mission/astronaut/lena/history").json()["reaction_ms"]
    calm = sorted(r["value"] for r in hist[:15])[7]
    assert types["reaction_ms"]["value"] > calm      # slower than her usual while sleep is disrupted


def test_cmo_quick_screen_puts_the_sick_first():
    now = client.get("/mission/now", params={"day": 19}).json()
    assert now[0]["name"] == "John" and now[0]["level"] == "red" and "fever" in now[0]["what"]
    assert len(now) == 5 and all(n["do"] for n in now)


def test_alarm_log_grows_with_the_mission_and_records_the_moved_eva():
    early = client.get("/mission/alarms", params={"day": 10}).json()
    late = client.get("/mission/alarms", params={"day": 27}).json()
    assert len(late) > len(early)
    assert any(e["kind"] == "task" and e["day"] == 19 and "Stefan" in e["what"] for e in late)
    assert any(e["kind"] == "alert" and e["day"] == 27 for e in late)          # solar flare


def test_weekly_report_covers_seven_days_and_lists_medicine_given():
    r = client.get("/mission/report", params={"day": 21, "period": "week"}).json()
    assert (r["from_day"], r["to_day"]) == (15, 21)
    john = next(c for c in r["crew"] if c["name"] == "John")
    assert any("Paracetamol" in m for m in john["medication_given"]) and "fever" in john["symptoms"]
    assert client.get("/mission/report", params={"period": "month"}).status_code == 422
