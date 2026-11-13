"""Static metadata: indicators, body systems, thresholds, environments."""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

INDICATORS: dict[str, dict] = {
    "heart_rate":   {"label": "Heart rate",     "unit": "bpm",   "system": "cardiovascular"},
    "bp_sys":       {"label": "Systolic BP",    "unit": "mmHg",  "system": "cardiovascular"},
    "bp_dia":       {"label": "Diastolic BP",   "unit": "mmHg",  "system": "cardiovascular"},
    "glucose":      {"label": "Blood glucose",  "unit": "mg/dL", "system": "metabolic"},
    "temp":         {"label": "Body temp",      "unit": "°C",    "system": "immune"},
    "sleep_hours":  {"label": "Sleep",          "unit": "h",     "system": "sleep"},
    "mood":         {"label": "Mood",           "unit": "1-5",   "system": "behavioral"},
    "exercise_min": {"label": "Exercise",       "unit": "min",   "system": "musculoskeletal"},
}

# Physically possible value range, used to clamp forecasts.
BOUNDS: dict[str, tuple[float, float]] = {
    "mood": (1, 5), "sleep_hours": (0, 24), "exercise_min": (0, 600),
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
ENVIRONMENTS: dict[str, dict] = {
    "iss":       {"label": "Space station (LEO)", "gravity_g": 0.0,  "comm_delay_s": 0},
    "transit":   {"label": "Deep-space transit",  "gravity_g": 0.0,  "comm_delay_s": 600},
    "rover":     {"label": "Mars surface rover",       "gravity_g": 0.38, "comm_delay_s": 1200},
    "moon_base": {"label": "Moon base",           "gravity_g": 0.16, "comm_delay_s": 1.3},
    "mars_base": {"label": "Mars base",           "gravity_g": 0.38, "comm_delay_s": 1200},
}


def load_thresholds() -> dict[str, dict]:
    raw = json.loads((DATA_DIR / "thresholds.json").read_text())
    return {k: v for k, v in raw.items() if not k.startswith("_")}


THRESHOLDS = load_thresholds()
