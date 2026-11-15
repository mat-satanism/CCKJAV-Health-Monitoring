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
from math import comb
from pathlib import Path

from .config import CONTENT, DATA_DIR, ENVIRONMENTS, INDICATORS, SYSTEMS, THRESHOLDS
from .status import MODEL_PATH, PRIORS, classify, display_unit

SIM_DIR = DATA_DIR / "processed" / "sim"
ANAMNESIS_PATH = DATA_DIR / "synthetic" / "anamnesis.json"
BIOGRAPHY_PATH = DATA_DIR / "synthetic" / "biographies.json"
# Crew signal, tuned on 40 simulated missions (docs/crew-signal.md): catches 59% of CO2 days, fires on 0.8% of
# calm days. (1.5 scales caught 78% but fired on 10% of calm days: too noisy for a busy CMO.)
Z_SHIFT = 2.0             # a person counts as "moved" when 2+ prediction scales off their own norm
P_MOVED = 0.023           # chance of that in one direction on a normal day (one tail of a normal at 2.0)
CREW_MIN = 3              # at least this many people moving the same way ...
P_SIGNAL = 0.05           # ... and less than a 5% chance of that happening by chance
SHARED_CAUSES = "station air (CO2), noise, temperature, light and work hours"
MISSION_SAVED_PATH = Path(os.environ.get("CHN_MISSION_SAVED_PATH", DATA_DIR / "local" / "mission_entries.json"))
WATCH_MULTIPLE = 3.0      # doctors see a risk when it is at least 3 times the usual level
HIGH_MULTIPLE = 5.0       # at 5 times the usual level a physical-event risk asks the CMO to confirm fitness
PHYSICAL_EVENTS = {"infection", "deconditioning"}
BLOCKING_SYMPTOMS = {"fever", "dizziness when standing"}
ORDER = ["grey", "green", "yellow", "red"]
CONTACT_DAYS = 2          # close contact = a shared task on the day of the fever or the 2 days before
TREND_DAYS = 7
TREND_MIN_R = 0.7         # the week must go clearly one way (correlation with time)
TREND_MIN_SPREADS = 2.0   # and the change over the week must be at least 2 of the person's usual day-to-day spreads
WORSE_WHEN = {"heart_rate": 1, "bp_sys": 1, "bp_dia": 1, "glucose": 1, "temp": 1, "sleep_hours": -1, "mood": -1,
              "exercise_min": -1, "hrv_ms": -1, "reaction_ms": 1}    # +1: going up is worse, -1: going down is worse
# Placeholder advice (no clinical source yet), shown as such in the app.
ISOLATION_ACTION = "isolate in own quarters and stop shared tasks"
CONTACT_ACTION = "check temperature twice a day for 3 days and report symptoms"
SUPPORT = {
    "low": "Take it easier today: swap hard training for light movement, keep your sleep window, and talk to the CMO "
           "or someone you trust if you want to. You don't have to push through alone.",
    "watch": "Some numbers are a bit off your usual. Nothing urgent: they are checked every day, and the CMO will "
             "look at them with you.",
    "good": "You're doing well. Everything is as usual for you.",
}
# Demo nutrition tips (placeholders, not dietary advice). Key: when the tip applies.
NUTRITION = {
    "always": "Calcium and vitamin D sources every day: bones lose density in low gravity.",
    "fever": "Drink more fluids while you have a fever.",
    "sleep": "No caffeine after midday while your sleep is short.",
    "slow_caffeine": "Slow caffeine metabolism in your history: keep coffee to the morning.",
    "exercise": "Enough protein after training to keep muscle while training is reduced.",
}

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


def sim_dir(env: str) -> Path:
    """Mars base is the original mission in sim/; every other place has its own folder (pipeline/environments.py)."""
    return SIM_DIR if env == "mars_base" else SIM_DIR / env


def available_environments() -> list[str]:
    return [e for e in ENVIRONMENTS if (sim_dir(e) / "crew.csv").exists() and (sim_dir(e) / "predictions.csv").exists()]


def saved_path(env: str) -> Path:
    if env == "mars_base":
        return MISSION_SAVED_PATH
    return MISSION_SAVED_PATH.with_name(f"{MISSION_SAVED_PATH.stem}_{env}{MISSION_SAVED_PATH.suffix}")


def _read(name: str, env: str = "mars_base") -> list[dict]:
    with (sim_dir(env) / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Mission:
    def __init__(self, env: str = "mars_base") -> None:
        self.env = env
        self.saved_path = saved_path(env)
        self.crew = _read("crew.csv", env)
        self.ids = [c["astronaut_id"] for c in self.crew]
        self.days_total = 0
        self.values: dict[tuple[str, int], dict] = {}
        for r in _read("days.csv", env):
            day = int(r["mission_day"])
            self.days_total = max(self.days_total, day)
            self.values[(r["astronaut_id"], day)] = {
                **{i: float(r[i]) for i in INDICATORS},
                "symptoms": [s for s in r["symptoms"].split(";") if s],
            }
        self.preds = {(r["astronaut_id"], int(r["mission_day"])): r for r in _read("predictions.csv", env)}
        self.events = _read("events.csv", env)
        self.tasks = _read("tasks.csv", env)
        model = json.loads(MODEL_PATH.read_text())
        self.base_rates = {e: v["base_rate"] for e, v in model["events"].items()}
        self.anamnesis = json.loads(ANAMNESIS_PATH.read_text(encoding="utf-8"))["crew"]
        self.biographies = json.loads(BIOGRAPHY_PATH.read_text(encoding="utf-8"))["crew"]
        self.simulated = copy.deepcopy(self.values)
        self.entries: dict[str, dict] = {}        # "aid|day" -> {"values": {...}, "symptoms": [...]}
        self.readiness: dict[str, dict] = {}      # "aid|day" -> {"ready": bool, "note": str}
        self.day = 15
        self._load_saved()

    def switch(self, env: str) -> None:
        """Same crew in another place: reload that place's simulated mission, keep the day."""
        day = self.day
        self.__init__(env)  # type: ignore[misc]
        self.day = min(day, self.days_total)

    # ---------- values entered in the app ----------
    def _load_saved(self) -> None:
        if self.saved_path.exists():
            saved = json.loads(self.saved_path.read_text(encoding="utf-8"))
            self.entries, self.readiness = saved.get("entries", {}), saved.get("readiness", {})
        for key, e in self.entries.items():
            aid, day = key.split("|")
            self._apply(aid, int(day), e)

    def _apply(self, aid: str, day: int, entry: dict) -> None:
        self.values[(aid, day)].update(entry.get("values", {}))
        if "symptoms" in entry:
            self.values[(aid, day)]["symptoms"] = entry["symptoms"]

    def _persist(self) -> None:
        self.saved_path.parent.mkdir(parents=True, exist_ok=True)
        self.saved_path.write_text(json.dumps({"entries": self.entries, "readiness": self.readiness}, indent=1),
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
        self.saved_path.unlink(missing_ok=True)
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
        iso = self.isolation(day)
        isolated = any(x["astronaut_id"] == aid for x in iso)
        contact_of = [x["name"] for x in iso for c in x["contacts"] if c["astronaut_id"] == aid]
        cautions = [f"{r['label']} risk {r['multiple']:g}x usual in the next 48 h ({'; '.join(r['signs']) or 'no single sign'})"
                    for r in risks if r["event"] in PHYSICAL_EVENTS and r["level"] == "high"]
        out = {**member, "skills": member["skills"].split(";"), "day": day,
               "status": max((i["status"] for i in indicators), key=ORDER.index),
               "indicators": indicators, "symptoms": symptoms, "risks": risks,
               "fit_for_high_demand": not reasons, "unfit_reasons": reasons, "cautions": cautions,
               "isolated": isolated, "contact_of": contact_of, "source": "synthetic"}
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
            out["trends"] = self.trends(aid, day)
            out["support"] = self.support(aid, day, out, out["trends"])
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
        for x in self.isolation(day):
            who = ", ".join(c["name"] for c in x["contacts"])
            out.append({"kind": "isolation", "level": "red", "who": x["name"],
                        "message": f"{x['name']} has a fever: {x['action']}."
                                   + (f" Close contacts in the last {CONTACT_DAYS} days: {who}: {CONTACT_ACTION}." if who else "")
                                   + " (Placeholder protocol.)"})
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
        isolated = {aid for aid, s in states.items() if s["isolated"]}
        today = [t for t in self.tasks if int(t["mission_day"]) == day]
        busy = {t["assignee"] for t in today if t["demand"] == "high"}
        out = []
        for t in today:
            partner = t.get("partner") or None
            item = {**t, "mission_day": day, "assignee_name": names[t["assignee"]], "status": "planned",
                    "partner": partner, "partner_name": names.get(partner) if partner else None,
                    "reassigned_to": None, "reassigned_to_name": None, "reason": None, "warning": None}
            off = t["kind"] != "pmc" and (t["assignee"] in isolated
                                          or (t["demand"] == "high" and not states[t["assignee"]]["fit_for_high_demand"]))
            if t["kind"] == "eva" and flare:
                item.update(status="postponed", reason="Solar flare: no EVA until the radiation alarm is over.")
            elif off:
                why = "isolated with a fever" if t["assignee"] in isolated else "; ".join(states[t["assignee"]]["unfit_reasons"])
                for aid in self.ids:
                    s = states[aid]
                    if (aid != t["assignee"] and t["skill"] in s["skills"] and aid not in isolated
                            and (s["fit_for_high_demand"] or t["demand"] != "high") and aid not in busy):
                        busy.add(aid)
                        item.update(status="reassigned", reassigned_to=aid, reassigned_to_name=names[aid],
                                    reason=f"{names[t['assignee']]} is not fit: {why}")
                        break
                else:
                    item.update(status="needs decision", reason=f"{names[t['assignee']]} is not fit ({why}) "
                                                               "and no fit crew member with this skill is free.")
            if partner in isolated and item["status"] == "planned":
                item["warning"] = f"{names[partner]} is isolated: do it alone or with another crew member."
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

    # ---------- isolation of close contacts ----------
    def _feverish(self, aid: str, day: int) -> bool:
        red_high = THRESHOLDS.get("temp", {}).get("red_high")
        v = self.values[(aid, day)]
        return "fever" in v["symptoms"] or (red_high is not None and v["temp"] >= red_high)

    def isolation(self, day: int | None = None) -> list[dict]:
        """Who has a fever today, and who worked closely with them (a shared task) in the last CONTACT_DAYS days."""
        day = day or self.day
        names = {c["astronaut_id"]: c["name"] for c in self.crew}
        sick = [aid for aid in self.ids if self._feverish(aid, day)]
        out = []
        for aid in sick:
            contacts = set()
            for t in self.tasks:
                if day - CONTACT_DAYS <= int(t["mission_day"]) <= day and t.get("partner"):
                    if t["assignee"] == aid:
                        contacts.add(t["partner"])
                    elif t["partner"] == aid:
                        contacts.add(t["assignee"])
            contacts -= set(sick)
            out.append({"astronaut_id": aid, "name": names[aid], "action": ISOLATION_ACTION,
                        "contacts": [{"astronaut_id": c, "name": names[c], "action": CONTACT_ACTION}
                                     for c in sorted(contacts)]})
        return out

    # ---------- trends over the last week ----------
    def trends(self, aid: str, day: int) -> list[dict]:
        if day < TREND_DAYS:
            return []
        out = []
        days = list(range(day - TREND_DAYS + 1, day + 1))
        for ind in INDICATORS:
            ys = [self.values[(aid, d)][ind] for d in days]
            n = len(ys)
            xm, ym = (n - 1) / 2, sum(ys) / n
            sxx = sum((i - xm) ** 2 for i in range(n))
            sxy = sum((i - xm) * (y - ym) for i, y in enumerate(ys))
            syy = sum((y - ym) ** 2 for y in ys)
            if syy == 0:
                continue
            slope, r = sxy / sxx, sxy / (sxx * syy) ** 0.5
            before = [self.values[(aid, d)][ind] for d in range(1, days[0])]
            spread = classify(ind, ys[0], before, population_band=False)["spread"] or PRIORS.get(ind, {}).get("sigma")
            if not spread or abs(r) < TREND_MIN_R or abs(slope * (n - 1)) < TREND_MIN_SPREADS * spread:
                continue
            worse = (slope > 0) == (WORSE_WHEN[ind] > 0)
            out.append({"type": ind, "label": INDICATORS[ind]["label"], "per_day": round(slope, 2),
                        "unit": display_unit(ind), "worse": worse,
                        "message": f"{INDICATORS[ind]['label']} has gone {'up' if slope > 0 else 'down'} for a week "
                                   f"({slope:+.1f} {display_unit(ind)} a day)"})
        return out

    def support(self, aid: str, day: int, state: dict, trends: list[dict]) -> dict:
        """A kind, plain message for the astronaut, and demo nutrition tips."""
        r = self.readiness.get(f"{aid}|{day}")
        stress = [i for i in state["indicators"] if i["status"] != "green" and i["type"] in ("mood", "hrv_ms", "reaction_ms", "sleep_hours")]
        stress_trend = [t for t in trends if t["worse"] and t["type"] in ("mood", "sleep_hours", "hrv_ms")]
        off = [i for i in state["indicators"] if i["status"] != "green"]
        level = "low" if stress or stress_trend or (r and not r["ready"]) else "watch" if off else "good"
        tips = [NUTRITION["always"]]
        if "fever" in state["symptoms"]:
            tips.append(NUTRITION["fever"])
        if any(i["type"] == "sleep_hours" for i in stress) or any(t["type"] == "sleep_hours" for t in stress_trend):
            tips.append(NUTRITION["sleep"])
        if any("caffeine" in g.lower() for g in self.anamnesis[aid].get("genetic", [])):
            tips.append(NUTRITION["slow_caffeine"])
        if any(t["type"] == "exercise_min" and t["worse"] for t in trends):
            tips.append(NUTRITION["exercise"])
        return {"level": level, "message": SUPPORT[level], "nutrition": tips}

    # ---------- patient file ----------
    def patient_file(self, aid: str, day: int) -> dict:
        """Fictional biography -> exposure history -> sourced risks and monitoring, plus the mission so far."""
        bio = self.biographies[aid]
        exposures = [{"id": e, **CONTENT["exposures"][e]} for e in bio["exposures"]]
        states = [self.astronaut(aid, d) for d in range(1, day + 1)]
        member = next(c for c in self.crew if c["astronaut_id"] == aid)
        hist = self.anamnesis[aid]
        return {
            "astronaut_id": aid, "name": member["name"], "role": member["role"], "day": day,
            "biography": {k: v for k, v in bio.items() if k != "exposures"},
            "anamnesis": {k: v for k, v in hist.items() if k != "medication_log"},
            "exposures": exposures,
            "mission_so_far": {
                "days_yellow": sum(s["status"] == "yellow" for s in states),
                "days_red": sum(s["status"] == "red" for s in states),
                "symptoms": sorted({x for s in states for x in s["symptoms"]}),
                "medication_given": [m for m in hist.get("medication_log", []) if m["day"] <= day],
                "not_ready_days": [d for d in range(1, day + 1)
                                   if (r := self.readiness.get(f"{aid}|{d}")) and not r["ready"]],
                "worse_trends": [t["message"] for t in self.trends(aid, day) if t["worse"]],
            },
            "source": "synthetic",
        }

    # ---------- crew-wide (environment) signal and the doctors' brief ----------
    def crew_signal(self, day: int) -> list[dict]:
        """Indicators where several people moved the same way on the same day: more likely a shared cause."""
        crew = [self.astronaut(aid, day) for aid in self.ids]
        out = []
        for ind in INDICATORS:
            zs = [(a["name"], i["z"]) for a in crew for i in a["indicators"] if i["type"] == ind and i["z"] is not None]
            n = len(zs)
            worse_up = WORSE_WHEN[ind] > 0          # only the worrying direction: a crew sleeping more is not an alarm
            direction = "up" if worse_up else "down"
            picked = [nm for nm, z in zs if (z >= Z_SHIFT if worse_up else z <= -Z_SHIFT)]
            k = len(picked)
            if k < CREW_MIN:
                continue
            p = sum(comb(n, j) * P_MOVED**j * (1 - P_MOVED) ** (n - j) for j in range(k, n + 1))
            if p >= P_SIGNAL:
                continue
            out.append({"type": ind, "label": INDICATORS[ind]["label"], "direction": direction,
                            "people": picked, "n": k, "of": n, "p_chance": round(p, 4),
                            "mean_shift": round(sum(z for _, z in zs) / n, 2),
                            "check": SHARED_CAUSES})
        return out

    def brief(self, day: int) -> dict:
        """One short read for the CMO: what matters today, most important first. Template, no language model."""
        lines = []
        for s in self.crew_signal(day):
            lines.append(f"Crew-wide: {s['label'].lower()} {s['direction']} in {s['n']} of {s['of']} "
                         f"({', '.join(s['people'])}); by chance alone "
                         f"{'under 0.1%' if s['p_chance'] < 0.001 else format(s['p_chance'], '.1%')}. Check {s['check']}.")
        lines += [a["message"] for a in self.alerts(day)]
        lines += [f"{x['name']}: {x['what']}. {x['do']}" for x in self.now(day) if x["level"] != "green"]
        for aid in self.ids:
            worse = [t for t in self.trends(aid, day) if t["worse"]]
            if worse:
                name = next(c["name"] for c in self.crew if c["astronaut_id"] == aid)
                lines.append(f"{name}, this week: " + "; ".join(t["message"][0].lower() + t["message"][1:] for t in worse[:2]) + ".")
        moved = [t for t in self.tasks_for(day) if t["status"] not in ("planned",)]
        if moved:
            lines.append(f"{len(moved)} task(s) moved or postponed today.")
        pmc = [t for t in self.tasks_for(day) if t["kind"] == "pmc"]
        if pmc:
            lines.append("Private medical conferences with the flight surgeon today: "
                         + ", ".join(t["assignee_name"] for t in pmc) + " (about 15 minutes each).")
        all_clear = not lines or all(line.startswith("Private medical conferences") for line in lines)
        if all_clear:
            lines.insert(0, "All crew as usual today. Nothing needs action.")
        return {"day": day, "lines": lines, "all_clear": all_clear, "source": "synthetic"}

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
            if a["isolated"]:
                level, what, do = "red", "Fever: isolated", "Examine now. Isolate in own quarters; no tasks today."
            elif a["unfit_reasons"]:
                level, what, do = "red", "; ".join(a["unfit_reasons"]), "Examine now. Off EVA and heavy tasks today."
            elif red:
                level, what, do = "red", f"{red[0]['label']} {red[0]['value']:g} {red[0]['unit']}", "Re-measure now; examine if confirmed."
            elif high:
                r = high[0]
                level, what, do = "yellow", f"{r['label']} risk {r['multiple']:g}x usual in 48 h", r["action"]
            elif a["contact_of"]:
                level, what, do = "yellow", f"Close contact of {', '.join(a['contact_of'])}", CONTACT_ACTION.capitalize() + "."
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
                "worse_trends": [t["message"] for t in self.trends(aid, day) if t["worse"]],
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
        delay_s = ENVIRONMENTS[self.env]["comm_delay_s"]
        if role == "ground":
            if delay_s >= 60:
                guidance = (f"You see the crew's data about {round(delay_s / 60)} minutes late, and your advice takes as "
                            "long to arrive. Advise the CMO on trends and risks; anything urgent is handled onboard first.")
            else:
                guidance = ("Live link: you see the crew's data as it comes and can talk to the CMO directly. Lead on "
                            "anything above usual risk; the CMO acts onboard.")
            header = {"role": "ground", "title": "Flight surgeon on Earth", "data_delay_min": round(delay_s / 60),
                      "reply_round_trip_min": round(2 * delay_s / 60), "guidance": guidance}
        else:
            header = {"role": "cmo", "title": "Crew medical officer (onboard)", "data_delay_min": 0,
                      "reply_round_trip_min": 0,
                      "guidance": "Live data. Act on red now, re-measure single odd values before raising an alarm, "
                                  "and send the ground a summary of anything above usual risk."}
        return {**header, "day": day, "anomalies": anomalies,
                "risks": sorted(risks, key=lambda r: -r["multiple"]), "symptoms": symptoms,
                "alerts": self.alerts(day), "source": "synthetic"}


MISSION = Mission() if (SIM_DIR / "crew.csv").exists() and MODEL_PATH.exists() else None
