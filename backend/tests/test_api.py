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
    assert status["exercise_min"] != "red"     # the demo person often has days without exercise
    assert client.get("/insights").json()["level"] != "ground"


def _status(ind):
    return next(i for i in client.get("/status").json()["indicators"] if i["type"] == ind)


def test_athletes_usual_low_pulse_is_not_flagged():
    hr = _status("heart_rate")                  # demo person's resting pulse is about 49, below the population band
    assert hr["status"] == "green" and "usual" in hr["message"]


def test_a_big_change_from_the_personal_norm_is_yellow():
    _post("heart_rate", 70, "bpm")              # about +20 bpm vs this person's norm, still inside population limits
    hr = _status("heart_rate")
    assert hr["status"] == "yellow" and "vs this person's usual" in hr["message"]


def test_lowest_mood_is_yellow_not_red():
    _post("mood", 1, "1-5")
    status = {i["type"]: i["status"] for i in client.get("/status").json()["indicators"]}
    assert status["mood"] == "yellow"


def test_impossible_value_rejected():
    assert _post("heart_rate", -50, "bpm").status_code == 422
    assert _post("mood", 7, "1-5").status_code == 422


def test_forecast_stays_in_range():
    body = client.get("/forecast/mood").json()
    assert all(1 <= v <= 5 for v in body["values"] + body["low"] + body["high"])


def test_forecast_band_holds_the_forecast():
    body = client.get("/forecast/heart_rate?days=7").json()
    assert len(body["values"]) == len(body["low"]) == len(body["high"]) == 7
    assert all(lo <= v <= hi for v, lo, hi in zip(body["values"], body["low"], body["high"]))
    widths = [hi - lo for lo, hi in zip(body["low"], body["high"])]
    assert widths == sorted(widths)                       # less sure further ahead


def test_forecast_goes_back_to_the_norm_not_off_a_cliff():
    from app import analytics
    rising = [60.0] * 14 + [62.0, 64.0, 66.0, 68.0, 70.0]  # five days up in a row
    old = analytics.linear_forecast(rising, 7)
    new = analytics.forecast(rising, 7, "heart_rate")
    assert old[-1] > 80                                    # the old straight line keeps climbing
    assert 60 <= new[-1] < 70                              # the new one bends back towards the usual 60-62
    assert new == sorted(new, reverse=True)


def test_complete_task():
    assert client.post("/tasks/bp/complete").json()["done"] is True


def test_demo_marks_real_and_synthetic_values():
    status = {i["type"]: i for i in client.get("/status").json()["indicators"]}
    assert status["heart_rate"]["source"] == "sensor"        # real PMData
    assert status["mood"]["source"] == "manual"              # real PMData self-report
    for ind in ("bp_sys", "bp_dia", "glucose", "temp"):      # never measured by this person
        assert status[ind]["source"] == "synthetic"
        assert status[ind]["status"] != "grey"


def test_blood_reference_keeps_flagged_samples_with_a_note():
    rows = client.get("/reference/blood", params={"crew": "C003"}).json()
    r45 = [r for r in rows if r["analyte"] == "glucose" and r["timepoint"] == "R+45"]
    assert r45 and r45[0]["value"] == 36.0
    assert "delayed" in r45[0]["quality_note"]
    assert client.get("/reference/blood", params={"crew": "C009"}).status_code == 404


def test_every_indicator_and_system_has_sourced_content():
    content = client.get("/meta").json()["content"]
    sources = content["sources"]
    for group in ("indicators", "systems"):
        names = client.get("/meta").json()[group]
        for name in names:
            item = content[group][name]
            assert item["sources"], f"{group}/{name} has no source"
            assert all(s in sources and sources[s]["url"].startswith("https://") for s in item["sources"])
    for item in content["indicators"].values():
        assert item["why"] and item["how_to_measure"] and item["advice"]


def test_a_check_in_from_today_is_the_newest_value():
    from datetime import UTC, datetime
    now = datetime.now(UTC).replace(hour=0, minute=5).isoformat()   # early morning: before the demo's 08:00
    client.post("/measurements", json=[{"ts": now, "type": "heart_rate", "value": 55, "unit": "bpm"}])
    assert _status("heart_rate")["latest"] == 55


def test_saved_check_ins_survive_a_backend_restart_but_not_reset():
    from app import main
    _post("sleep_hours", 6.5, "h")
    main.load()                                 # what happens when the server starts again
    assert _status("sleep_hours")["latest"] == 6.5
    client.post("/demo/reset")
    assert _status("sleep_hours")["latest"] != 6.5


def test_measurement_plan_items_cite_known_sources():
    content = client.get("/meta").json()["content"]
    items = content["measurement_plan"]["items"]
    assert any(i["what"] == "Bone density" for i in items)
    assert all(i["sources"] and all(s in content["sources"] for s in i["sources"]) for i in items)


def test_new_indicators_have_a_frequency_and_use_only_the_personal_norm():
    meta = client.get("/meta").json()
    for ind in ("hrv_ms", "reaction_ms"):
        assert ind in meta["indicators"] and meta["content"]["indicators"][ind]["frequency"]
    assert _status("hrv_ms")["status"] == "grey"     # the real-data demo person has no HRV


def test_exposures_and_indicator_tests_cite_known_sources():
    content = client.get("/meta").json()["content"]
    for e in content["exposures"].values():
        assert e["risk"] and e["sources"] and all(s in content["sources"] for s in e["sources"])
        assert e["monitoring"] or e["our_plan"]
    for ind in content["indicators"].values():
        assert ind["tests"] and all(s in content["sources"] for s in ind["sources"])
