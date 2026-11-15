"""Static metadata: indicators, body systems, thresholds, environments."""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# collected_by: who provides the value, as on the space station (docs/data-entry.md):
#   device = the wearable sends it by itself (CSA Bio-Monitor measures pulse, ECG, blood pressure, breathing,
#            skin temperature, activity); test = the app's 3-minute reaction test records it;
#   medic  = the crew medical officer measures it at a check-up or when someone is unwell;
#   self   = only the astronaut can say it (how they feel).
INDICATORS: dict[str, dict] = {
    "heart_rate":   {"label": "Heart rate",     "unit": "bpm",   "system": "cardiovascular", "collected_by": "device"},
    "bp_sys":       {"label": "Systolic BP",    "unit": "mmHg",  "system": "cardiovascular", "collected_by": "device"},
    "bp_dia":       {"label": "Diastolic BP",   "unit": "mmHg",  "system": "cardiovascular", "collected_by": "device"},
    "glucose":      {"label": "Blood glucose",  "unit": "mg/dL", "system": "metabolic", "collected_by": "medic"},
    "temp":         {"label": "Body temp",      "unit": "°C",    "system": "immune", "collected_by": "medic"},
    "sleep_hours":  {"label": "Sleep",          "unit": "h",     "system": "sleep", "collected_by": "device"},
    "mood":         {"label": "Mood",           "unit": "1-5",   "system": "behavioral", "collected_by": "self"},
    "exercise_min": {"label": "Exercise",       "unit": "min",   "system": "musculoskeletal", "collected_by": "device"},
    "hrv_ms":       {"label": "Heart rate variability", "unit": "ms", "system": "cardiovascular", "collected_by": "device"},
    "reaction_ms":  {"label": "Reaction time",  "unit": "ms",    "system": "behavioral", "collected_by": "test"},
}

# How long a value stays "fresh", in days. Daily signals are measured every day; blood pressure, glucose and
# temperature are measured at planned check-ups or when something is wrong, not every day (NASA practice).
# An older value is shown grey ("no fresh data"), never red.
FRESH_DAYS: dict[str, float] = {
    "heart_rate": 2, "sleep_hours": 2, "mood": 2, "exercise_min": 2, "hrv_ms": 2, "reaction_ms": 2,
    "bp_sys": 7, "bp_dia": 7, "glucose": 7, "temp": 7,
}

# Plausible input range (not medical limits): values outside are rejected as
# typos/sensor errors, and forecasts are clamped to it.
BOUNDS: dict[str, tuple[float, float]] = {
    "heart_rate": (20, 250), "bp_sys": (50, 260), "bp_dia": (30, 160),
    "glucose": (20, 600), "temp": (30, 45), "sleep_hours": (0, 24),
    "mood": (1, 5), "exercise_min": (0, 600), "hrv_ms": (5, 300), "reaction_ms": (100, 3000),
}

SYSTEMS: dict[str, dict] = {
    "cardiovascular":  {"label": "Heart & vessels"},
    "musculoskeletal": {"label": "Bones & muscles"},
    "behavioral":      {"label": "Mind & mood"},
    "immune":          {"label": "Immune system"},
    "metabolic":       {"label": "Metabolism"},
    "sleep":           {"label": "Sleep"},
}

# comm_delay_s values are one-way approximations; verify before the pitch.
ENVIRONMENTS: dict[str, dict] = {   # "note": what this place changes in the simulated mission (docs/environments.md)
    "iss":       {"label": "Space station (LEO)", "gravity_g": 0.0,  "comm_delay_s": 0,
                  "note": "0 g: muscles and blood vessels decondition faster. Earth's magnetic field shields from solar "
                          "flares. Doctors on Earth see the data live."},
    "transit":   {"label": "Deep-space transit",  "gravity_g": 0.0,  "comm_delay_s": 600,
                  "note": "0 g and no planet to shield: the most radiation and the fastest deconditioning. "
                          "Signal delay up to 10 min."},
    "rover":     {"label": "Mars surface rover",       "gravity_g": 0.38, "comm_delay_s": 1200,
                  "note": "A small pressurised cabin: CO2 builds up sooner than in a base. 20 min signal delay."},
    "moon_base": {"label": "Moon base",           "gravity_g": 0.16, "comm_delay_s": 1.3,
                  "note": "1/6 g, no air or magnetic field: about twice the radiation of Mars. Doctors on Earth are "
                          "1.3 s away."},
    "mars_base": {"label": "Mars base",           "gravity_g": 0.38, "comm_delay_s": 1200,
                  "note": "The original mission: 0.38 g, a thin atmosphere, a 20 min signal delay to Earth."},
}


def load_thresholds() -> dict[str, dict]:
    raw = json.loads((DATA_DIR / "thresholds.json").read_text())
    return {k: v for k, v in raw.items() if not k.startswith("_")}


THRESHOLDS = load_thresholds()


def _load_content(name: str) -> dict[str, dict]:
    raw = json.loads((DATA_DIR / "content" / f"{name}.json").read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_")}


# Plain-language explanations and advice with sources (data/content/*.json).
CONTENT: dict[str, dict] = {name: _load_content(name) for name in ("indicators", "systems", "sources", "measurement_plan", "exposures")}

COLLECTED_BY_TEXT = {"device": "the wearable sends it automatically", "test": "the 3-minute test records it",
                     "medic": "the crew medical officer measures it", "self": "the astronaut reports it"}
