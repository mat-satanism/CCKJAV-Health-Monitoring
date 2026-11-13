"""Turn measurements into statuses, messages, actions and an escalation level."""
from . import analytics
from .config import INDICATORS, SYSTEMS, THRESHOLDS
from .models import BodySystemStatus, IndicatorStatus, Measurement

ORDER = ["grey", "green", "yellow", "red"]
DEVIATION_YELLOW = 2.0  # |z| above this vs personal baseline -> yellow

# Placeholder advice. Replace with sourced content (data/content/*.json).
ACTIONS = {
    "heart_rate": "Rest 10 minutes, then re-measure.",
    "bp_sys": "Sit quietly 5 minutes and re-measure; check fluid intake.",
    "bp_dia": "Sit quietly 5 minutes and re-measure.",
    "glucose": "Re-measure; review last meal and timing.",
    "temp": "Re-measure; watch for infection symptoms.",
    "sleep_hours": "Keep a fixed sleep window; dim lights 1 h before sleep.",
    "mood": "Talk to a crewmate or schedule a call home.",
    "exercise_min": "Log today's resistance and cardio workout.",
}


def _threshold_status(ind: str, value: float) -> str:
    t = THRESHOLDS.get(ind)
    if not t:
        return "green"
    if value <= t["red_low"] or value >= t["red_high"]:
        return "red"
    if value < t["yellow_low"] or value > t["yellow_high"]:
        return "yellow"
    return "green"


def indicator_status(ind: str, series: list[Measurement]) -> IndicatorStatus:
    if not series:
        return IndicatorStatus(type=ind, latest=None, status="grey",
                               message="No data yet", actions=[f"Measure {INDICATORS[ind]['label'].lower()}"])
    values = [m.value for m in sorted(series, key=lambda m: m.ts)]
    latest = values[-1]
    status = _threshold_status(ind, latest)
    message = {"green": "Within normal range", "yellow": "Outside normal range",
               "red": "Outside safe limits"}[status]
    dev = analytics.deviation(values)
    if status == "green" and dev is not None and abs(dev) >= DEVIATION_YELLOW:
        status, message = "yellow", "Unusual for you compared to your baseline"
    return IndicatorStatus(
        type=ind, latest=latest, status=status,
        baseline=analytics.baseline(values), deviation=dev, trend=analytics.trend(values),
        message=message, actions=[ACTIONS[ind]] if status != "green" else [],
    )


def system_statuses(indicators: dict[str, IndicatorStatus]) -> list[BodySystemStatus]:
    out = []
    for system in SYSTEMS:
        inds = [i for i, meta in INDICATORS.items() if meta["system"] == system]
        worst = max((indicators[i].status for i in inds), key=ORDER.index)
        out.append(BodySystemStatus(system=system, status=worst, indicators=inds))
    return out


def escalation(indicators: dict[str, IndicatorStatus]) -> str:
    """self: handle alone; crew: tell crewmates/CMO; ground: notify flight surgeon."""
    reds = sum(s.status == "red" for s in indicators.values())
    yellows = sum(s.status == "yellow" for s in indicators.values())
    if reds:
        return "ground"
    if yellows >= 2:
        return "crew"
    return "self"
