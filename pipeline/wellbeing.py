"""Wellbeing forecast on real people: can today's wearable data and check-in predict a worse day tomorrow?

    python -m pipeline.wellbeing          # after python -m pipeline.build

Data: PMData (16 people, morning questionnaire 1-5, readiness 0-10) and LifeSnaps (yes/no feelings).
All PMData scales go "higher = better" (fatigue 5 = fresh, stress 5 = relaxed: they correlate positively
with mood and readiness), so "worse" always means "below".

Targets (PMData): tomorrow's mood / fatigue / readiness is below this person's usual
(median of the last 14 days, today included), the same definition as `target_worse_mood` in features.py.
Target (LifeSnaps): tomorrow the person ticked sad, tense or tired.

Honest check:
- every person is scored by a model that never saw them (5 folds by person, the folds from features.py);
- the reference is "same as today": how far below their usual the person is today (a score, so it has an AUC);
- the 95% interval and the "model minus reference" interval come from resampling people, not days.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .common import PROCESSED
from .features import BASELINE_DAYS, MIN_BASELINE_OBS

N_BOOT = 1000
SEED = 7
FOREST = {"n_estimators": 300, "min_samples_leaf": 20, "max_features": "sqrt", "random_state": 42, "n_jobs": -1}


@dataclass(frozen=True)
class Task:
    name: str
    dataset: str           # "pmdata" or "lifesnaps"
    column: str            # self-report that defines the target
    target: str            # name of the 0/1 target column
    reference: str         # "same as today" score column (higher = more likely worse tomorrow)


TASKS = [
    Task("worse mood", "pmdata", "mood", "y_mood", "ref_mood"),
    Task("more tired (fatigue)", "pmdata", "fatigue", "y_fatigue", "ref_fatigue"),
    Task("less ready (readiness)", "pmdata", "readiness", "y_readiness", "ref_readiness"),
    Task("negative feeling", "lifesnaps", "neg_emotion_today", "target_neg_emotion", "neg_emotion_today"),
]

PM_SIGNALS = ["heart_rate", "sleep_hours_device", "exercise_min", "steps", "sleep_hours", "mood", "fatigue", "stress"]
DEVICE = ("heart_rate", "sleep_hours_device", "exercise_min", "steps", "stress_score", "temp_skin")  # wearable, not self-report
LS_SIGNALS = ["heart_rate", "sleep_hours_device", "exercise_min", "steps", "stress_score", "temp_skin"]


def add_pmdata_targets(f: pd.DataFrame) -> pd.DataFrame:
    """Add y_<col> and ref_<col> for mood, fatigue and readiness. Rows are a full daily calendar per person."""
    f = f.sort_values(["person_id", "date"]).copy()
    for col in ("mood", "fatigue", "readiness"):
        g = f.groupby("person_id")[col]
        usual = g.transform(lambda x: x.rolling(BASELINE_DAYS, min_periods=MIN_BASELINE_OBS).median())
        tomorrow = g.shift(-1)
        f[f"y_{col}"] = (tomorrow < usual).astype(float).where(tomorrow.notna() & usual.notna())
        f[f"ref_{col}"] = usual - f[col]          # how far below usual today: "same as today" as a score
    return f


def feature_columns(dataset: str, f: pd.DataFrame) -> list[str]:
    signals = PM_SIGNALS if dataset == "pmdata" else LS_SIGNALS
    cols = [c for s in signals for c in (f"{s}_z", f"{s}_dev3")]
    if dataset == "pmdata":
        cols += ["sleep_quality", "soreness", "readiness", "ref_mood", "ref_fatigue", "ref_readiness"]
    else:
        cols += ["neg_emotion_today"]
    cols.append("weekend")
    return [c for c in cols if c in f.columns]


def load(dataset: str) -> pd.DataFrame:
    f = pd.read_csv(PROCESSED / f"features_{dataset}.csv")
    if dataset == "pmdata":
        f = add_pmdata_targets(f)
    f["weekend"] = (f["dow"] >= 5).astype(float)
    return f


def check_in_only(cols: list[str]) -> list[str]:
    """Drop wearable inputs: answers "does the wristband add anything to the questionnaire?"."""
    return [c for c in cols if not c.startswith(DEVICE)]


def models() -> dict:
    return {
        "logistic regression": make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(),
                                             LogisticRegression(C=0.1, max_iter=2000)),
        "random forest": make_pipeline(SimpleImputer(strategy="median", add_indicator=True),
                                       RandomForestClassifier(**FOREST)),
    }


def out_of_person_scores(f: pd.DataFrame, cols: list[str], target: str) -> dict[str, np.ndarray]:
    """Each row scored by a model trained only on the other folds' people."""
    out = {name: np.full(len(f), np.nan) for name in models()}
    x, y = f[cols].to_numpy(float), f[target].to_numpy(int)
    for fold in sorted(f["fold"].unique()):
        test = (f["fold"] == fold).to_numpy()
        for name, m in models().items():
            m.fit(x[~test], y[~test])
            out[name][test] = m.predict_proba(x[test])[:, 1]
    return out


def person_bootstrap(people: np.ndarray, y: np.ndarray, a: np.ndarray, b: np.ndarray | None = None,
                     n: int = N_BOOT, seed: int = SEED) -> tuple[float, float]:
    """95% interval of AUC(a), or of AUC(a) - AUC(b), resampling whole people."""
    rng = np.random.default_rng(seed)
    ids = np.unique(people)
    rows = {p: np.flatnonzero(people == p) for p in ids}
    stats = []
    for _ in range(n):
        idx = np.concatenate([rows[p] for p in rng.choice(ids, len(ids))])
        if len(np.unique(y[idx])) < 2:
            continue
        s = roc_auc_score(y[idx], a[idx])
        if b is not None:
            s -= roc_auc_score(y[idx], b[idx])
        stats.append(s)
    lo, hi = np.percentile(stats, [2.5, 97.5])
    return round(float(lo), 3), round(float(hi), 3)


def evaluate(task: Task, f: pd.DataFrame) -> pd.DataFrame:
    d = f[f[task.target].notna() & f[task.reference].notna()].reset_index(drop=True)
    cols = feature_columns(task.dataset, d)
    y, people = d[task.target].to_numpy(int), d["person_id"].to_numpy()
    ref = d[task.reference].to_numpy(float)
    scores = {"same as today (reference)": ref} | out_of_person_scores(d, cols, task.target)
    no_device = out_of_person_scores(d, check_in_only(cols), task.target)
    scores["random forest, check-in only"] = no_device["random forest"]
    rows = []
    for name, s in scores.items():
        auc = round(float(roc_auc_score(y, s)), 3)
        lo, hi = person_bootstrap(people, y, s)
        row = {"task": task.name, "dataset": task.dataset, "method": name, "auc": auc, "auc_95": f"{lo}-{hi}"}
        if name != "same as today (reference)":
            dlo, dhi = person_bootstrap(people, y, s, ref)
            row["vs_reference_95"] = f"{dlo:+.3f}..{dhi:+.3f}"
        rows.append(row)
    out = pd.DataFrame(rows)
    out["days"], out["people"], out["positive_rate"] = len(d), d["person_id"].nunique(), round(float(y.mean()), 3)
    return out


def top_signals(task: Task, f: pd.DataFrame, top: int = 5) -> pd.DataFrame:
    """Which inputs move the forest's answer most: mean |SHAP| of a forest trained on everyone."""
    import shap

    d = f[f[task.target].notna() & f[task.reference].notna()].reset_index(drop=True)
    cols = feature_columns(task.dataset, d)
    imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    x = imputer.fit_transform(d[cols].to_numpy(float))
    forest = RandomForestClassifier(**FOREST).fit(x, d[task.target].to_numpy(int))
    values = shap.TreeExplainer(forest).shap_values(x, check_additivity=False)
    values = values[1] if isinstance(values, list) else values[..., 1]   # contribution to "worse tomorrow"
    impact = pd.Series(np.abs(values).mean(axis=0), index=cols).sort_values(ascending=False).head(top)
    return pd.DataFrame({"task": task.name, "signal": impact.index, "mean_abs_shap_pp": (impact * 100).round(2).values})


def run() -> tuple[pd.DataFrame, pd.DataFrame]:
    data = {ds: load(ds) for ds in ("pmdata", "lifesnaps")}
    scores = pd.concat([evaluate(t, data[t.dataset]) for t in TASKS], ignore_index=True)
    signals = pd.concat([top_signals(t, data[t.dataset]) for t in TASKS], ignore_index=True)
    return scores, signals


def main() -> None:
    scores, signals = run()
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(scores.to_string(index=False))
        print()
        print(signals.to_string(index=False))


if __name__ == "__main__":
    main()
