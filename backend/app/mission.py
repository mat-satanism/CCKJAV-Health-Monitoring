"""Simulated crew mission: crew status, tasks with reassignment, alerts and the doctors' view.

Everything here is SYNTHETIC (data/processed/sim, made by pipeline/simulation.py; design in docs/simulation.md).
Risks come from the model in models/risk_model.json, precomputed in sim/predictions.csv.

Indicator statuses use the shared rule in status.py (personal norm first), same as My check-in.
Values entered in the app for a crew member (and their readiness check) override the simulated day and are
saved to MISSION_SAVED_PATH (data/local/, not in git); Reset demo removes them. Risks stay the precomputed
model output: entering a value changes the statuses and the tasks, not the 48-hour risks.
"""
import copy
import csv
import json
import os
from pathlib import Path

from .config import DATA_DIR, ENVIRONMENTS, INDICATORS, SYSTEMS
from .status import MODEL_PATH, classify

SIM_DIR = DATA_DIR / "processed" / "sim"
ANAMNESIS_PATH = DATA_DIR / "synthetic" / "anamnesis.json"
MISSION_SAVED_PATH = Path(os.environ.get("CHN_MISSION_SAVED_PATH", DATA_DIR / "local" / "mission_entries.json"))
WATCH_MULTIPLE = 3.0      # doctors see a risk when it is at least 3 times the usual level
HIGH_MULTIPLE = 5.0       # at 5 times the usual level a physical-event risk asks the CMO to confirm fitness
PHYSICAL_EVENTS = {"infection", "deconditioning"}
BLOCKING_SYMPTOMS = {"fever", "dizziness when standing"}
ORDER = ["grey", "green", "yellow", "red"]

EVENT_LABELS = {
    "sleep_disruption": "Sleep disruption", "infection": "Infection", "deconditioning": "Deconditioning",
    "low_mood": "Low mood", "co2_buildup": "CO2 build-up",
}
# Placeholder advice (not from a clinical source yet), like rules.ACTIONS.
EVENT_ACTIONS = {
    "sleep_disruption": "Protect the sleep window; move demanding tasks away from the next 2 days.",
    "infection": "Re-measure temperature in 2 h; keep apart from the crew if it rises; no EVA.",
    "deconditioning": "Restore daily resistance and cardio training; check pressure when standing; no EVA.",
    "low_mood": "Private conversation with the CMO; schedule a call with the ground psychologist.",
    "co2_buildup": "Check the CO2 scrubber and air flow before treating individual crew members.",
}


def _read(name: str) -> list[dict]:
    with (SIM_DIR / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Mission:
    def __init__(self) -> None:
        self.crew = _read("crew.csv")
        self.ids = [c["astronaut_id"] for c in self.crew]
        self.days_total = 0
        self.values: dict[tuple[str, int], dict] = {}
        for r in _read("days.csv"):
            day = int(r["mission_day"])
            self.days_total = max(self.days_total, day)
            self.values[(r["astronaut_id"], day)] = {
                **{i: float(r[i]) for i in INDICATORS},
                "symptoms": [s for s in r["symptoms"].split(";") if s],
            }
        self.preds = {(r["astronaut_id"], int(r["mission_day"])): r for r in _read("predictions.csv")}
        self.events = _read("events.csv")
        self.tasks = _read("tasks.csv")
        model = json.loads(MODEL_PATH.read_text())
        self.base_rates = {e: v["base_rate"] for e, v in model["events"].items()}
        self.anamnesis = json.loads(ANAMNESIS_PATH.read_text(encoding="utf-8"))["crew"]
        self.simulated = copy.deepcopy(self.values)
        self.entries: dict[str, dict] = {}        # "aid|day" -> {"values": {...}, "symptoms": [...]}
        self.readiness: dict[str, dict] = {}      # "aid|day" -> {"ready": bool, "note": str}
        self.day = 15
        self._load_saved()

    # ---------- values entered in the app ----------
    def _load_saved(self) -> None:
        if MISSION_SAVED_PATH.exists():
            saved = json.loads(MISSION_SAVED_PATH.read_text(encoding="utf-8"))
            self.entries, self.readiness = saved.get("entries", {}), saved.get("readiness", {})
        for key, e in self.entries.items():
            aid, day = key.split("|")
            self._apply(aid, int(day), e)

    def _apply(self, aid: str, day: int, entry: dict) -> None:
        self.values[(aid, day)].update(entry.get("values", {}))
        if "symptoms" in entry:
            self.values[(aid, day)]["symptoms"] = entry["symptoms"]

    def _persist(self) -> None:
        MISSION_SAVED_PATH.parent.mkdir(parents=True, exist_ok=True)
        MISSION_SAVED_PATH.write_text(json.dumps({"entries": self.entries, "readiness": self.readiness}, indent=1),
                                      encoding="utf-8")

    def enter(self, aid: str, day: int, values: dict[str, float], symptoms: list[str] | None = None) -> None:
        """Values for one crew member on one mission day, entered in the check-in."""
        key = f"{aid}|{day}"
        entry = self.entries.setdefault(key, {"values": {}})
        entry["values"].update(values)
        if symptoms is not None:
            entry["symptoms"] = symptoms
        self._apply(aid, day, entry)
        self._persist()

    def set_readiness(self, aid: str, day: int, ready: bool, note: str = "") -> dict:
        self.readiness[f"{aid}|{day}"] = {"ready": ready, "note": note}
        self._persist()
        return self.readiness_reply(aid, day)

    def readiness_reply(self, aid: str, day: int) -> dict | None:
        r = self.readiness.get(f"{aid}|{day}")
        if r is None:
            return None
        state = self.astronaut(aid, day, with_card=False)
        off = [i["label"].lower() for i in state["indicators"] if i["status"] in ("yellow", "red")]
        off += state["symptoms"]
        if not r["ready"]:
            reply = "Noted. The CMO will check in with you before your first task. Take it easy until then."
        elif off:
            reply = f"Thanks. You feel ready; the CMO will have a quick look at {', '.join(off)} with you."
        else:
            reply = "You're doing well. Everything is as usual for you today. Have a good day."
        return {**r, "reply": reply}

    def reset(self) -> None:
        self.values = copy.deepcopy(self.simulated)
        self.entries, self.readiness = {}, {}
        MISSION_SAVED_PATH.unlink(missing_ok=True)
        self.day = 15

    # ---------- one astronaut ----------
    def _indicator(self, aid: str, day: int, ind: str) -> dict:
        value = self.values[(aid, day)][ind]
        past = [self.values[(aid, d)][ind] for d in range(1, day)]
        c = classify(ind, value, past, population_band=False)
        return {"type": ind, "label": INDICATORS[ind]["label"], "unit": c["unit"], "value": value,
                "norm": None if c["norm"] is None else round(c["norm"], 1),
                "z": None if c["z"] is None else round(c["z"], 1), "status": c["status"], "message": c["message"]}

    def _risks(self, aid: str, day: int) -> list[dict]:
        p = self.preds.get((aid, day), {})
        out = []
        for event, base in self.base_rates.items():
            risk = float(p.get(f"risk_{event}", 0) or 0)
            multiple = risk / base if base else 0.0
            level = "high" if multiple >= HIGH_MULTIPLE else "watch" if multiple >= WATCH_MULTIPLE else "normal"
            out.append({"event": event, "label": EVENT_LABELS[event], "risk": round(risk, 3),
                        "multiple": round(multiple, 1), "level": level,
                        "signs": [s for s in (p.get(f"signs_{event}") or "").split("; ") if s],
                        "action": EVENT_ACTIONS[event]})
        return sorted(out, key=lambda r: -r["risk"])

    def astronaut(self, aid: str, day: int | None = None, with_card: bool = False) -> dict:
        """with_card: add what the personal card needs (body systems, medical history, today's medication)."""
        day = day or self.day
        member = next(c for c in self.crew if c["astronaut_id"] == aid)
        indicators = [self._indicator(aid, day, i) for i in INDICATORS]
        symptoms = self.values[(aid, day)]["symptoms"]
        risks = self._risks(aid, day)
        # Measured facts take someone off a high-demand task; a prediction alone only asks the CMO to confirm.
        reasons = [f"{i['label']} {i['value']:g} {i['unit']}: outside safe limits" for i in indicators if i["status"] == "red"]
        reasons += [f"Symptom: {s}" for s in symptoms if s in BLOCKING_SYMPTOMS]
        cautions = [f"{r['label']} risk {r['multiple']:g}x usual in the next 48 h ({'; '.join(r['signs']) or 'no single sign'})"
                    for r in risks if r["event"] in PHYSICAL_EVENTS and r["level"] == "high"]
        out = {**member, "skills": member["skills"].split(";"), "day": day,
               "status": max((i["status"] for i in indicators), key=ORDER.index),
               "indicators": indicators, "symptoms": symptoms, "risks": risks,
               "fit_for_high_demand": not reasons, "unfit_reasons": reasons, "cautions": cautions,
               "source": "synthetic"}
        if with_card:
            entered = self.entries.get(f"{aid}|{day}", {}).get("values", {})
            for i in indicators:
                i["entered"] = i["type"] in entered
            history = self.anamnesis[aid]
            out.update(
                systems=[{"system": s, "indicators": inds,
                          "status": max((i["status"] for i in indicators if i["type"] in inds), key=ORDER.index)}
                         for s in SYSTEMS for inds in [[k for k, m in INDICATORS.items() if m["system"] == s]]],
                anamnesis={k: v for k, v in history.items() if k != "medication_log"},
                medication_today=[{**m, "day": day, "given_by": "self"} for m in history["medications"]
                                  if m["schedule"].startswith("daily")]
                                 + [m for m in history.get("medication_log", []) if m["day"] == day],
                readiness=self.readiness_reply(aid, day))
        return out

    def history(self, aid: str) -> dict:
        """Every mission day for one crew member: value, personal norm, its 95% prediction band, status."""
        out = {}
        for ind in INDICATORS:
            rows = []
            for day in range(1, self.days_total + 1):
                value = self.values[(aid, day)][ind]
                c = classify(ind, value, [self.values[(aid, d)][ind] for d in range(1, day)], population_band=False)
                rows.append({"day": day, "value": value, "status": c["status"],
                             "norm": None if c["norm"] is None else round(c["norm"], 2),
                             "low": None if c["low"] is None else round(c["low"], 2),
                             "high": None if c["high"] is None else round(c["high"], 2),
                             "z": None if c["z"] is None else round(c["z"], 2),
                             "entered": ind in self.entries.get(f"{aid}|{day}", {}).get("values", {})})
            out[ind] = rows
        return out

    # ---------- whole crew ----------
    def alerts(self, day: int | None = None) -> list[dict]:
        day = day or self.day
        out = []
        for e in self.events:
            if e["type"] == "solar_flare" and int(e["onset_day"]) <= day <= int(e["end_day"]):
                out.append({"kind": "solar_flare", "level": "red", "who": "crew",
                            "message": "Solar flare: radiation alarm. Crew to the shelter, EVA postponed."})
        headache = [c["name"] for c in self.crew if "headache" in self.values[(c["astronaut_id"], day)]["symptoms"]]
        if len(headache) >= 3:
            out.append({"kind": "environment", "level": "yellow", "who": "crew",
                        "message": f"Same symptoms in {len(headache)} crew members ({', '.join(headache)}): "
                                   "check station air (CO2) before treating people one by one."})
        return out

    def tasks_for(self, day: int | None = None) -> list[dict]:
        day = day or self.day
        flare = any(a["kind"] == "solar_flare" for a in self.alerts(day))
        states = {aid: self.astronaut(aid, day) for aid in self.ids}
        names = {c["astronaut_id"]: c["name"] for c in self.crew}
        today = [t for t in self.tasks if int(t["mission_day"]) == day]
        busy = {t["assignee"] for t in today if t["demand"] == "high"}
        out = []
        for t in today:
            item = {**t, "mission_day": day, "assignee_name": names[t["assignee"]], "status": "planned",
                    "reassigned_to": None, "reassigned_to_name": None, "reason": None, "warning": None}
            if t["kind"] == "eva" and flare:
                item.update(status="postponed", reason="Solar flare: no EVA until the radiation alarm is over.")
            elif t["demand"] == "high" and not states[t["assignee"]]["fit_for_high_demand"]:
                why = "; ".join(states[t["assignee"]]["unfit_reasons"])
                for aid in self.ids:
                    s = states[aid]
                    if aid != t["assignee"] and t["skill"] in s["skills"] and s["fit_for_high_demand"] and aid not in busy:
                        busy.add(aid)
                        item.update(status="reassigned", reassigned_to=aid, reassigned_to_name=names[aid],
                                    reason=f"{names[t['assignee']]} is not fit: {why}")
                        break
                else:
                    item.update(status="needs decision", reason=f"{names[t['assignee']]} is not fit ({why}) "
                                                               "and no fit crew member with this skill is free.")
            if t["demand"] == "high" and item["status"] == "planned" and states[t["assignee"]]["cautions"]:
                item["warning"] = (f"CMO to confirm {names[t['assignee']]} is fit: "
                                   + "; ".join(states[t["assignee"]]["cautions"]))
            out.append(item)
        return out

    def timeline(self) -> list[dict]:
        """One entry per mission day: the crew's worst status, risks above usual, alerts and moved tasks."""
        out = []
        for day in range(1, self.days_total + 1):
            crew = [self.astronaut(aid, day) for aid in self.ids]
            tasks = self.tasks_for(day)
            out.append({
                "day": day,
                "status": max((a["status"] for a in crew), key=ORDER.index),
                "high_risks": sum(r["level"] == "high" for a in crew for r in a["risks"]),
                "alerts": [a["kind"] for a in self.alerts(day)],
                "changed_tasks": sum(t["status"] != "planned" for t in tasks),
            })
        return out

    # ---------- for the doctors: what to do now, alarm log, report ----------
    def now(self, day: int | None = None) -> list[dict]:
        """CMO quick screen: one line per crew member with the single most important thing and what to do."""
        day = day or self.day
        out = []
        for aid in self.ids:
            a = self.astronaut(aid, day)
            red = [i for i in a["indicators"] if i["status"] == "red"]
            yellow = [i for i in a["indicators"] if i["status"] == "yellow"]
            high = [r for r in a["risks"] if r["level"] == "high"]
            if a["unfit_reasons"]:
                level, what, do = "red", "; ".join(a["unfit_reasons"]), "Examine now. Off EVA and heavy tasks today."
            elif red:
                level, what, do = "red", f"{red[0]['label']} {red[0]['value']:g} {red[0]['unit']}", "Re-measure now; examine if confirmed."
            elif high:
                r = high[0]
                level, what, do = "yellow", f"{r['label']} risk {r['multiple']:g}x usual in 48 h", r["action"]
            elif yellow:
                i = yellow[0]
                level, what, do = "yellow", f"{i['label']}: {i['message']}", "Re-measure later today before acting."
            else:
                level, what, do = "green", "As usual for this person", "Nothing to do."
            out.append({"astronaut_id": aid, "name": a["name"], "role": a["role"], "level": level,
                        "what": what, "do": do, "symptoms": a["symptoms"]})
        return sorted(out, key=lambda x: -ORDER.index(x["level"]))

    def alarm_log(self, upto: int | None = None) -> list[dict]:
        """Every alarm from day 1 to `upto`: red values, symptoms that block tasks, high risks, crew alerts, moved tasks."""
        upto = upto or self.day
        log = []
        for day in range(1, upto + 1):
            for aid in self.ids:
                a = self.astronaut(aid, day)
                for i in a["indicators"]:
                    if i["status"] == "red":
                        log.append({"day": day, "who": a["name"], "level": "red", "kind": "value",
                                    "what": f"{i['label']} {i['value']:g} {i['unit']}: outside safe limits",
                                    "action": "Off heavy tasks until re-measured and examined"})
                for r in a["risks"]:
                    if r["level"] == "high":
                        physical = r["event"] in PHYSICAL_EVENTS
                        log.append({"day": day, "who": a["name"], "level": "yellow", "kind": "risk",
                                    "what": f"{r['label']} risk {r['multiple']:g}x usual in 48 h",
                                    "action": "CMO to confirm fitness for heavy tasks" if physical else "Watch; " + r["action"]})
            for al in self.alerts(day):
                log.append({"day": day, "who": "crew", "level": al["level"], "kind": "alert", "what": al["message"],
                            "action": "Crew-wide response"})
            for t in self.tasks_for(day):
                if t["status"] != "planned":
                    who = t["reassigned_to_name"]
                    log.append({"day": day, "who": t["assignee_name"], "level": "yellow", "kind": "task",
                                "what": f"{t['title']}: {t['status']}" + (f" to {who}" if who else ""),
                                "action": t["reason"] or ""})
        return log

    def report(self, day: int | None = None, period: str = "day") -> dict:
        """Summary for the flight surgeon on Earth, made overnight while the crew sleeps.

        period "day": this mission day. period "week": the last 7 days up to this day.
        """
        day = day or self.day
        first = day if period == "day" else max(1, day - 6)
        days = range(first, day + 1)
        crew = []
        for aid in self.ids:
            states = [self.astronaut(aid, d) for d in days]
            today = states[-1]
            hist = self.anamnesis[aid]
            meds = [m for m in hist.get("medication_log", []) if first <= m["day"] <= day]
            ready = [self.readiness.get(f"{aid}|{d}") for d in days]
            crew.append({
                "astronaut_id": aid, "name": today["name"], "role": today["role"], "status": today["status"],
                "fit_for_high_demand": today["fit_for_high_demand"],
                "days_yellow": sum(s["status"] == "yellow" for s in states),
                "days_red": sum(s["status"] == "red" for s in states),
                "off_today": [f"{i['label']}: {i['message']}" for i in today["indicators"] if i["status"] != "green"],
                "symptoms": sorted({x for s in states for x in s["symptoms"]}),
                "top_risks": [f"{r['label']} {r['multiple']:g}x usual" for r in today["risks"] if r["level"] != "normal"][:3],
                "medication_given": [f"Day {m['day']}: {m['drug']} {m['dose']} ({m['reason']})" for m in meds],
                "not_ready_days": [d for d, r in zip(days, ready) if r and not r["ready"]],
            })
        log = [e for e in self.alarm_log(day) if e["day"] >= first]
        return {"day": day, "period": period, "from_day": first, "to_day": day,
                "made": f"Made overnight after mission day {day}, while the crew sleeps.",
                "crew": crew, "alarms": log,
                "tasks_changed": sum(e["kind"] == "task" for e in log),
                "source": "synthetic", "note": "Simulated crew data. Not medical advice."}

    def doctor(self, role: str, day: int | None = None) -> dict:
        day = day or self.day
        crew = [self.astronaut(aid, day) for aid in self.ids]
        anomalies = [{"astronaut_id": a["astronaut_id"], "name": a["name"], **i}
                     for a in crew for i in a["indicators"] if i["status"] in ("yellow", "red")]
        risks = [{"astronaut_id": a["astronaut_id"], "name": a["name"], **r}
                 for a in crew for r in a["risks"] if r["level"] != "normal"]
        symptoms = [{"astronaut_id": a["astronaut_id"], "name": a["name"], "symptoms": a["symptoms"]}
                    for a in crew if a["symptoms"]]
        delay_s = ENVIRONMENTS["mars_base"]["comm_delay_s"]
        if role == "ground":
            header = {"role": "ground", "title": "Flight surgeon on Earth", "data_delay_min": round(delay_s / 60),
                      "reply_round_trip_min": round(2 * delay_s / 60),
                      "guidance": "You see the crew's data about 20 minutes late, and your advice takes as long to arrive. "
                                  "Advise the CMO on trends and risks; anything urgent is handled onboard first."}
        else:
            header = {"role": "cmo", "title": "Crew medical officer (onboard)", "data_delay_min": 0,
                      "reply_round_trip_min": 0,
                      "guidance": "Live data. Act on red now, re-measure single odd values before raising an alarm, "
                                  "and send the ground a summary of anything above usual risk."}
        return {**header, "day": day, "anomalies": anomalies,
                "risks": sorted(risks, key=lambda r: -r["multiple"]), "symptoms": symptoms,
                "alerts": self.alerts(day), "source": "synthetic"}


MISSION = Mission() if (SIM_DIR / "crew.csv").exists() and MODEL_PATH.exists() else None
