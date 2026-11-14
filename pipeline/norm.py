"""Bayesian personal norm: population priors, and a comparison with the old median rule.

    python -m pipeline.norm

Idea (mentor's one-page concept, raw notes in the wiki): start from what is typical for people in general
(the prior), then update it with this person's own days. After a few days the person's data dominates.
For each indicator the model is a normal level per person with day-to-day noise (Normal-Inverse-Gamma,
so both the person's level and their own spread are learned). The prediction for tomorrow is a band:
95% and 99% of values should fall inside it if nothing has changed.

Priors come from the calm days (days 1-15, no events) of the simulated training missions, which are
calibrated on real people (PMData, LifeSnaps, NHANES; docs/simulation.md):
- m0: average level of a person; tau0: how much people differ from each other;
- sigma: typical day-to-day spread within one person.

The rule itself lives in backend/app/status.py (one rule for the whole app); this module writes
models/norm_priors.json and compares the new rule with the old one on new simulated missions.
"""
import json
import sys
import time

import numpy as np
import pandas as pd

from . import model as M
from . import simulation as sim
from .common import PROCESSED, ROOT

PRIORS_PATH = ROOT / "models" / "norm_priors.json"
KEY = ["mission_id", "astronaut_id"]


def fit_priors(days: pd.DataFrame) -> dict:
    calm = days[days["mission_day"] <= sim.EVENT_FREE_DAYS]
    out = {}
    for ind in sim.INDICATORS:
        g = calm.groupby(KEY)[ind]
        means, variances = g.mean(), g.var()
        out[ind] = {"m0": round(float(means.mean()), 3), "tau0": round(float(means.std()), 3),
                    "sigma": round(float(np.sqrt(variances.mean())), 3)}
    return out


def _status_table(classify, days: pd.DataFrame, method: str) -> pd.DataFrame:
    """Status of every indicator on every day, as the app would show it in the crew mission."""
    rows = []
    for (mid, aid), g in days.sort_values("mission_day").groupby(KEY, sort=False):
        g = g.reset_index(drop=True)
        for ind in sim.INDICATORS:
            values = g[ind].tolist()
            for t in range(len(values)):
                c = classify(ind, values[t], values[:t], population_band=False, method=method)
                if c["status"] != "green":
                    rows.append({"mission_id": mid, "astronaut_id": aid, "mission_day": t + 1,
                                 "indicator": ind, "status": c["status"]})
    return pd.DataFrame(rows, columns=["mission_id", "astronaut_id", "mission_day", "indicator", "status"])


def compare(test_days: pd.DataFrame, test_events: pd.DataFrame) -> pd.DataFrame:
    sys.path.insert(0, str(ROOT / "backend"))
    from app.status import classify

    person_days = test_days[["mission_id", "astronaut_id", "mission_day", "event_free"]]
    calm = person_days[person_days["event_free"] & (person_days["mission_day"] > 7)]
    out = []
    for method in ("median", "bayes"):
        start = time.time()
        flags = _status_table(classify, test_days, method)
        flagged = flags[flags["status"] == "yellow"][KEY + ["mission_day"]].drop_duplicates()
        f = set(map(tuple, flagged.to_numpy()))
        calm_rate = float(np.mean([tuple(r) in f for r in calm[KEY + ["mission_day"]].to_numpy()]))
        caught = []
        for _, e in test_events[test_events["type"].isin(sim.PREDICTED)].iterrows():
            who = test_days.loc[test_days["mission_id"] == e["mission_id"], "astronaut_id"].unique() \
                if e["who"] == "crew" else [e["who"]]
            window = range(int(e["prodrome_start"]), int(e["onset_day"]) + 1)
            caught.append(any((e["mission_id"], w, d) in f for w in who for d in window))
        out.append({"rule": method, "calm_days_yellow": round(calm_rate, 3),
                    "events_flagged_early": round(float(np.mean(caught)), 3), "events": len(caught),
                    "seconds": round(time.time() - start)})
    return pd.DataFrame(out)


def main() -> None:
    cal = sim.calibrate(pd.read_csv(PROCESSED / "daily.csv"), pd.read_csv(PROCESSED / "nhanes_reference.csv"))
    train_days, _ = sim.training_missions(cal, M.TRAIN_MISSIONS, M.TRAIN_SEED)
    priors = fit_priors(train_days)
    PRIORS_PATH.write_text(json.dumps({"note": "Population priors for the Bayesian personal norm, from calm days of "
                                               f"{M.TRAIN_MISSIONS} simulated missions (seed {M.TRAIN_SEED}). "
                                               "See pipeline/norm.py.", "indicators": priors}, indent=1))
    print(f"priors -> {PRIORS_PATH.relative_to(ROOT)}")
    print(pd.DataFrame(priors).T.to_string())
    test_days, test_events = sim.training_missions(cal, 30, M.TEST_SEED)
    print("\nOld rule (median, 3 spreads) vs Bayesian norm, on 30 new simulated missions")
    print(compare(test_days, test_events).to_string(index=False))


if __name__ == "__main__":
    main()
