from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _now():
    return datetime.now(UTC).isoformat()


def setup_function():
    client.post("/demo/reset")


def test_health():
    assert client.get("/health").json() == {"ok": True}


def test_status_has_all_systems():
    body = client.get("/status").json()
    assert {s["system"] for s in body["systems"]} == {
        "cardiovascular", "musculoskeletal", "behavioral", "immune", "metabolic", "sleep"}


def test_one_red_reading_asks_to_remeasure_a_second_calls_the_ground():
    client.post("/measurements", json=[{"ts": _now(), "type": "temp", "value": 39.5, "unit": "°C", "reason": "wearable off"}])
    ins = client.get("/insights").json()
    assert ins["level"] == "crew" and any(i["recheck"] and i["type"] == "temp" for i in ins["items"])
    client.post("/measurements", json=[{"ts": _now(), "type": "temp", "value": 39.4, "unit": "°C", "reason": "wearable off"}])
    assert client.get("/insights").json()["level"] == "ground"


def test_an_old_value_is_grey_not_red():
    old = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    client.post("/demo/reset")
    status = {i["type"]: i for i in client.get("/status").json()["indicators"]}
    assert status["temp"]["status"] != "grey"          # demo temperature is from yesterday
    from app import main
    for m in main.MEASUREMENTS:
        if m.type == "temp":
            m.ts = datetime.fromisoformat(old)
    t = _status("temp")
    assert t["status"] == "grey" and "No fresh value" in t["message"] and t["age_days"] >= 9


def test_bad_inputs_are_rejected_with_a_reason():
    def post(**kw):
        return client.post("/measurements", json=[{"ts": _now(), "type": "temp", "value": 37.0, "unit": "°C", **kw}])
    assert post(unit="°F").status_code == 422
    assert post(ts="2099-01-01T08:00:00Z").status_code == 422
    assert client.post("/measurements", json=[{"ts": _now(), "type": "mood", "value": 2.5, "unit": "1-5"}]).status_code == 422
    assert client.post("/measurements", json=[{"ts": _now(), "type": "mood", "value": 3, "unit": "1-5"}] * 101).status_code == 422
    assert client.get("/forecast/mood", params={"days": 1000}).status_code == 422
    assert client.put("/context", json={"environment": "venus_base", "mission_day": 1}).status_code == 422


def test_time_without_zone_is_utc_and_status_still_works():
    naive = datetime.now(UTC).replace(tzinfo=None).isoformat()
    assert client.post("/measurements", json=[{"ts": naive, "type": "heart_rate", "value": 52, "unit": "bpm", "reason": "wearable off"}]).status_code == 200
    assert client.get("/status").status_code == 200
    assert client.get("/measurements", params={"type": "heart_rate", "start": "2000-01-01T00:00:00"}).status_code == 200


def test_values_typed_in_the_app_are_stored_as_self_reports():
    r = client.post("/measurements", json=[{"ts": _now(), "type": "heart_rate", "value": 52, "unit": "bpm",
                                            "source": "sensor", "reason": "wearable off"}])
    assert r.json()[0]["source"] == "manual"


def test_device_values_are_not_typed_without_a_reason():
    r = client.post("/measurements", json=[{"ts": _now(), "type": "heart_rate", "value": 52, "unit": "bpm"}])
    assert r.status_code == 422 and "wearable" in r.json()["detail"]
    ok = client.post("/measurements", json=[{"ts": _now(), "type": "mood", "value": 4, "unit": "1-5"}])
    assert ok.status_code == 200   # how the person feels needs no reason: only they can say it


def test_every_indicator_says_who_collects_it():
    meta = client.get("/meta").json()["indicators"]
    assert {m["collected_by"] for m in meta.values()} <= {"device", "test", "medic", "self"}
    assert meta["mood"]["collected_by"] == "self" and meta["heart_rate"]["collected_by"] == "device"


def test_unknown_indicator_rejected():
    r = client.post("/measurements", json=[
        {"ts": _now(), "type": "nope", "value": 1, "unit": "x"}])
    assert r.status_code == 422


def _post(type_, value, unit):
    return client.post("/measurements", json=[
        {"ts": _now(), "type": type_, "value": value, "unit": unit, "reason": "wearable off"}])


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
    client.post("/measurements", json=[{"ts": now, "type": "heart_rate", "value": 55, "unit": "bpm", "reason": "wearable off"}])
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


def test_wellbeing_forecast_for_the_real_data_demo():
    body = client.get("/wellbeing").json()
    assert body["available"]
    assert set(body["models"]) == {"mood", "fatigue"}
    for m in body["models"].values():                   # never shown without beating "same as today"
        assert m["within_person_auc"] > m["same_as_today_auc"]
    days = body["days"]
    assert [d["mission_day"] for d in days] == list(range(1, 31))
    last = days[-1]
    assert last["for_date"] == datetime.now(UTC).date().isoformat()   # the last demo day is yesterday
    for d in days:
        for key in ("mood", "fatigue"):
            f = d[key]
            assert 0 <= f["probability"] <= 1 and f["times_usual"] >= 0
            assert len(f["reasons"]) <= 3
    assert days[17]["mood"]["times_usual"] >= 1.5         # day 18: mood already low, tomorrow is worse too


def test_task_feedback_is_kept_with_the_task():
    r = client.post("/tasks/sleep/feedback", json={"outcome": "better"})
    assert r.status_code == 200 and r.json()["feedback"] == "better" and r.json()["feedback_ts"]
    assert client.post("/tasks/sleep/feedback", json={"outcome": "great"}).status_code == 422
    assert client.post("/tasks/nope/feedback", json={"outcome": "same"}).status_code == 404


def test_a_broken_saved_file_is_set_aside_and_the_app_still_loads():
    from app import main
    main.SAVED_PATH.parent.mkdir(parents=True, exist_ok=True)
    main.SAVED_PATH.write_text("{not json", encoding="utf-8")
    main.load()
    assert client.get("/status").status_code == 200
    assert main.SAVED_PATH.with_suffix(".broken").exists() and not main.SAVED_PATH.exists()
    main.SAVED_PATH.with_suffix(".broken").unlink()
