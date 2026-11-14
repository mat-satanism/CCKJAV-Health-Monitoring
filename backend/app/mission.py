"""Simulated crew mission: crew status, tasks with reassignment, alerts and the doctors' view.

Everything here is SYNTHETIC (data/processed/sim, made by pipeline/simulation.py; design in docs/simulation.md).
Risks come from the model in models/risk_model.json, precomputed in sim/predictions.csv.

Indicator statuses use the shared rule in status.py (personal norm first), same as My check-in.
"""
import csv
import json

from .config import DATA_DIR, ENVIRONMENTS, INDICATORS
from .status import MODEL_PATH, classify

SIM_DIR = DATA_DIR / "processed" / "sim"
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
        self.day = 15

    # ---------- one astronaut ----------
    def _indicator(self, aid: str, day: int, ind: str) -> dict:
        value = self.values[(aid, day)][ind]
        past = [self.values[(aid, d)][ind] for d in range(1, day)]
        c = classify(ind, value, past)
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

    def astronaut(self, aid: str, day: int | None = None) -> dict:
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
        return {**member, "skills": member["skills"].split(";"), "day": day,
                "status": max((i["status"] for i in indicators), key=ORDER.index),
                "indicators": indicators, "symptoms": symptoms, "risks": risks,
                "fit_for_high_demand": not reasons, "unfit_reasons": reasons, "cautions": cautions,
                "source": "synthetic"}

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
