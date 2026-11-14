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
    hist = client.get("/mission/astronaut/maria/history").json()
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
    r = client.post("/mission/astronaut/maria/entries", params={"day": 20}, json={"values": {"sleep_hours": 7.5}})
    assert r.json()["day"] == 20
    sleep = next(i for i in client.get("/mission/astronaut/maria", params={"day": 20}).json()["indicators"]
                 if i["type"] == "sleep_hours")
    assert sleep["value"] == 7.5 and sleep["entered"]
    assert client.get("/mission/astronaut/maria", params={"day": 40}).status_code == 422


def test_crew_has_hrv_and_reaction_time():
    _day(22)                                     # Maria's sleep is disrupted from day 21
    maria = client.get("/mission/astronaut/maria").json()
    types = {i["type"]: i for i in maria["indicators"]}
    assert {"hrv_ms", "reaction_ms"} <= set(types)
    hist = client.get("/mission/astronaut/maria/history").json()["reaction_ms"]
    calm = sorted(r["value"] for r in hist[:15])[7]
    assert types["reaction_ms"]["value"] > calm      # slower than her usual while sleep is disrupted


def test_cmo_quick_screen_puts_the_sick_first():
    now = client.get("/mission/now", params={"day": 19}).json()
    assert now[0]["name"] == "John" and now[0]["level"] == "red" and "fever" in now[0]["what"].lower()
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


def test_fever_isolates_john_and_flags_maria_who_worked_with_him():
    _day(18)
    alerts = client.get("/mission/alerts").json()
    iso = next(a for a in alerts if a["kind"] == "isolation")
    assert iso["who"] == "John" and "Maria" in iso["message"]
    maria = client.get("/mission/astronaut/maria", params={"day": 18}).json()
    assert maria["contact_of"] == ["John"] and not maria["isolated"]
    maint = _task("Systems maintenance")               # John's own task goes to Stefan while he is isolated
    assert maint["assignee"] == "john" and maint["reassigned_to_name"] == "Stefan"
    now = client.get("/mission/now", params={"day": 18}).json()
    assert now[0]["name"] == "John" and "isolate" in now[0]["do"].lower()


def test_week_trend_shows_marias_sleep_going_down_before_her_sleep_problem():
    card = client.get("/mission/astronaut/maria", params={"day": 20}).json()
    sleep = [t for t in card["trends"] if t["type"] == "sleep_hours"]
    assert sleep and sleep[0]["worse"] and sleep[0]["per_day"] < 0


def test_support_message_and_demo_nutrition_tips():
    calm = client.get("/mission/astronaut/kenji", params={"day": 10}).json()["support"]
    assert calm["nutrition"] and calm["message"]
    john = client.get("/mission/astronaut/john", params={"day": 19}).json()["support"]
    assert john["level"] == "low" and any("fluids" in t for t in john["nutrition"])
    assert any("caffeine" in t for t in john["nutrition"])          # slow caffeine metabolism in his history


def test_patient_file_turns_the_biography_into_sourced_monitoring():
    f = client.get("/mission/astronaut/kenji/file", params={"day": 20}).json()
    assert f["biography"]["flights"] == 2 and f["source"] == "synthetic"
    ids = {e["id"] for e in f["exposures"]}
    assert {"previous_spaceflight", "long_duration_flight"} <= ids
    assert all(e["sources"] and (e["monitoring"] or e["our_plan"]) for e in f["exposures"])
    john = client.get("/mission/astronaut/john/file", params={"day": 20}).json()
    assert any(m["drug"] == "Paracetamol" for m in john["mission_so_far"]["medication_given"])
    assert client.get("/mission/astronaut/nobody/file").status_code == 404


def test_co2_days_show_a_crew_wide_signal_and_the_calibration_week_does_not():
    assert any(s["type"] == "mood" and s["direction"] == "down"
               for s in client.get("/mission/crew-signal", params={"day": 25}).json())
    for day in range(1, 7):
        assert client.get("/mission/crew-signal", params={"day": day}).json() == []


def test_brief_puts_the_crew_signal_first_and_says_all_clear_on_a_quiet_day():
    lines = client.get("/mission/brief", params={"day": 25}).json()["lines"]
    assert lines[0].startswith("Crew-wide") and any(line.startswith("Crew-wide: mood down") for line in lines)
    quiet = client.get("/mission/brief", params={"day": 4}).json()
    assert quiet["all_clear"] and quiet["lines"][0].startswith("All crew as usual")


def test_entered_values_feed_the_brief_the_same_day():
    client.post("/mission/astronaut/stefan/entries", params={"day": 4}, json={"values": {"temp": 39.4}})
    lines = client.get("/mission/brief", params={"day": 4}).json()["lines"]
    assert any(line.startswith("Stefan") for line in lines)


def test_private_medical_conference_is_never_moved_to_someone_else():
    for day in range(1, 31):
        for t in client.get("/mission/tasks").json() if _day(day) is None else []:
            if t["kind"] == "pmc":
                assert t["status"] == "planned"
