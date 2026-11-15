"""Trend arrow and the 7-day chart forecast. Input `values`: floats in time order (oldest first).

The personal norm and the statuses live in status.py (Bayesian norm, docs/personal-norm.md); the models in
pipeline/ (risk model, wellbeing forecast). The old median baseline() and deviation() were removed on
2026-11-15: nothing used them any more, and they disagreed with the Bayesian norm the app shows.
"""
from statistics import median, pstdev

BASELINE_DAYS = 14   # the forecast's norm window, the same as status.NORM_DAYS (checked: docs/norm-days.md)


def trend(values: list[float], n: int = 5) -> str | None:
    """'up' / 'down' / 'flat' over the last n values. Default: mean step sign."""
    tail = values[-n:]
    if len(tail) < 3:
        return None
    step = (tail[-1] - tail[0]) / (len(tail) - 1)
    spread = (pstdev(values) or 1.0) * 0.15
    return "up" if step > spread else "down" if step < -spread else "flat"


# Forecast settings per indicator, fitted on real people (PMData, LifeSnaps; training people only) by
# `python -m pipeline.forecast_eval`, which also checks that these numbers still match. See docs/forecast.md.
# persistence: share of today's distance from the norm left tomorrow (0 = back to usual at once).
# band: width of the 80% band in units of the person's spread, so that 80% of real values fall inside.
FORECAST = {
    "heart_rate":   {"persistence": 0.9, "band": 2.52},
    "sleep_hours":  {"persistence": 0.0, "band": 1.51},
    "mood":         {"persistence": 0.0, "band": 1.3},
    "exercise_min": {"persistence": 0.0, "band": 1.32},
    "hrv_ms":       {"persistence": 0.5, "band": 1.59},
}
# No open daily data for pressure, glucose, temperature, reaction time: an ASSUMPTION, between the fitted ones.
FORECAST_DEFAULT = {"persistence": 0.5, "band": 1.5}


def forecast_band(values: list[float], days: int = 7, indicator: str | None = None) -> list[tuple[float, float, float]]:
    """Next `days` values as (forecast, low, high); low-high is the 80% band.

    Back to the person's own norm: today's distance from the usual level (median of the last 14 values) shrinks
    by `persistence` every day. The band grows from one day's spread towards the person's full spread.
    """
    window = values[-BASELINE_DAYS:]
    if len(window) < 3:
        return []
    cfg = FORECAST.get(indicator or "", FORECAST_DEFAULT)
    phi, k = cfg["persistence"], cfg["band"]
    norm = median(window)
    spread = pstdev(window)
    gap = values[-1] - norm
    out = []
    for h in range(1, days + 1):
        mid = norm + gap * phi ** h
        half = k * spread * ((1 - phi ** (2 * h)) + 1 / BASELINE_DAYS) ** 0.5
        out.append((round(mid, 2), round(mid - half, 2), round(mid + half, 2)))
    return out


def forecast(values: list[float], days: int = 7, indicator: str | None = None) -> list[float]:
    """Next `days` values: back to the person's own norm (see forecast_band)."""
    return [mid for mid, _, _ in forecast_band(values, days, indicator)]


def linear_forecast(values: list[float], days: int = 7) -> list[float]:
    """The old forecast, kept for comparison: linear extrapolation of the last 7 points."""
    tail = values[-7:]
    if len(tail) < 2:
        return []
    step = (tail[-1] - tail[0]) / (len(tail) - 1)
    return [round(tail[-1] + step * (i + 1), 2) for i in range(days)]
