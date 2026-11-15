"""Turn measurements into statuses, messages, actions and an escalation level.

The status rule itself lives in status.py and is shared with the crew mission view.
"""
from datetime import UTC, datetime

from . import analytics
from .config import CONTENT, FRESH_DAYS, INDICATORS, SYSTEMS
from .models import BodySystemStatus, IndicatorStatus, Measurement
from .status import classify

ORDER = ["grey", "green", "yellow", "red"]

# First piece of advice per indicator, from data/content/indicators.json (each item cites its sources there).
ACTIONS = {ind: CONTENT["indicators"][ind]["advice"][0] for ind in INDICATORS}


def indicator_status(ind: str, series: list[Measurement], now: datetime | None = None) -> IndicatorStatus:
    label = INDICATORS[ind]["label"].lower()
    if not series:
        return IndicatorStatus(type=ind, latest=None, status="grey",
                               message="No data yet", actions=[f"Measure {label}"])
    ordered = sorted(series, key=lambda m: m.ts)
    values = [m.value for m in ordered]
    latest = values[-1]
    age = ((now or datetime.now(UTC)) - ordered[-1].ts).total_seconds() / 86400
    c = classify(ind, latest, values[:-1])
    base = {"type": ind, "latest": latest, "baseline": None if c["norm"] is None else round(c["norm"], 2),
            "deviation": None if c["z"] is None else round(c["z"], 2), "trend": analytics.trend(values),
            "source": ordered[-1].source, "age_days": round(max(age, 0.0), 1)}
    if age > FRESH_DAYS.get(ind, 2):
        return IndicatorStatus(**base, status="grey", message=f"No fresh value: last measured {age:.0f} days ago",
                               actions=[f"Measure {label} when convenient"])
    if c["status"] == "red":
        # One red reading can be a slipped cuff or a typo: confirm it before the ground is called.
        prev = classify(ind, values[-2], values[:-2])["status"] if len(values) > 1 else "green"
        if prev != "red":
            return IndicatorStatus(**base, status="red", recheck=True,
                                   message="Outside safe limits on one reading. Re-measure now to confirm.",
                                   actions=[f"Re-measure {label} now", ACTIONS[ind]])
        return IndicatorStatus(**base, status="red", message="Outside safe limits, confirmed by a second reading",
                               actions=[ACTIONS[ind]])
    return IndicatorStatus(**base, status=c["status"], message=c["message"],
                           actions=[ACTIONS[ind]] if c["status"] != "green" else [])


def system_statuses(indicators: dict[str, IndicatorStatus]) -> list[BodySystemStatus]:
    out = []
    for system in SYSTEMS:
        inds = [i for i, meta in INDICATORS.items() if meta["system"] == system]
        worst = max((indicators[i].status for i in inds), key=ORDER.index)
        out.append(BodySystemStatus(system=system, status=worst, indicators=inds))
    return out


def escalation(indicators: dict[str, IndicatorStatus]) -> str:
    """self: handle alone; crew: tell crewmates/CMO; ground: notify flight surgeon.

    Only a confirmed red (two readings) calls the ground; a single red asks to re-measure and tells the crew.
    """
    reds = sum(s.status == "red" and not s.recheck for s in indicators.values())
    rechecks = sum(s.recheck for s in indicators.values())
    yellows = sum(s.status == "yellow" for s in indicators.values())
    if reds:
        return "ground"
    if rechecks:
        return "crew"
    if yellows >= 2:
        return "crew"
    return "self"
