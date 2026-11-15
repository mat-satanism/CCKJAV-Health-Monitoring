"""Same crew, same model, a different place: station, transit, Moon base, Mars rover, Mars base.

    python -m pipeline.environments

The Mars base mission (data/processed/sim/) is made by pipeline.build and pipeline.model and is not touched here.
For every other place this writes data/processed/sim/<place>/ (crew, days, events, tasks, predictions): the same
five people, simulated with that place's hazards (simulation.ENVIRONMENTS), scored by the SAME risk model.

The model is trained on Mars-base missions only. So the honest question is whether it still works elsewhere:
for each place, 100 new random missions (the test seed) are simulated with that place's hazards and the model is
scored on them (AUC per event, and mean predicted risk vs how often the event really came).
"""
import json

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from . import model as M
from . import simulation as sim
from .common import PROCESSED, ROOT

SIM = PROCESSED / "sim"
PLACES = [e for e in sim.ENVIRONMENTS if e != "mars_base"]


def trained():
    """The shipped model, rebuilt from the same seeds (training is deterministic) and checked against it."""
    cal = sim.calibrate(pd.read_csv(PROCESSED / "daily.csv"), pd.read_csv(PROCESSED / "nhanes_reference.csv"))
    settings, forests = M.train(sim.training_missions(cal, M.TRAIN_MISSIONS, M.TRAIN_SEED)[0])
    M.fit_calibration(settings, forests, sim.training_missions(cal, M.CAL_MISSIONS, M.CAL_SEED)[0])
    shipped = pd.read_csv(SIM / "predictions.csv")
    again = M.predict_demo(settings, forests, sim.demo_mission(cal)[1])
    cols = [c for c in shipped.columns if c.startswith("risk_")]
    if not np.allclose(shipped[cols].to_numpy(), again[cols].to_numpy(), atol=1e-3):
        raise SystemExit("The rebuilt model differs from sim/predictions.csv: run python -m pipeline.model first.")
    return cal, settings, forests


def score(settings: dict, forests: dict, days: pd.DataFrame) -> pd.DataFrame:
    d, _ = M.sim_features(days, settings["floors"])
    probs, _ = M.risk(forests, d, explain_signs=False, settings=settings)
    rows = []
    for event in sim.PREDICTED:
        y = d[f"label_{event}_48h"].to_numpy()
        p = probs[f"risk_{event}"].to_numpy()
        rows.append({"event": event, "days_with_event_ahead": round(float(y.mean()), 3),
                     "auc": round(roc_auc_score(y, p), 3) if 0 < y.sum() < len(y) else np.nan,
                     "mean_risk_said": round(float(p.mean()), 3)})
    return pd.DataFrame(rows)


def write_demo(cal, settings: dict, forests: dict, env: str) -> pd.DataFrame:
    crew, days, events = sim.demo_mission(cal, env)
    out = SIM / env
    out.mkdir(parents=True, exist_ok=True)
    crew.to_csv(out / "crew.csv", index=False)
    days.to_csv(out / "days.csv", index=False)
    events.to_csv(out / "events.csv", index=False)
    sim.demo_tasks().to_csv(out / "tasks.csv", index=False)
    pred = M.predict_demo(settings, forests, days)
    pred.to_csv(out / "predictions.csv", index=False)
    return pred


def main() -> None:
    cal, settings, forests = trained()
    table = []
    for env in sim.ENVIRONMENTS:
        test_days, _ = sim.training_missions(cal, M.TEST_MISSIONS, M.TEST_SEED, env=env)
        table.append(score(settings, forests, test_days).assign(place=env))
    t = pd.concat(table, ignore_index=True)
    auc = t.pivot(index="event", columns="place", values="auc")[list(sim.ENVIRONMENTS)]
    ahead = t.pivot(index="event", columns="place", values="days_with_event_ahead")[list(sim.ENVIRONMENTS)]
    said = t.pivot(index="event", columns="place", values="mean_risk_said")[list(sim.ENVIRONMENTS)]
    with pd.option_context("display.width", 200):
        print(f"Model trained on Mars-base missions; scored on {M.TEST_MISSIONS} new missions per place.\n")
        print("AUC (0.5 = guessing):\n" + auc.to_string())
        print("\nShare of days with the event in the next 48 h (what really happened):\n" + ahead.to_string())
        print("\nMean risk the model said (should be close to the line above):\n" + said.to_string())
    facts = {"auc": auc.to_dict(), "share_ahead": ahead.to_dict(), "mean_risk_said": said.to_dict()}
    (ROOT / "docs" / "environments.json").write_text(json.dumps(facts, indent=1))
    print()
    for env in PLACES:
        pred = write_demo(cal, settings, forests, env)
        top = pred.loc[pred["mission_day"].between(15, 18)]
        john = top[top["astronaut_id"] == "john"]["risk_infection"].max()
        print(f"sim/{env}/  written; John's infection risk on days 15-18 peaks at {john:.2f}")


if __name__ == "__main__":
    main()
