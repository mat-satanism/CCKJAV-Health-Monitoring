"""Demo mission for the app ("My check-in"): 30 days of one PMData participant in `Measurement` format.

Chosen person and window (see docs/data.md): pm_p06, 2019-11-06 .. 2019-12-05.
Real: resting heart rate, self-reported sleep, mood and exercise (all 30 days).
Days 1-14 are calm (the personal baseline); on days 18-24 sleep drops to 2-4 h
and resting heart rate rises from about 49 to 51.8 bpm, then recovers.
SYNTHETIC (source = "synthetic"): blood pressure, glucose and temperature, which this person never measured.
Generated like the crew simulation: personal level from NHANES percentiles, day-to-day spread and the
temperature level are the documented assumptions in pipeline/simulation.py (ASSUMED).
"""
import numpy as np
import pandas as pd

from . import simulation as sim

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


SYNTHETIC_SEED = 606
SYNTHETIC = {"bp_sys": "mmHg", "bp_dia": "mmHg", "glucose": "mg/dL", "temp": "°C"}


TYPICAL = 0.5  # personal level = NHANES median (a typical healthy adult); only day-to-day changes are random


def synthetic_vitals(nhanes_reference: pd.DataFrame, days: int, seed: int = SYNTHETIC_SEED) -> dict[str, np.ndarray]:
    """Blood pressure, glucose and temperature for one typical healthy person, `days` long."""
    rng = np.random.default_rng(seed)
    ref = nhanes_reference.set_index("indicator")
    pcts = [0.01, 0.05, 0.50, 0.95, 0.99]

    def level(ind: str, u: float) -> float:
        r = ref.loc[ind]
        return float(np.interp(u, pcts, [r["p01"], r["p05"], r["p50"], r["p95"], r["p99"]]))

    out = {}
    for ind, u in (("bp_sys", TYPICAL), ("bp_dia", TYPICAL), ("glucose", TYPICAL)):
        a = sim.ASSUMED[ind]
        out[ind] = np.round(sim._ar1(rng, days, level(ind, u), a["sd"], a["phi"]))
    t = sim.ASSUMED["temp"]
    out["temp"] = np.round(sim._ar1(rng, days, t["mean"], t["sd"], t["phi"]), 1)
    return out


def demo_mission(daily: pd.DataFrame, person: str = DEMO_PERSON, start: str = DEMO_START,
                 days: int = DEMO_DAYS, nhanes_reference: pd.DataFrame | None = None) -> pd.DataFrame:
    """Real rows for the person; with `nhanes_reference`, also synthetic pressure, glucose and temperature."""
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
    if nhanes_reference is not None:
        vitals = synthetic_vitals(nhanes_reference, days)
        for day in range(1, days + 1):
            ts = (first + pd.Timedelta(days=day - 1, hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ")
            for typ, unit in SYNTHETIC.items():
                rows.append({"astronaut_id": ASTRONAUT_ID, "mission_day": day, "ts": ts, "type": typ,
                             "value": float(vitals[typ][day - 1]), "unit": unit, "source": "synthetic"})
    return pd.DataFrame(rows).sort_values(["mission_day", "type"]).reset_index(drop=True)
