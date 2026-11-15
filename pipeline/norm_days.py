"""How many days does the personal norm need? Checked on real people (PMData, LifeSnaps).

    python -m pipeline.norm_days

The app's Bayesian norm (backend/app/status.py) has two numbers: BAYES_MIN, the days of the person's own data
before the norm is used (the "calibration week", now 6), and NORM_DAYS, the window it learns from (now 14).
The team's question: the NASA decision-support concept talks about a first week; we use 14 days. Which is right?

1. Calibration: after k days, how far is the norm's centre from where the person really sits over the next 30
   days (median of days k+1..k+30)? In units of that month's spread. k = 3 ... 14.
2. Window: with the last W values (W = 7 ... 28), does the 95% band hold the next real value 95% of the time,
   how wide is it, and on what share of days does the app's rule turn the person yellow?

Real days include real bad days, so the yellow share is not purely false alarms; it is compared between windows.
"""
import sys

import numpy as np
import pandas as pd

from .common import PROCESSED, ROOT

sys.path.insert(0, str(ROOT / "backend"))
from app import status  # pyright: ignore[reportMissingImports]  (backend/ is put on the path above)

SERIES = [   # (app indicator, daily.csv column, dataset)
    ("heart_rate", "heart_rate", "pmdata"), ("heart_rate", "heart_rate", "lifesnaps"),
    ("sleep_hours", "sleep_hours", "pmdata"), ("sleep_hours", "sleep_hours_device", "lifesnaps"),
    ("mood", "mood", "pmdata"),
    ("exercise_min", "exercise_min", "pmdata"), ("exercise_min", "exercise_min", "lifesnaps"),
    ("hrv_ms", "hrv_ms", "lifesnaps"),
]
CALIBRATION_DAYS = [3, 4, 5, 6, 7, 8, 10, 14]
WINDOWS = [7, 10, 14, 21, 28]
NEXT_MONTH = 30


def series(min_len: int) -> list[tuple[str, str, list[float]]]:
    daily = pd.read_csv(PROCESSED / "daily.csv").sort_values(["person_id", "date"])
    out = []
    for ind, col, ds in SERIES:
        d = daily[(daily["source_dataset"] == ds) & daily[col].notna()]
        for pid, g in d.groupby("person_id"):
            v = g[col].astype(float).tolist()
            if len(v) >= min_len:
                out.append((ind, pid, v))
    return out


def calibration() -> pd.DataFrame:
    """Error of the norm's centre after k days vs the person's next 30 days, in that month's spreads."""
    data = series(max(CALIBRATION_DAYS) + NEXT_MONTH)
    rows = []
    old_min = status.BAYES_MIN
    status.BAYES_MIN = 1
    try:
        for ind, pid, v in data:
            for k in CALIBRATION_DAYS:
                month = v[k:k + NEXT_MONTH]
                spread = float(np.std(month)) or 1.0
                pred = status.predictive(ind, v[:k])
                rows.append({"indicator": ind, "person": pid, "days": k,
                             "error": abs(pred["center"] - float(np.median(month))) / spread})
    finally:
        status.BAYES_MIN = old_min
    out = pd.DataFrame(rows)
    table = out.groupby(["indicator", "days"])["error"].median().unstack("days")
    table.loc["ALL (median of indicators)"] = table.median()
    return table.round(2)


def windows() -> pd.DataFrame:
    """Per window W: 95% coverage of the next value, band width in the person's spreads, share of yellow days."""
    data = series(max(WINDOWS) + 30)
    rows = []
    old = status.NORM_DAYS
    try:
        for w in WINDOWS:
            status.NORM_DAYS = w
            for ind, pid, v in data:
                spread = float(np.std(v)) or 1.0
                for t in range(max(WINDOWS), len(v)):    # same days for every window
                    past, x = v[:t], v[t]
                    pred = status.predictive(ind, past)
                    c = status.classify(ind, x, past, population_band=False)
                    rows.append({"window": w, "indicator": ind, "inside95": abs(x - pred["center"]) <= pred["h95"],
                                 "width": 2 * pred["h95"] / spread, "yellow": c["status"] == "yellow"})
    finally:
        status.NORM_DAYS = old
    r = pd.DataFrame(rows)
    per = r.groupby(["window", "indicator"])[["inside95", "width", "yellow"]].mean()
    allrow = per.groupby("window").mean()
    allrow["indicator"] = "ALL"
    out = pd.concat([per.reset_index(), allrow.reset_index()], ignore_index=True)
    return out.set_index(["indicator", "window"]).sort_index().round(3)


def simulation_check() -> pd.DataFrame:
    """Real data has no labelled events, so the safety side is checked on 30 new simulated missions: per window,
    the share of calm days with any yellow and the share of events flagged between the first signs and the start."""
    from . import model as M
    from . import norm as N
    from . import simulation as sim

    cal = sim.calibrate(pd.read_csv(PROCESSED / "daily.csv"), pd.read_csv(PROCESSED / "nhanes_reference.csv"))
    days, events = sim.training_missions(cal, 30, M.TEST_SEED)
    calm = days[days["event_free"] & (days["mission_day"] > 7)][N.KEY + ["mission_day"]]
    rows = []
    old = status.NORM_DAYS
    try:
        for w in WINDOWS:
            status.NORM_DAYS = w
            flags = N._status_table(status.classify, days, "bayes")
            f = set(map(tuple, flags[flags["status"] == "yellow"][N.KEY + ["mission_day"]].to_numpy()))
            row = {"window": w, "calm_days_yellow": float(np.mean([tuple(r) in f for r in calm.to_numpy()]))}
            caught = {}
            for _, e in events[events["type"].isin(sim.PREDICTED)].iterrows():
                who = days.loc[days["mission_id"] == e["mission_id"], "astronaut_id"].unique() \
                    if e["who"] == "crew" else [e["who"]]
                hit = any((e["mission_id"], a, d) in f for a in who
                          for d in range(int(e["prodrome_start"]), int(e["onset_day"]) + 1))
                caught.setdefault(e["type"], []).append(hit)
            row["events_flagged_early"] = float(np.mean([h for v in caught.values() for h in v]))
            row |= {f"early_{k}": float(np.mean(v)) for k, v in sorted(caught.items())}
            rows.append(row)
    finally:
        status.NORM_DAYS = old
    return pd.DataFrame(rows).set_index("window").round(3)


def main() -> None:
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print("1. Calibration: error of the norm after k days vs the next 30 days (in spreads; lower is better)")
        print(calibration().to_string())
        print("\n2. Window: share of next values inside the 95% band, band width (in spreads), share of yellow days")
        print(windows().to_string())
        print("\n3. Simulation (labelled events): calm days with any yellow, events flagged early, per event type")
        print(simulation_check().T.to_string())


if __name__ == "__main__":
    main()
