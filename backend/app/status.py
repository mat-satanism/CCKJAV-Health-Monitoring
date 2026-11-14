"""One status rule for every view (My check-in and the crew mission): personal norm first.

- red: outside the safe limits in data/thresholds.json (red_low / red_high);
- yellow: Z_YELLOW or more spreads away from this person's own norm, the median of the previous
  NORM_DAYS values (at least NORM_MIN of them);
- before a norm exists, the yellow band of data/thresholds.json is used instead;
- green otherwise.

Z_YELLOW = 3: with 8 indicators a 2-spread rule marks someone yellow on 54% of calm simulated days,
3 spreads on 13% (docs/simulation.md). The spread never goes below a per-indicator floor (from the model
file, else MIN_SPREAD), so a very steady person is not flagged for a tiny change. Population thresholds
only decide yellow before a norm exists, so an athlete's usual low resting pulse is not flagged every day.
"""
import json
from statistics import median, stdev

from .config import DATA_DIR, INDICATORS, THRESHOLDS

NORM_DAYS, NORM_MIN = 14, 7
Z_YELLOW = 3.0
MIN_SPREAD = 1.0
MODEL_PATH = DATA_DIR.parent / "models" / "risk_model.json"
FLOORS: dict[str, float] = json.loads(MODEL_PATH.read_text())["floors"] if MODEL_PATH.exists() else {}
DISPLAY_UNIT = {"1-5": "points"}


def display_unit(ind: str) -> str:
    unit = INDICATORS[ind]["unit"]
    return DISPLAY_UNIT.get(unit, unit)


def classify(ind: str, value: float, past: list[float]) -> dict:
    """Status of today's value given earlier values (oldest first). Only the last NORM_DAYS of `past` are used."""
    window = past[-NORM_DAYS:]
    t = THRESHOLDS.get(ind, {})
    unit = display_unit(ind)
    norm = median(window) if len(window) >= NORM_MIN else None
    status, message, z = "green", "As usual for this person", None
    if norm is not None:
        spread = max(stdev(window), FLOORS.get(ind, MIN_SPREAD))
        z = (value - norm) / spread
        if abs(z) >= Z_YELLOW:
            status, message = "yellow", f"{value - norm:+.1f} {unit} vs this person's usual {norm:.1f}"
    elif value < t.get("yellow_low", float("-inf")) or value > t.get("yellow_high", float("inf")):
        status, message = "yellow", "Outside the normal range (no personal norm yet)"
    else:
        message = "Within the normal range (no personal norm yet)"
    red_low, red_high = t.get("red_low"), t.get("red_high")
    if (red_low is not None and value <= red_low) or (red_high is not None and value >= red_high):
        status, message = "red", "Outside safe limits"
    return {"status": status, "message": message, "norm": norm, "z": z, "unit": unit}
