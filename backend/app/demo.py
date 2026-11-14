"""Demo mission for the UI.

Mixed demo (see docs/data.md):
- heart_rate, sleep_hours, mood, exercise_min: 30 real days of one PMData participant,
  read from data/processed/demo_mission.csv. Dates are shifted so the last day is today.
- bp_sys, bp_dia, glucose, temp: no data for this person, so they stay grey.

If the CSV is missing, the demo falls back to a synthetic mission for all indicators.
The data team can replace either source by returning `Measurement` objects from `demo_mission()`.
"""
import csv
import random
from datetime import datetime, timedelta, timezone

from .config import DATA_DIR, INDICATORS
from .models import Measurement

DEMO_CSV = DATA_DIR / "processed" / "demo_mission.csv"
BLOOD_CSV = DATA_DIR / "processed" / "inspiration4_blood.csv"

# Synthetic fallback: (mean, noise) per indicator, plus drift applied in the last days.
PROFILE = {
    "heart_rate": (64, 3), "bp_sys": (118, 4), "bp_dia": (76, 3), "glucose": (90, 6),
    "temp": (36.6, 0.15), "sleep_hours": (7.0, 0.5), "mood": (4, 0.4), "exercise_min": (120, 15),
}
DRIFT = {"heart_rate": 2.5, "sleep_hours": -0.5, "mood": -0.4}  # per day, last 5 days


def _real_mission() -> list[Measurement]:
    with DEMO_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    times = [datetime.fromisoformat(r["ts"].replace("Z", "+00:00")) for r in rows]
    today = datetime.now(timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0)
    shift = today - max(times)
    return [
        Measurement(ts=t + shift, astronaut_id=r["astronaut_id"], type=r["type"],
                    value=float(r["value"]), unit=r["unit"], source=r["source"])
        for r, t in zip(rows, times)
    ]


def _synthetic_mission(days: int = 30, seed: int = 7) -> list[Measurement]:
    rng = random.Random(seed)
    start = datetime.now(timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    out = []
    for d in range(days):
        ts = start + timedelta(days=d)
        late = max(0, d - (days - 6))
        for ind, (mean, noise) in PROFILE.items():
            v = rng.gauss(mean + DRIFT.get(ind, 0) * late, noise)
            if ind == "mood":
                v = min(5, max(1, round(v)))
            out.append(Measurement(ts=ts, type=ind, value=round(v, 1),
                                   unit=INDICATORS[ind]["unit"], source="synthetic"))
    return out


def demo_mission() -> list[Measurement]:
    if DEMO_CSV.exists():
        return _real_mission()
    return _synthetic_mission()


def blood_reference(crew: str = "C001") -> list[dict]:
    """Inspiration4 blood tests for one crew member (NASA, 7 timepoints).

    Not daily data: shown as a reference table next to the body map, not as status.
    """
    with BLOOD_CSV.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["crew_id"] == crew]

    def number(text: str) -> float | None:
        return float(text) if text not in ("", None) else None

    return [
        {
            "panel": r["panel"], "analyte": r["analyte"], "unit": r["unit"],
            "timepoint": r["timepoint"], "days_from_flight": int(r["days_from_flight"]),
            "value": number(r["value"]), "ref_min": number(r["ref_min"]), "ref_max": number(r["ref_max"]),
            "flag": r["flag"] or None, "quality_note": r["quality_note"] or None,
        }
        for r in rows
    ]
