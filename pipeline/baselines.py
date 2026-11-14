"""Simple reference scores a real model has to beat. Run after `python -m pipeline.build`:

    python -m pipeline.baselines

"Always the majority class": predicts whichever answer was more common in the training people.
"Same as today": predicts that tomorrow will be like today.
Metrics: balanced accuracy (mean of the hit rate on each class, 0.5 = guessing) and F1 of the positive class
("tomorrow is worse"). Plain accuracy is not used: classes are uneven.
"""
import numpy as np
import pandas as pd

from .common import PROCESSED

TASKS = {
    "pmdata": ("features_pmdata.csv", "target_worse_mood", "worse_mood_today"),
    "lifesnaps": ("features_lifesnaps.csv", "target_neg_emotion", "neg_emotion_today"),
}


def scores(y: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    y, pred = y.astype(int), pred.astype(int)
    tp = int(((y == 1) & (pred == 1)).sum())
    tn = int(((y == 0) & (pred == 0)).sum())
    fp = int(((y == 0) & (pred == 1)).sum())
    fn = int(((y == 1) & (pred == 0)).sum())
    tpr = tp / (tp + fn) if tp + fn else np.nan
    tnr = tn / (tn + fp) if tn + fp else np.nan
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else np.nan
    return {"balanced_acc": round((tpr + tnr) / 2, 3), "f1": round(f1, 3)}


def evaluate(name: str, file: str, target: str, today: str) -> pd.DataFrame:
    f = pd.read_csv(PROCESSED / file)
    f = f[f[target].notna()]
    majority = int(f.loc[~f["is_test"], target].mean() >= 0.5)
    rows = []
    for label, part in (("test people", f[f["is_test"]]), ("all people", f)):
        for method, pred in (("always majority class", pd.Series(majority, index=part.index)),
                             ("same as today", part[today])):
            keep = pred.notna()
            y = part.loc[keep, target].to_numpy()
            rows.append({"dataset": name, "rows": label, "method": method, "n": int(keep.sum()),
                         "people": part.loc[keep, "person_id"].nunique(),
                         "positive_rate": round(float(y.mean()), 3),
                         **scores(y, pred[keep].to_numpy())})
    return pd.DataFrame(rows)


def main() -> None:
    table = pd.concat([evaluate(name, *spec) for name, spec in TASKS.items()], ignore_index=True)
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
