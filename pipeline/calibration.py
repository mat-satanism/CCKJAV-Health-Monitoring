"""Can the percentages be trusted? When a model says "10%", does the event happen about 1 time in 10?

    python -m pipeline.calibration

Risk model: trained on 400 simulated missions, scored on 100 new ones (the same split as pipeline/model.py).
Wellbeing forecast: real people, each scored by a model that never saw them (pipeline/wellbeing.py).

Scores: the reliability table (predictions grouped by size: mean prediction vs how often it happened), the
expected calibration error (ECE: the average gap, weighted by group size; 0 = perfect) and the Brier score
(mean squared error of the probability; lower is better). The app shows risks as "× usual" = probability /
usual rate, so a miscalibrated probability shows up directly as a wrong multiple.

Recalibration (Platt: a logistic fit on the model's log-odds). Risk model: fitted on 100 separate simulated
missions (seed 99) and shipped in models/risk_model.json; the table compares raw and shipped on the test missions.
Wellbeing forecast: only checked, each person's recalibration fitted on other people; not shipped (no gain).
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss

from . import model as M
from . import simulation as sim
from . import wellbeing as w
from .common import PROCESSED

BINS = [0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0]


def reliability(y: np.ndarray, p: np.ndarray) -> pd.DataFrame:
    g = pd.cut(p, BINS, include_lowest=True)
    t = pd.DataFrame({"y": y, "p": p, "bin": g}).groupby("bin", observed=True).agg(
        days=("y", "size"), predicted=("p", "mean"), happened=("y", "mean"))
    return t.round(3)


def ece(y: np.ndarray, p: np.ndarray) -> float:
    t = reliability(y, p)
    return float((t["days"] * (t["predicted"] - t["happened"]).abs()).sum() / t["days"].sum())


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def platt_cross(y: np.ndarray, p: np.ndarray, groups: np.ndarray, k: int = 5) -> np.ndarray:
    """Recalibrated probabilities, each group's fitted on the other groups only."""
    ids = np.unique(groups)
    fold = {g: i % k for i, g in enumerate(np.random.default_rng(7).permutation(ids))}
    f = np.array([fold[g] for g in groups])
    out = np.empty_like(p)
    for i in range(k):
        test = f == i
        lr = LogisticRegression().fit(_logit(p[~test])[:, None], y[~test])
        out[test] = lr.predict_proba(_logit(p[test])[:, None])[:, 1]
    return out


def summary(name: str, y: np.ndarray, p: np.ndarray, q: np.ndarray) -> dict:
    """p: the model's raw probability; q: recalibrated."""
    return {"model": name, "rate": round(float(y.mean()), 3), "mean_predicted": round(float(p.mean()), 3),
            "ece": round(ece(y, p), 4), "brier": round(brier_score_loss(y, p), 4),
            "ece_recalibrated": round(ece(y, q), 4), "brier_recalibrated": round(brier_score_loss(y, q), 4)}


def risk_model() -> tuple[list[dict], dict[str, pd.DataFrame]]:
    cal = sim.calibrate(pd.read_csv(PROCESSED / "daily.csv"), pd.read_csv(PROCESSED / "nhanes_reference.csv"))
    train_days, _ = sim.training_missions(cal, M.TRAIN_MISSIONS, M.TRAIN_SEED)
    test_days, _ = sim.training_missions(cal, M.TEST_MISSIONS, M.TEST_SEED)
    settings, forests = M.train(train_days)
    M.fit_calibration(settings, forests, sim.training_missions(cal, M.CAL_MISSIONS, M.CAL_SEED)[0])
    d, _ = M.sim_features(test_days, settings["floors"])
    raw, _ = M.risk(forests, d, explain_signs=False)
    shipped, _ = M.risk(forests, d, explain_signs=False, settings=settings)
    rows, tables = [], {}
    for event in sim.PREDICTED:
        y, p, q = d[f"label_{event}_48h"].to_numpy(int), raw[f"risk_{event}"].to_numpy(), shipped[f"risk_{event}"].to_numpy()
        rows.append(summary(f"risk: {event}", y, p, q))
        tables[f"risk: {event}, raw"] = reliability(y, p)
        tables[f"risk: {event}, recalibrated (shipped)"] = reliability(y, q)
    return rows, tables


def wellbeing_model() -> tuple[list[dict], dict[str, pd.DataFrame]]:
    rows, tables = [], {}
    f = w.load("pmdata")
    for key, (name, inputs) in w.EXPORT_TASKS.items():
        task = next(t for t in w.TASKS if t.name == name)
        d = f[f[task.target].notna() & f[task.reference].notna()].reset_index(drop=True)
        p = w.out_of_person_scores(d, w.export_columns(inputs, d), task.target)["random forest"]
        y = d[task.target].to_numpy(int)
        rows.append(summary(f"wellbeing: {key}", y, p, platt_cross(y, p, d["person_id"].to_numpy())))
        tables[f"wellbeing: {key}"] = reliability(y, p)
    return rows, tables


def main() -> None:
    r1, t1 = risk_model()
    r2, t2 = wellbeing_model()
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(pd.DataFrame(r1 + r2).to_string(index=False))
        for name, t in {**t1, **t2}.items():
            print(f"\n{name}\n{t.to_string()}")


if __name__ == "__main__":
    main()
