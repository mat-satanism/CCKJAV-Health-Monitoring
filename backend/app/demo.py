"""Synthetic demo mission so the UI has history before real data exists.

The data team can replace this with cleaned datasets: load them into
`Measurement` objects and return them from `demo_mission()`.
"""
import random
from datetime import datetime, timedelta, timezone

from .config import INDICATORS
from .models import Measurement

# (mean, noise) per indicator, plus drift applied in the last days
PROFILE = {
    "heart_rate": (64, 3), "bp_sys": (118, 4), "bp_dia": (76, 3), "glucose": (90, 6),
    "temp": (36.6, 0.15), "sleep_hours": (7.0, 0.5), "mood": (4, 0.4), "exercise_min": (120, 15),
}
DRIFT = {"heart_rate": 2.5, "sleep_hours": -0.5, "mood": -0.4}  # per day, last 5 days


def demo_mission(days: int = 30, seed: int = 7) -> list[Measurement]:
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
