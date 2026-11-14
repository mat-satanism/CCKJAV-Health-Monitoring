"""Analytics interface: the plug-in point for the data/ML team.

Keep these function signatures stable; swap the bodies for real models.
Input `values` is a list of floats ordered by time (oldest first).
"""
from statistics import median, pstdev

BASELINE_DAYS = 14


def baseline(values: list[float]) -> float | None:
    """Personal norm. Default: median of the first BASELINE_DAYS values."""
    window = values[:BASELINE_DAYS]
    return median(window) if len(window) >= 3 else None


def deviation(values: list[float]) -> float | None:
    """How unusual the latest value is vs the personal norm (z-score-like)."""
    window = values[:BASELINE_DAYS]
    base = baseline(values)
    if base is None or len(values) <= len(window):
        return None
    spread = pstdev(window) or 1.0
    return round((values[-1] - base) / spread, 2)


def trend(values: list[float], n: int = 5) -> str | None:
    """'up' / 'down' / 'flat' over the last n values. Default: mean step sign."""
    tail = values[-n:]
    if len(tail) < 3:
        return None
    step = (tail[-1] - tail[0]) / (len(tail) - 1)
    spread = (pstdev(values) or 1.0) * 0.15
    return "up" if step > spread else "down" if step < -spread else "flat"


def forecast(values: list[float], days: int = 7) -> list[float]:
    """Next `days` values. Default: linear extrapolation of the last 7 points."""
    tail = values[-7:]
    if len(tail) < 2:
        return []
    step = (tail[-1] - tail[0]) / (len(tail) - 1)
    return [round(tail[-1] + step * (i + 1), 2) for i in range(days)]
