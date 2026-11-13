"""FastAPI skeleton. Endpoints follow docs/api-contract.md.

In-memory storage for now (to be replaced with SQLite).
Status logic is a stub: thresholds and personal baselines are TODO.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    BodySystemStatus, IndicatorStatus, Measurement, MissionContext, Task,
)

app = FastAPI(title="CCKJAV Health Monitoring API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

MEASUREMENTS: list[Measurement] = []
CONTEXT = MissionContext()
TASKS: list[Task] = [
    Task(id="t1", title="Measure blood pressure", points=10),
    Task(id="t2", title="Log sleep hours", points=5),
    Task(id="t3", title="Mood check-in", points=5),
]

SYSTEM_INDICATORS = {
    "cardiovascular": ["heart_rate", "bp_sys", "bp_dia"],
    "metabolic": ["glucose", "weight"],
    "immune": ["temp"],
    "behavioral": ["mood"],
    "sleep": ["sleep_hours"],
    "musculoskeletal": ["exercise_min"],
}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/context", response_model=MissionContext)
def get_context():
    return CONTEXT


@app.put("/context", response_model=MissionContext)
def put_context(ctx: MissionContext):
    global CONTEXT
    CONTEXT = ctx
    return CONTEXT


@app.post("/measurements", response_model=list[Measurement])
def add_measurements(items: list[Measurement]):
    MEASUREMENTS.extend(items)
    return items


@app.get("/measurements", response_model=list[Measurement])
def list_measurements(type: str | None = None):
    return [m for m in MEASUREMENTS if type is None or m.type == type]


def _indicator_status(ind: str) -> IndicatorStatus:
    values = [m for m in MEASUREMENTS if m.type == ind]
    if not values:
        return IndicatorStatus(type=ind, latest=None, status="grey", message="No data yet")
    latest = max(values, key=lambda m: m.ts).value
    # TODO: thresholds from data/thresholds.json + personal baseline
    return IndicatorStatus(type=ind, latest=latest, status="green")


@app.get("/status")
def status():
    indicators = {i: _indicator_status(i) for inds in SYSTEM_INDICATORS.values() for i in inds}
    order = ["grey", "green", "yellow", "red"]
    systems = [
        BodySystemStatus(
            system=s,
            status=max((indicators[i].status for i in inds), key=order.index),
            indicators=inds,
        )
        for s, inds in SYSTEM_INDICATORS.items()
    ]
    return {"indicators": list(indicators.values()), "systems": systems}


@app.get("/tasks", response_model=list[Task])
def tasks():
    return TASKS


@app.post("/tasks/{task_id}/complete", response_model=Task)
def complete_task(task_id: str):
    task = next(t for t in TASKS if t.id == task_id)
    task.done = True
    return task
