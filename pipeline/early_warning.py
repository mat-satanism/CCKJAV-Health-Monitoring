"""Does the model warn early without crying wolf? Model vs the simple status rules, on new simulated missions.

    python -m pipeline.early_warning

Two ways the app can raise a flag for an astronaut:
- rules: any indicator yellow or red that day (the Bayesian personal norm and safety limits, backend/app/status.py);
- model: any event risk at 3x the usual level or more (doctors see it) or 5x (the CMO is asked to confirm fitness).

For each, on 100 new simulated missions (seed never used in training):
- before an event: share of events with a flag on any of the 6 days up to its start (the person, or for a
  crew-wide event any crew member), and how many days ahead the first flag came (median);
- calm week: share of astronauts with a flag on mission days 10-15, which are always event-free (no early signs
  either). Same 6-day length, so the two shares compare directly: a method that flags most calm weeks too gives
  warnings nobody can act on.

If the risk model carries the recalibration of docs/calibration.md (pipeline.model.fit_calibration), it is used;
otherwise the raw forest. Rerun after the model changes.
"""
import inspect
import sys

import numpy as np
import pandas as pd

from . import model as M
from . import norm as N
from . import simulation as sim
from .common import PROCESSED, ROOT

sys.path.insert(0, str(ROOT / "backend"))
from app import status  # pyright: ignore[reportMissingImports]  (backend/ is put on the path above)

WINDOW = 5                    # days before the start that count as "early"
CALM_DAYS = (10, 15)          # always event-free in the simulation, the norm is already learned
THRESHOLDS = (3.0, 5.0)       # backend/app/mission.py: WATCH_MULTIPLE, HIGH_MULTIPLE
METHODS = {"rules": "Status rules (any yellow or red)", "model_3x": "Model, risk 3x usual or more",
           "model_5x": "Model, risk 5x usual or more"}


def flags_table() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, bool]:
    """Per astronaut-day of the test missions: does each method raise a flag? Also the days and the events."""
    cal = sim.calibrate(pd.read_csv(PROCESSED / "daily.csv"), pd.read_csv(PROCESSED / "nhanes_reference.csv"))
    train_days, _ = sim.training_missions(cal, M.TRAIN_MISSIONS, M.TRAIN_SEED)
    test_days, events = sim.training_missions(cal, M.TEST_MISSIONS, M.TEST_SEED)
    settings, forests = M.train(train_days)
    calibrated = hasattr(M, "fit_calibration")
    kwargs = {}
    if calibrated:
        M.fit_calibration(settings, forests, sim.training_missions(cal, M.CAL_MISSIONS, M.CAL_SEED)[0])
        if "settings" in inspect.signature(M.risk).parameters:
            kwargs["settings"] = settings
    d, _ = M.sim_features(test_days, settings["floors"])
    probs, _ = M.risk(forests, d, explain_signs=False, **kwargs)
    multiple = pd.concat([probs[f"risk_{e}"] / settings["events"][e]["base_rate"] for e in sim.PREDICTED], axis=1)
    t = d[N.KEY + ["mission_day"]].copy()
    for thr in THRESHOLDS:
        t[f"model_{thr:g}x"] = (multiple >= thr).any(axis=1).to_numpy()
    s = N._status_table(status.classify, test_days, "bayes")
    rules = s.assign(flag=s["status"].isin(["yellow", "red"])).groupby(N.KEY + ["mission_day"])["flag"].any()
    t = t.set_index(N.KEY + ["mission_day"])
    t["rules"] = rules.reindex(t.index).fillna(False).astype(bool)
    return t.sort_index(), test_days, events, calibrated


def summary(t: pd.DataFrame, days: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    crew = days.groupby("mission_id")["astronaut_id"].unique()
    rows = []
    for col, label in METHODS.items():
        leads = []
        for _, e in events[events["type"].isin(sim.PREDICTED)].iterrows():
            who = crew[e["mission_id"]] if e["who"] == "crew" else [e["who"]]
            on = int(e["onset_day"])
            lead = None
            for day in range(on - WINDOW, on + 1):                 # earliest flag in the window
                if any(t.at[(e["mission_id"], a, day), col] for a in who if (e["mission_id"], a, day) in t.index):
                    lead = on - day
                    break
            leads.append(lead)
        leads = pd.Series(leads, dtype=float)
        calm = [t.loc[(m, a, slice(*CALM_DAYS)), col].any() for m, a in days[N.KEY].drop_duplicates().to_numpy()]
        calm_days = days[(days["mission_day"] > 7) & days["event_free"]][N.KEY + ["mission_day"]]
        per_day = float(np.mean([t.at[tuple(r), col] for r in calm_days.to_numpy()]))
        rows.append({"method": label, "flagged_before_events": round(float(leads.notna().mean()), 3),
                     "median_days_ahead": float(leads.median()),
                     "flagged_in_a_calm_week": round(float(np.mean(calm)), 3),
                     "flags_per_calm_astronaut_week": round(per_day * 7, 2), "events": len(leads)})
    return pd.DataFrame(rows)


def run() -> tuple[pd.DataFrame, bool]:
    t, days, events, calibrated = flags_table()
    return summary(t, days, events), calibrated


def main() -> None:
    table, calibrated = run()
    print(f"risk model: {'recalibrated' if calibrated else 'raw forest (no recalibration in this version)'}")
    with pd.option_context("display.width", 200, "display.max_columns", 10):
        print(table.to_string(index=False))


if __name__ == "__main__":
    main()
