"""Demo mission for the app: 30 real days of one PMData participant in `Measurement` format.

Chosen person and window (see docs/data.md): pm_p06, 2019-11-06 .. 2019-12-05.
All 30 days have resting heart rate, self-reported sleep, mood and exercise.
Days 1-14 are calm (the personal baseline); on days 18-24 sleep drops to 2-4 h
and resting heart rate rises from about 49 to 51.8 bpm, then recovers.
"""
import pandas as pd

DEMO_PERSON = "pm_p06"
DEMO_START = "2019-11-06"
DEMO_DAYS = 30
ASTRONAUT_ID = "a1"  # default astronaut id in backend/app/models.py

# daily.csv column -> (Measurement.type, unit as in backend/app/config.py, Measurement.source)
INDICATORS = {
    "heart_rate": ("heart_rate", "bpm", "sensor"),
    "sleep_hours": ("sleep_hours", "h", "manual"),
    "mood": ("mood", "1-5", "manual"),
    "exercise_min": ("exercise_min", "min", "sensor"),
}


def demo_mission(daily: pd.DataFrame, person: str = DEMO_PERSON, start: str = DEMO_START,
                 days: int = DEMO_DAYS) -> pd.DataFrame:
    g = daily[daily["person_id"] == person].copy()
    g["date"] = pd.to_datetime(g["date"])
    first = pd.Timestamp(start)
    g = g[(g["date"] >= first) & (g["date"] < first + pd.Timedelta(days=days))]
    rows = []
    for _, r in g.iterrows():
        for col, (typ, unit, source) in INDICATORS.items():
            if pd.notna(r[col]):
                rows.append({
                    "astronaut_id": ASTRONAUT_ID,
                    "mission_day": (r["date"] - first).days + 1,
                    "ts": (r["date"] + pd.Timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "type": typ, "value": round(float(r[col]), 1), "unit": unit, "source": source,
                })
    return pd.DataFrame(rows).sort_values(["mission_day", "type"]).reset_index(drop=True)
