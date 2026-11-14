"""One status rule for every view (My check-in and the crew mission): personal norm first.

- red: outside the safe limits in data/thresholds.json (red_low / red_high). Only measured facts turn red,
  because red takes someone off heavy tasks;
- yellow (Bayesian personal norm, method="bayes", the default): today's value is outside this person's
  99% prediction band, or outside the 95% band two days in a row. One reading just outside 95% stays green
  with "check again tomorrow";
- before BAYES_MIN days of the person's data, the yellow band of data/thresholds.json is used instead
  (only in My check-in; the crew mission shows no yellow in its first week);
- green otherwise.

Bayesian norm (mentor's suggestion; pipeline/norm.py): start from the population prior in
models/norm_priors.json (typical level, how much people differ, typical day-to-day spread), then update it
with the person's last NORM_DAYS values. Normal-Inverse-Gamma model, so the person's own level AND own spread
are learned; the prediction for today is a Student-t band. The mentor's concept marks "outside 99%" as red;
here it is yellow, because red is reserved for safety limits that take someone off a task.

method="median" keeps the old rule (median of the last 14 days, yellow at 3+ spreads) for comparison.
"""
import json
from statistics import median, stdev

from .config import DATA_DIR, INDICATORS, THRESHOLDS

NORM_DAYS, NORM_MIN = 14, 7       # median rule
BAYES_MIN = 6                      # days of the person's own data before the Bayesian norm is used ("calibration")
Z_YELLOW = 3.0
MIN_SPREAD = 1.0
ALPHA0 = 3.0                       # weak prior on the person's spread: a few days of data outweigh it
Z95, Z99 = 1.959964, 2.575829
MODEL_PATH = DATA_DIR.parent / "models" / "risk_model.json"
PRIORS_PATH = DATA_DIR.parent / "models" / "norm_priors.json"
FLOORS: dict[str, float] = json.loads(MODEL_PATH.read_text())["floors"] if MODEL_PATH.exists() else {}
PRIORS: dict[str, dict] = json.loads(PRIORS_PATH.read_text())["indicators"] if PRIORS_PATH.exists() else {}
DISPLAY_UNIT = {"1-5": "points"}


def display_unit(ind: str) -> str:
    unit = INDICATORS[ind]["unit"]
    return DISPLAY_UNIT.get(unit, unit)


def _t_quantile(z: float, df: float) -> float:
    """Student-t quantile from the normal one (Cornish-Fisher expansion; accurate enough for df >= 6)."""
    return (z + (z**3 + z) / (4 * df) + (5 * z**5 + 16 * z**3 + 3 * z) / (96 * df**2)
            + (3 * z**7 + 19 * z**5 + 17 * z**3 - 15 * z) / (384 * df**3))


def predictive(ind: str, past: list[float]) -> dict | None:
    """Bayesian prediction for the next value from the last NORM_DAYS values: center, scale, 95% and 99% half-widths."""
    window = past[-NORM_DAYS:]
    n, p = len(window), PRIORS.get(ind)
    if p is None or n < BAYES_MIN:
        return None
    sigma2, tau2 = p["sigma"] ** 2, max(p["tau0"], 1e-6) ** 2
    k0, b0 = sigma2 / tau2, sigma2 * (ALPHA0 - 1)
    ybar = sum(window) / n
    ss = sum((y - ybar) ** 2 for y in window)
    kn, an = k0 + n, ALPHA0 + n / 2
    mn = (k0 * p["m0"] + n * ybar) / kn
    bn = b0 + ss / 2 + k0 * n * (ybar - p["m0"]) ** 2 / (2 * kn)
    scale = (bn * (kn + 1) / (an * kn)) ** 0.5
    df = 2 * an
    return {"center": mn, "scale": scale, "h95": _t_quantile(Z95, df) * scale, "h99": _t_quantile(Z99, df) * scale}


def _red(ind: str, value: float) -> bool:
    t = THRESHOLDS.get(ind, {})
    red_low, red_high = t.get("red_low"), t.get("red_high")
    return (red_low is not None and value <= red_low) or (red_high is not None and value >= red_high)


def _population_yellow(ind: str, value: float) -> bool:
    t = THRESHOLDS.get(ind, {})
    lo, hi = t.get("yellow_low"), t.get("yellow_high")
    return (lo is not None and value < lo) or (hi is not None and value > hi)


def classify(ind: str, value: float, past: list[float], population_band: bool = True, method: str = "bayes") -> dict:
    """Status of today's value given earlier values (oldest first).

    population_band=False (crew mission): during the first days only red can fire; the crew is still
    calibrating, like a real mission's first week, so nobody turns yellow just for being an athlete.
    Returns status, message, norm (center), z (distance in prediction scales), spread, unit and the 95% band.
    """
    unit = display_unit(ind)
    out = {"status": "green", "message": "As usual for this person", "norm": None, "z": None, "spread": None,
           "low": None, "high": None, "unit": unit}
    if method == "median":
        window = past[-NORM_DAYS:]
        if len(window) >= NORM_MIN:
            norm = median(window)
            spread = max(stdev(window), FLOORS.get(ind, MIN_SPREAD))
            z = (value - norm) / spread
            out.update(norm=norm, z=z, spread=spread, low=norm - Z_YELLOW * spread, high=norm + Z_YELLOW * spread)
            if abs(z) >= Z_YELLOW:
                out.update(status="yellow", message=f"{value - norm:+.1f} {unit} vs this person's usual {norm:.1f}")
    else:
        pred = predictive(ind, past)
        if pred is not None:
            c = pred["center"]
            out.update(norm=c, z=(value - c) / pred["scale"], spread=pred["scale"],
                       low=c - pred["h95"], high=c + pred["h95"])
            diff = f"{value - c:+.1f} {unit} vs this person's usual {c:.1f}"
            if abs(value - c) > pred["h99"]:
                out.update(status="yellow", message=f"{diff}: very unusual for this person")
            elif abs(value - c) > pred["h95"]:
                prev = predictive(ind, past[:-1]) if past else None
                if prev is not None and abs(past[-1] - prev["center"]) > prev["h95"]:
                    out.update(status="yellow", message=f"{diff}: outside the usual range two days in a row")
                else:
                    out.update(message=f"{diff}: slightly outside the usual range, check again tomorrow")
    if out["norm"] is None:
        if population_band and _population_yellow(ind, value):
            out.update(status="yellow", message="Outside the normal range (no personal norm yet)")
        elif population_band:
            out["message"] = "Within the normal range (no personal norm yet)"
        else:
            out["message"] = f"Learning this person's norm ({min(len(past), BAYES_MIN)} of {BAYES_MIN} days)"
    if _red(ind, value):
        out.update(status="red", message="Outside safe limits")
    return out
