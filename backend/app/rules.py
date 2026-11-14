"""Turn measurements into statuses, messages, actions and an escalation level.

The status rule itself lives in status.py and is shared with the crew mission view.
"""
from . import analytics
from .config import CONTENT, INDICATORS, SYSTEMS
from .models import BodySystemStatus, IndicatorStatus, Measurement
from .status import classify

ORDER = ["grey", "green", "yellow", "red"]

# First piece of advice per indicator, from data/content/indicators.json (each item cites its sources there).
ACTIONS = {ind: CONTENT["indicators"][ind]["advice"][0] for ind in INDICATORS}


def indicator_status(ind: str, series: list[Measurement]) -> IndicatorStatus:
    if not series:
        return IndicatorStatus(type=ind, latest=None, status="grey",
                               message="No data yet", actions=[f"Measure {INDICATORS[ind]['label'].lower()}"])
    ordered = sorted(series, key=lambda m: m.ts)
    values = [m.value for m in ordered]
    latest = values[-1]
    c = classify(ind, latest, values[:-1])
    return IndicatorStatus(
        type=ind, latest=latest, status=c["status"],
        baseline=None if c["norm"] is None else round(c["norm"], 2),
        deviation=None if c["z"] is None else round(c["z"], 2), trend=analytics.trend(values),
        source=ordered[-1].source,
        message=c["message"], actions=[ACTIONS[ind]] if c["status"] != "green" else [],
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
