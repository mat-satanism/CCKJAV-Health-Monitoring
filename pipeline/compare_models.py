"""Which risk model to use: logistic regression vs random forest vs LightGBM, on the same data and split.

    python -m pipeline.compare_models

Train: 400 simulated missions (seed 7). Test: 100 new missions (seed 1234), never seen in training.
Metrics per event:
- ROC AUC: how well the model ranks risky days above calm ones (0.5 = guessing, 1 = perfect);
- PR AUC: the same but focused on the rare positive days (better for rare events);
- precision / recall / F1 when the top 5% riskiest astronaut-days raise an alert
  (precision: share of alerts that were real; recall: share of real events that got an alert).
Also: the real-data check on PMData mood (does anything learned on the simulation carry over?).
Results go to docs/model-comparison.md by hand; the numbers depend only on the seeds.
"""
import time

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import model as M
from . import simulation as sim
from .common import PROCESSED

CANDIDATES = {
    "logistic": lambda: make_pipeline(StandardScaler(), LogisticRegression(C=M.C, max_iter=2000)),
    "random_forest": lambda: RandomForestClassifier(n_estimators=300, min_samples_leaf=20, n_jobs=-1,
                                                    random_state=42),
    "lightgbm": lambda: LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=15, min_child_samples=40,
                                       subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=42,
                                       verbose=-1),
}


def scores(y: np.ndarray, p: np.ndarray) -> dict:
    alert = p >= np.quantile(p, 1 - M.ALERT_SHARE)
    tp = float((alert & (y == 1)).sum())
    precision, recall = tp / max(alert.sum(), 1), tp / max((y == 1).sum(), 1)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"roc_auc": roc_auc_score(y, p), "pr_auc": average_precision_score(y, p),
            "precision": precision, "recall": recall, "f1": f1}


def main() -> None:
    cal = sim.calibrate(pd.read_csv(PROCESSED / "daily.csv"), pd.read_csv(PROCESSED / "nhanes_reference.csv"))
    train_days, _ = sim.training_missions(cal, M.TRAIN_MISSIONS, M.TRAIN_SEED)
    test_days, _ = sim.training_missions(cal, M.TEST_MISSIONS, M.TEST_SEED)
    tr, floors = M.sim_features(train_days)
    te, _ = M.sim_features(test_days, floors)
    Xtr, Xte = M.matrix(tr), M.matrix(te)

    real = pd.read_csv(PROCESSED / "features_pmdata.csv")
    real = real[real["target_worse_mood"].notna()].copy()
    real["has_norm"] = real["heart_rate_base"].notna().astype(float)
    Xreal, yreal = M.matrix(real), real["target_worse_mood"].to_numpy()

    rows = []
    for name, make in CANDIDATES.items():
        start = time.time()
        for event in sim.PREDICTED:
            clf = make().fit(Xtr, tr[f"label_{event}_48h"].to_numpy())
            row = {"model": name, "event": event,
                   **scores(te[f"label_{event}_48h"].to_numpy(), clf.predict_proba(Xte)[:, 1])}
            if event == "low_mood":
                row["real_mood_auc"] = roc_auc_score(yreal, clf.predict_proba(Xreal)[:, 1])
            rows.append(row)
        print(f"{name}: {time.time() - start:.0f} s")
    out = pd.DataFrame(rows).round(3)
    print(out.to_string(index=False))
    print("\nMean over events")
    print(out.groupby("model")[["roc_auc", "pr_auc", "precision", "recall", "f1"]].mean().round(3).to_string())


if __name__ == "__main__":
    main()
