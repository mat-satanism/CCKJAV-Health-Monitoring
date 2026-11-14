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
    "hrv_ms":       {"label": "Heart rate variability", "unit": "ms", "system": "cardiovascular"},
    "reaction_ms":  {"label": "Reaction time",  "unit": "ms",    "system": "behavioral"},
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


def _load_content(name: str) -> dict[str, dict]:
    raw = json.loads((DATA_DIR / "content" / f"{name}.json").read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_")}


# Plain-language explanations and advice with sources (data/content/*.json).
CONTENT: dict[str, dict] = {name: _load_content(name) for name in ("indicators", "systems", "sources", "measurement_plan", "exposures")}
