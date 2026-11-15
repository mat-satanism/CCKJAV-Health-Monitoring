from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

# Keep in sync with config.INDICATORS. To add one (e.g. spo2), add it in both places.
IndicatorType = Literal[
    "heart_rate", "bp_sys", "bp_dia", "glucose", "temp", "sleep_hours", "mood", "exercise_min",
    "hrv_ms", "reaction_ms",
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
    value: float = Field(allow_inf_nan=False)
    unit: str = Field(max_length=20)
    source: Literal["manual", "sensor", "synthetic"] = "manual"
    reason: str | None = Field(default=None, max_length=200)   # why a device/medic value was typed by hand

    @field_validator("ts")
    @classmethod
    def _utc(cls, ts: datetime) -> datetime:
        """A time without a time zone is taken as UTC; every stored time is UTC, so times always compare."""
        return ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)


class IndicatorStatus(BaseModel):
    type: IndicatorType
    latest: float | None
    status: Status
    baseline: float | None = None
    deviation: float | None = None
    trend: Literal["up", "down", "flat"] | None = None
    source: Literal["manual", "sensor", "synthetic"] | None = None  # where the latest value came from
    message: str = ""
    actions: list[str] = []
    age_days: float | None = None     # how old the latest value is
    recheck: bool = False             # red on a single reading: re-measure to confirm before calling the ground


class BodySystemStatus(BaseModel):
    system: BodySystem
    status: Status
    indicators: list[IndicatorType]


class Task(BaseModel):
    id: str
    title: str
    points: int
    done: bool = False
    feedback: Literal["better", "same", "worse", "gone"] | None = None   # how the person feels after it
    feedback_ts: datetime | None = None


class TaskFeedback(BaseModel):
    outcome: Literal["better", "same", "worse", "gone"]


class MissionContext(BaseModel):
    environment: Environment = "iss"
    mission_day: int = 1
    gravity_g: float | None = None
    comm_delay_s: float | None = None
