"""Risk model: for each astronaut and day, the chance that each event starts in the next 48 hours.

    python -m pipeline.model

Trained on simulated missions (pipeline/simulation.py), tested on missions with other seeds and, for the one
target real data has, on real PMData people. One random forest per event, chosen over logistic regression and
LightGBM in pipeline/compare_models.py (see docs/model-comparison.md): as good as LightGBM on new simulated
missions and the only one that holds up on real people. Each prediction is explained with SHAP: how much each
sign added to or took away from the risk. The app reads the precomputed demo predictions (sim/predictions.csv)
and the settings in models/risk_model.json (floors, usual risk per event), so it does not need scikit-learn.
"""
import json

import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

from . import bayes_features as B
from . import features as F
from . import simulation as sim
from .common import PROCESSED, ROOT

MODEL_PATH = ROOT / "models" / "risk_model.json"
TRAIN_MISSIONS, TRAIN_SEED = 400, 7
TEST_MISSIONS, TEST_SEED = 100, 1234
ALERT_SHARE = 0.05          # "top 5% riskiest astronaut-days raise an alert" for the recall/precision numbers
FOREST = {"n_estimators": 300, "min_samples_leaf": 20, "random_state": 42}   # leaves of 20+ days: no memorising
C = 0.5                     # regularisation of the logistic regression (compare_models only)
MIN_SIGN = 0.01             # a sign is shown only if SHAP says it adds at least 1 percentage point of risk
KEY = ["mission_id", "astronaut_id"]
CREW_SIGNALS = ["sleep_hours", "mood", "heart_rate"]
NORM = "bayes"   # inputs measured against the app's Bayesian personal norm; "median" = the old 14-day median

LABELS = {
    "heart_rate": ("Resting pulse", "bpm"), "bp_sys": ("Systolic pressure", "mmHg"),
    "bp_dia": ("Diastolic pressure", "mmHg"), "glucose": ("Glucose", "mg/dL"), "temp": ("Temperature", "°C"),
    "sleep_hours": ("Sleep", "h"), "mood": ("Mood", "points"), "exercise_min": ("Exercise", "min"),
    "hrv_ms": ("Heart rate variability", "ms"), "reaction_ms": ("Reaction time", "ms"),
}


def _rolling(series: pd.Series, groups: list[pd.Series], window: int, min_periods: int, how: str) -> pd.Series:
    r = series.groupby(groups, sort=False).rolling(window, min_periods=min_periods)
    out = getattr(r, how)()
    return out.reset_index(level=list(range(len(groups))), drop=True).reindex(series.index)


def sim_features(days: pd.DataFrame, floors: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """Same norm rules as pipeline/features.py: norm = median of the previous 14 days, deviations, z-scores.

    floors: minimum spread per indicator for z-scores. Computed here when None (training data only).
    """
    d = days.sort_values(KEY + ["mission_day"]).reset_index(drop=True)
    groups = [d["mission_id"], d["astronaut_id"]]
    for ind in sim.INDICATORS:
        x = d[ind].astype(float)
        past = x.groupby(groups, sort=False).shift(1)              # days before today only
        base = _rolling(past, groups, F.BASELINE_DAYS, F.MIN_BASELINE_OBS, "median")
        d[f"{ind}_dev"] = x - base
        d[f"{ind}_dev3"] = _rolling(d[f"{ind}_dev"], groups, F.RECENT_DAYS, 2, "mean")
        d[f"{ind}_spread"] = _rolling(past, groups, F.BASELINE_DAYS, F.MIN_BASELINE_OBS, "std")
    if floors is None:
        floors = {}
        for ind in sim.INDICATORS:
            s = d[f"{ind}_spread"]
            s = s[s > 0].dropna()
            floors[ind] = float(np.percentile(s, F.MIN_SPREAD_PERCENTILE)) if len(s) else 1.0
    for ind in sim.INDICATORS:
        d[f"{ind}_z"] = d[f"{ind}_dev"] / d[f"{ind}_spread"].clip(lower=floors[ind])
    # The whole crew at once: the sign of a station problem rather than a personal one.
    by_day = d.groupby(["mission_id", "mission_day"])
    for ind in CREW_SIGNALS:
        d[f"crew_{ind}_dev"] = by_day[f"{ind}_dev"].transform("mean")
    add_bayes_sim(d, groups)
    d["has_norm"] = d["heart_rate_dev"].notna().astype(float)
    return d, floors


def add_bayes_sim(d: pd.DataFrame, groups: list[pd.Series]) -> None:
    """Distance from the app's Bayesian norm (backend/app/status.py): <ind>_bdev in units, <ind>_bz in the
    person's predictive scale, 3-day means, and the crew mean. Only days before today enter the norm."""
    for ind in sim.INDICATORS:
        prior = B.APP_PRIORS[ind]
        bdev, bz = np.full(len(d), np.nan), np.full(len(d), np.nan)
        for idx in d.groupby(groups, sort=False).indices.values():
            past: list[float] = []
            for i in idx:
                x = float(d.at[i, ind])
                norm = B.bayes_norm(past[-B.status.NORM_DAYS:], prior)
                if norm is not None:
                    bdev[i], bz[i] = x - norm[0], (x - norm[0]) / norm[1]
                past.append(x)
        d[f"{ind}_bdev"], d[f"{ind}_bz"] = bdev, bz
        d[f"{ind}_bdev3"] = _rolling(d[f"{ind}_bdev"], groups, F.RECENT_DAYS, 2, "mean")
        d[f"{ind}_bz3"] = _rolling(d[f"{ind}_bz"], groups, F.RECENT_DAYS, 2, "mean")
    by_day = d.groupby(["mission_id", "mission_day"])
    for ind in CREW_SIGNALS:
        d[f"crew_{ind}_bdev"] = by_day[f"{ind}_bdev"].transform("mean")


def feature_columns(norm: str | None = None) -> list[str]:
    if (norm or NORM) == "median":
        cols = [f"{ind}_{kind}" for ind in sim.INDICATORS for kind in ("z", "dev3")]
        return cols + [f"crew_{ind}_dev" for ind in CREW_SIGNALS] + ["has_norm"]
    cols = [f"{ind}_{kind}" for ind in sim.INDICATORS for kind in ("bz", "bz3")]
    return cols + [f"crew_{ind}_bdev" for ind in CREW_SIGNALS] + ["has_norm"]


def matrix(d: pd.DataFrame) -> np.ndarray:
    return d.reindex(columns=feature_columns()).fillna(0.0).to_numpy(dtype=float)  # no norm yet = no deviation


def train(train_days: pd.DataFrame) -> tuple[dict, dict[str, RandomForestClassifier]]:
    """Returns (settings saved as JSON, one fitted forest per event)."""
    d, floors = sim_features(train_days)
    X = matrix(d)
    forests, events = {}, {}
    for event in sim.PREDICTED:
        y = d[f"label_{event}_48h"].to_numpy()
        forests[event] = RandomForestClassifier(**FOREST, n_jobs=-1).fit(X, y)
        events[event] = {"base_rate": round(float(y.mean()), 4)}   # share of days with this label: "usual" risk
    settings = {"model": "random_forest", "params": FOREST, "explanations": "SHAP (TreeExplainer)", "norm": NORM,
                "features": feature_columns(), "floors": floors, "events": events,
                "trained_on": f"{TRAIN_MISSIONS} simulated missions, seed {TRAIN_SEED}",
                "note": "Synthetic training data calibrated on PMData and NHANES. Not a medical device."}
    return settings, forests


def risk(forests: dict, d: pd.DataFrame, explain_signs: bool = True) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    """Probabilities per event and, if asked, SHAP contributions per feature (in probability units)."""
    X = matrix(d)
    probs, contrib = {}, {}
    for event, forest in forests.items():
        probs[f"risk_{event}"] = forest.predict_proba(X)[:, 1]
        if explain_signs:
            contrib[event] = shap.TreeExplainer(forest).shap_values(X)[:, :, 1]
    return pd.DataFrame(probs, index=d.index), contrib


def describe(feature: str, row: pd.Series) -> str:
    if feature.startswith("crew_"):
        ind = feature[len("crew_"):].rsplit("_", 1)[0]
        label, unit = LABELS[ind]
        return f"Whole crew: {label.lower()} {row[feature]:+.1f} {unit} vs usual"
    ind, kind = feature.rsplit("_", 1)
    label, unit = LABELS[ind]
    dev = "bdev" if kind.startswith("bz") else "dev"     # shown in units, whichever norm the model reads
    if kind in ("dev3", "bz3"):
        return f"{label} {row[f'{ind}_{dev}3']:+.1f} {unit} vs usual, last 3 days"
    return f"{label} {row[f'{ind}_{dev}']:+.1f} {unit} vs usual today"


def explain(model: dict, d: pd.DataFrame, contrib: dict[str, np.ndarray], top: int = 3) -> pd.DataFrame:
    names = model["features"]
    out = {}
    for event, c in contrib.items():
        texts = []
        for i in range(len(d)):
            order = np.argsort(-c[i])
            picked = [names[j] for j in order[:top] if c[i, j] >= MIN_SIGN and names[j] != "has_norm"]
            row = d.iloc[i]
            texts.append("; ".join(describe(f, row) for f in picked if pd.notna(row.get(f))))
        out[f"signs_{event}"] = texts
    return pd.DataFrame(out, index=d.index)


def evaluate(settings: dict, forests: dict, test_days: pd.DataFrame) -> pd.DataFrame:
    d, _ = sim_features(test_days, settings["floors"])
    probs, _ = risk(forests, d, explain_signs=False)
    simple = d[[f"{ind}_z" for ind in sim.INDICATORS]].abs().max(axis=1).fillna(0)   # rule: biggest |z| today
    rows = []
    for event in sim.PREDICTED:
        y = d[f"label_{event}_48h"].to_numpy()
        p = probs[f"risk_{event}"].to_numpy()
        alert = p >= np.quantile(p, 1 - ALERT_SHARE)
        rows.append({"event": event, "share_of_days": round(float(y.mean()), 3),
                     "auc_model": round(roc_auc_score(y, p), 3), "auc_rule_max_z": round(roc_auc_score(y, simple), 3),
                     "pr_auc_model": round(average_precision_score(y, p), 3),
                     "caught_top5pct": round(float(alert[y == 1].mean()), 3),
                     "precision_top5pct": round(float(y[alert].mean()), 3)})
    return pd.DataFrame(rows)


def real_people() -> pd.DataFrame:
    """PMData days with the risk model's inputs (both norms) and the target 'tomorrow's mood worse than usual'."""
    f = pd.read_csv(PROCESSED / "features_pmdata.csv")
    f = B.add_bayes(f, ["heart_rate", "sleep_hours", "mood", "exercise_min"])   # the app's priors for these
    f = f[f["target_worse_mood"].notna()].copy()
    f["has_norm"] = f["heart_rate_base"].notna().astype(float)
    return f


def real_check(forests: dict) -> pd.DataFrame:
    """Score the sim-trained mood-related models on real PMData people against 'tomorrow's mood is worse than usual'."""
    f = real_people()
    probs, _ = risk(forests, f, explain_signs=False)   # missing indicators (pressure, glucose, temperature, crew) count as 0
    y = f["target_worse_mood"].to_numpy()
    rows = [{"score": f"risk_{e}", "auc": round(roc_auc_score(y, probs[f"risk_{e}"]), 3)}
            for e in ("low_mood", "sleep_disruption")]
    today = f["worse_mood_today"].notna()
    rows.append({"score": "same as today (reference)",
                 "auc": round(roc_auc_score(y[today], f.loc[today, "worse_mood_today"]), 3)})
    out = pd.DataFrame(rows)
    out["rows"], out["people"] = len(f), f["person_id"].nunique()
    return out


def predict_demo(settings: dict, forests: dict, demo_days: pd.DataFrame) -> pd.DataFrame:
    d, _ = sim_features(demo_days, settings["floors"])
    probs, contrib = risk(forests, d)
    out = pd.concat([d[["astronaut_id", "mission_day"]], probs.round(3), explain(settings, d, contrib)], axis=1)
    return out.sort_values(["mission_day", "astronaut_id"]).reset_index(drop=True)


def main() -> None:
    cal = sim.calibrate(pd.read_csv(PROCESSED / "daily.csv"), pd.read_csv(PROCESSED / "nhanes_reference.csv"))
    train_days, _ = sim.training_missions(cal, TRAIN_MISSIONS, TRAIN_SEED)
    test_days, _ = sim.training_missions(cal, TEST_MISSIONS, TEST_SEED)
    settings, forests = train(train_days)
    MODEL_PATH.parent.mkdir(exist_ok=True)
    MODEL_PATH.write_text(json.dumps(settings, indent=1))
    print(f"model -> {MODEL_PATH.relative_to(ROOT)}")
    print("\nTest: 100 new simulated missions (seed never used in training)")
    print(evaluate(settings, forests, test_days).to_string(index=False))
    print("\nReal people (PMData), target: tomorrow's mood worse than usual")
    print(real_check(forests).to_string(index=False))
    _, demo_days, _ = sim.demo_mission(cal)
    pred = predict_demo(settings, forests, demo_days)
    pred.to_csv(PROCESSED / "sim" / "predictions.csv", index=False)
    print(f"\nsim/predictions.csv -> {len(pred)} rows")


if __name__ == "__main__":
    main()
