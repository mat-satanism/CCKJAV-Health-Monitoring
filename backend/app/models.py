from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

IndicatorType = Literal[
    "heart_rate", "bp_sys", "bp_dia", "glucose", "temp", "sleep_hours", "mood",
    "spo2", "weight", "exercise_min", "radiation_dose",
]
Status = Literal["green", "yellow", "red", "grey"]
BodySystem = Literal[
    "cardiovascular", "musculoskeletal", "behavioral", "immune", "metabolic", "sleep",
]
Environment = Literal["iss", "transit", "rover", "moon_base", "mars_base"]


class Measurement(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    astronaut_id: str = "a1"
    ts: datetime
    type: IndicatorType
    value: float
    unit: str
    source: Literal["manual", "sensor", "synthetic"] = "manual"


class IndicatorStatus(BaseModel):
    type: IndicatorType
    latest: float | None
    status: Status
    baseline: float | None = None
    deviation: float | None = None
    trend: Literal["up", "down", "flat"] | None = None
    message: str = ""
    actions: list[str] = []


class BodySystemStatus(BaseModel):
    system: BodySystem
    status: Status
    indicators: list[IndicatorType]


class Task(BaseModel):
    id: str
    title: str
    points: int
    done: bool = False


class MissionContext(BaseModel):
    environment: Environment = "iss"
    mission_day: int = 1
    gravity_g: float | None = None
    comm_delay_s: float | None = None
