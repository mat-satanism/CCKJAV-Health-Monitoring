"""FastAPI app. Endpoints follow docs/api-contract.md.

Storage is in-memory and seeded with the demo mission on start (see demo.py). Values entered in the app are
also written to SAVED_PATH (data/local/checkins.json, not in git), so a backend restart does not lose them.
"Reset demo" deletes that file.
"""
import json
import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import analytics, rules
from .config import BOUNDS, CONTENT, DATA_DIR, ENVIRONMENTS, INDICATORS, SYSTEMS
from .demo import blood_reference, demo_mission
from .mission import MISSION
from .models import Measurement, MissionContext, Task

app = FastAPI(title="CCKJAV Health Monitoring API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MEASUREMENTS: list[Measurement] = []
SAVED_PATH = Path(os.environ.get("CHN_SAVED_PATH", DATA_DIR / "local" / "checkins.json"))
CONTEXT = MissionContext(environment="mars_base", mission_day=94, **{
    k: ENVIRONMENTS["mars_base"][k] for k in ("gravity_g", "comm_delay_s")})
TASKS: list[Task] = []


def _default_tasks() -> list[Task]:
    return [
        Task(id="bp", title="Measure blood pressure", points=10),
        Task(id="hr", title="Measure resting heart rate", points=10),
        Task(id="sleep", title="Log sleep hours", points=5),
        Task(id="mood", title="Mood check-in", points=5),
        Task(id="exercise", title="Log resistance + cardio workout", points=15),
    ]


def _saved() -> list[Measurement]:
    if not SAVED_PATH.exists():
        return []
    return [Measurement(**m) for m in json.loads(SAVED_PATH.read_text(encoding="utf-8"))]


def _save(items: list[Measurement]) -> None:
    SAVED_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = [m.model_dump(mode="json") for m in _saved() + items]
    SAVED_PATH.write_text(json.dumps(rows, indent=1), encoding="utf-8")


def load() -> None:
    """Demo data plus everything entered in the app so far."""
    MEASUREMENTS.clear()
    MEASUREMENTS.extend(demo_mission())
    MEASUREMENTS.extend(_saved())
    TASKS[:] = _default_tasks()
    if MISSION:
        MISSION.day = 15


def reset() -> None:
    SAVED_PATH.unlink(missing_ok=True)
    if MISSION:
        MISSION.reset()
    load()


def _mission():
    if MISSION is None:
        raise HTTPException(503, "Simulated mission not built. Run: python -m pipeline.build && python -m pipeline.model")
    return MISSION


load()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/meta")
def meta():
    """Labels/units for indicators, systems and environments, plus explanations with sources (for the UI)."""
    return {"indicators": INDICATORS, "systems": SYSTEMS, "environments": ENVIRONMENTS, "content": CONTENT}


@app.get("/context", response_model=MissionContext)
def get_context():
    return CONTEXT


@app.put("/context", response_model=MissionContext)
def put_context(ctx: MissionContext):
    global CONTEXT
    env = ENVIRONMENTS[ctx.environment]
    CONTEXT = ctx.model_copy(update={"gravity_g": env["gravity_g"], "comm_delay_s": env["comm_delay_s"]})
    return CONTEXT


@app.post("/measurements", response_model=list[Measurement])
def add_measurements(items: list[Measurement]):
    for m in items:
        lo, hi = BOUNDS[m.type]
        if not lo <= m.value <= hi:
            raise HTTPException(422, f"{m.type}={m.value} is outside the plausible range {lo}-{hi}")
    MEASUREMENTS.extend(items)
    _save(items)
    return items


@app.get("/measurements", response_model=list[Measurement])
def list_measurements(type: str | None = None, start: datetime | None = None, end: datetime | None = None):
    out = [m for m in MEASUREMENTS
           if (type is None or m.type == type)
           and (start is None or m.ts >= start) and (end is None or m.ts <= end)]
    return sorted(out, key=lambda m: m.ts)


def _indicator_statuses():
    return {i: rules.indicator_status(i, [m for m in MEASUREMENTS if m.type == i]) for i in INDICATORS}


@app.get("/status")
def status():
    inds = _indicator_statuses()
    return {"indicators": list(inds.values()), "systems": rules.system_statuses(inds)}


# ---------- simulated crew mission (synthetic data, see docs/simulation.md) ----------
@app.get("/mission")
def mission_info():
    m = _mission()
    return {"day": m.day, "days_total": m.days_total, "crew": m.crew, "source": "synthetic",
            "note": "Simulated mission calibrated on real data. Not real astronauts."}


@app.put("/mission/day")
def mission_set_day(day: int):
    m = _mission()
    if not 1 <= day <= m.days_total:
        raise HTTPException(422, f"day must be between 1 and {m.days_total}")
    m.day = day
    return {"day": m.day}


@app.get("/mission/timeline")
def mission_timeline():
    return _mission().timeline()


@app.get("/mission/crew")
def mission_crew():
    m = _mission()
    return [m.astronaut(aid) for aid in m.ids]


@app.get("/mission/tasks")
def mission_tasks():
    return _mission().tasks_for()


@app.get("/mission/alerts")
def mission_alerts():
    return _mission().alerts()


@app.get("/mission/doctor")
def mission_doctor(role: str = "cmo"):
    if role not in ("cmo", "ground"):
        raise HTTPException(422, "role must be 'cmo' or 'ground'")
    return _mission().doctor(role)


class CrewEntry(BaseModel):
    values: dict[str, float] = {}
    symptoms: list[str] | None = None


class Readiness(BaseModel):
    ready: bool
    note: str = ""


def _crew_member(aid: str, day: int | None = None):
    """The mission, after checking the crew member and the day (None = the mission's current day)."""
    m = _mission()
    if aid not in m.ids:
        raise HTTPException(404, "Unknown crew member")
    if day is not None and not 1 <= day <= m.days_total:
        raise HTTPException(422, f"day must be between 1 and {m.days_total}")
    return m, day or m.day


@app.get("/mission/astronaut/{aid}")
def mission_astronaut(aid: str, day: int | None = None):
    """One crew member on one mission day: statuses, body systems, risks, medical history."""
    m, day = _crew_member(aid, day)
    return m.astronaut(aid, day, with_card=True)


@app.get("/mission/astronaut/{aid}/history")
def mission_astronaut_history(aid: str):
    m, _ = _crew_member(aid)
    return m.history(aid)


@app.post("/mission/astronaut/{aid}/entries")
def mission_astronaut_entry(aid: str, entry: CrewEntry, day: int | None = None):
    """Values for this crew member on one mission day (they replace the simulated ones)."""
    m, day = _crew_member(aid, day)
    for ind, value in entry.values.items():
        if ind not in INDICATORS:
            raise HTTPException(422, f"Unknown indicator {ind}")
        lo, hi = BOUNDS[ind]
        if not lo <= value <= hi:
            raise HTTPException(422, f"{ind}={value} is outside the plausible range {lo}-{hi}")
    m.enter(aid, day, entry.values, entry.symptoms)
    return m.astronaut(aid, day, with_card=True)


@app.post("/mission/astronaut/{aid}/readiness")
def mission_astronaut_readiness(aid: str, r: Readiness, day: int | None = None):
    m, day = _crew_member(aid, day)
    return m.set_readiness(aid, day, r.ready, r.note)


def _mission_day(day: int | None):
    m = _mission()
    if day is not None and not 1 <= day <= m.days_total:
        raise HTTPException(422, f"day must be between 1 and {m.days_total}")
    return m, day or m.day


@app.get("/mission/now")
def mission_now(day: int | None = None):
    """CMO quick screen: one line per crew member, most urgent first."""
    m, day = _mission_day(day)
    return m.now(day)


@app.get("/mission/alarms")
def mission_alarms(day: int | None = None):
    """Alarm log from day 1 up to this day."""
    m, day = _mission_day(day)
    return m.alarm_log(day)


@app.get("/mission/report")
def mission_report(day: int | None = None, period: str = "day"):
    """Report for the flight surgeon on Earth: one day or the last 7 days."""
    if period not in ("day", "week"):
        raise HTTPException(422, "period must be 'day' or 'week'")
    m, day = _mission_day(day)
    return m.report(day, period)


@app.get("/reference/blood")
def reference_blood(crew: str = "C001"):
    """NASA Inspiration4 blood tests for one crew member. Reference only, not daily status."""
    if crew not in {"C001", "C002", "C003", "C004"}:
        raise HTTPException(404, "Unknown crew member")
    return blood_reference(crew)


@app.get("/insights")
def insights():
    inds = _indicator_statuses()
    level = rules.escalation(inds)
    delay = CONTEXT.comm_delay_s or 0
    items = [{"type": s.type, "status": s.status, "message": s.message, "actions": s.actions}
             for s in inds.values() if s.status in ("yellow", "red")]
    note = None
    if level == "ground" and delay > 60:
        note = f"Ground reply takes at least {round(2 * delay / 60)} min round trip: follow onboard protocol first."
    return {"level": level, "items": items, "comm_note": note}


@app.get("/forecast/{indicator}")
def forecast(indicator: str, days: int = 7):
    if indicator not in INDICATORS:
        raise HTTPException(404, "Unknown indicator")
    values = [m.value for m in list_measurements(type=indicator)]
    lo, hi = BOUNDS[indicator]
    return {"type": indicator, "values": [min(hi, max(lo, v)) for v in analytics.forecast(values, days)]}


@app.get("/tasks", response_model=list[Task])
def tasks():
    return TASKS


@app.post("/tasks/{task_id}/complete", response_model=Task)
def complete_task(task_id: str):
    task = next((t for t in TASKS if t.id == task_id), None)
    if task is None:
        raise HTTPException(404, "Unknown task")
    task.done = True
    return task


@app.post("/demo/reset")
def demo_reset():
    reset()
    return {"ok": True, "measurements": len(MEASUREMENTS)}
