"""Risk model: for each astronaut and day, the chance that each event starts in the next 48 hours.

    python -m pipeline.model

Trained on simulated missions (pipeline/simulation.py), tested on missions with other seeds and, for the one
target real data has, on real PMData people. One logistic regression per event: small, works offline, and
every prediction can be explained as "which signs pushed the risk up". The fitted numbers are saved as plain
JSON (models/risk_model.json), so the app can use them without scikit-learn.
"""
import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score

from . import features as F
from . import simulation as sim
from .common import PROCESSED, ROOT

MODEL_PATH = ROOT / "models" / "risk_model.json"
TRAIN_MISSIONS, TRAIN_SEED = 400, 7
TEST_MISSIONS, TEST_SEED = 100, 1234
ALERT_SHARE = 0.05          # "top 5% riskiest astronaut-days raise an alert" for the recall/precision numbers
C = 0.5                     # regularisation of the logistic regression
MIN_SIGN = 0.25             # a sign is shown only if it adds at least this much to the log-odds
KEY = ["mission_id", "astronaut_id"]
CREW_SIGNALS = ["sleep_hours", "mood", "heart_rate"]

LABELS = {
    "heart_rate": ("Resting pulse", "bpm"), "bp_sys": ("Systolic pressure", "mmHg"),
    "bp_dia": ("Diastolic pressure", "mmHg"), "glucose": ("Glucose", "mg/dL"), "temp": ("Temperature", "°C"),
    "sleep_hours": ("Sleep", "h"), "mood": ("Mood", "points"), "exercise_min": ("Exercise", "min"),
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
    d["has_norm"] = d["heart_rate_dev"].notna().astype(float)
    return d, floors


def feature_columns() -> list[str]:
    cols = [f"{ind}_{kind}" for ind in sim.INDICATORS for kind in ("z", "dev3")]
    return cols + [f"crew_{ind}_dev" for ind in CREW_SIGNALS] + ["has_norm"]


def matrix(d: pd.DataFrame) -> np.ndarray:
    return d.reindex(columns=feature_columns()).fillna(0.0).to_numpy(dtype=float)  # no norm yet = no deviation


def train(train_days: pd.DataFrame) -> dict:
    d, floors = sim_features(train_days)
    X = matrix(d)
    mean, scale = X.mean(axis=0), X.std(axis=0)
    scale[scale == 0] = 1.0
    Xs = (X - mean) / scale
    events = {}
    for event in sim.PREDICTED:
        y = d[f"label_{event}_48h"].to_numpy()
        lr = LogisticRegression(C=C, max_iter=2000).fit(Xs, y)
        events[event] = {"coef": lr.coef_[0].round(6).tolist(), "intercept": float(lr.intercept_[0])}
    return {"features": feature_columns(), "mean": mean.round(6).tolist(), "scale": scale.round(6).tolist(),
            "floors": floors, "events": events,
            "trained_on": f"{TRAIN_MISSIONS} simulated missions, seed {TRAIN_SEED}",
            "note": "Synthetic training data calibrated on PMData and NHANES. Not a medical device."}


def risk(model: dict, d: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    """Probabilities per event and per-feature contributions (coefficient x standardised value)."""
    Xs = (matrix(d) - np.array(model["mean"])) / np.array(model["scale"])
    probs, contrib = {}, {}
    for event, p in model["events"].items():
        c = Xs * np.array(p["coef"])
        contrib[event] = c
        probs[f"risk_{event}"] = 1 / (1 + np.exp(-(c.sum(axis=1) + p["intercept"])))
    return pd.DataFrame(probs, index=d.index), contrib


def describe(feature: str, row: pd.Series) -> str:
    if feature.startswith("crew_"):
        ind = feature[len("crew_"):-len("_dev")]
        label, unit = LABELS[ind]
        return f"Whole crew: {label.lower()} {row[feature]:+.1f} {unit} vs usual"
    ind, kind = feature.rsplit("_", 1)
    label, unit = LABELS[ind]
    if kind == "dev3":
        return f"{label} {row[f'{ind}_dev3']:+.1f} {unit} vs usual, last 3 days"
    return f"{label} {row[f'{ind}_dev']:+.1f} {unit} vs usual today"


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


def evaluate(model: dict, test_days: pd.DataFrame) -> pd.DataFrame:
    d, _ = sim_features(test_days, model["floors"])
    probs, _ = risk(model, d)
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


def real_check(model: dict) -> pd.DataFrame:
    """Score the sim-trained mood-related models on real PMData people against 'tomorrow's mood is worse than usual'."""
    f = pd.read_csv(PROCESSED / "features_pmdata.csv")
    f = f[f["target_worse_mood"].notna()].copy()
    f["has_norm"] = f["heart_rate_base"].notna().astype(float)
    probs, _ = risk(model, f)          # missing indicators (pressure, glucose, temperature, crew) count as 0
    y = f["target_worse_mood"].to_numpy()
    rows = [{"score": f"risk_{e}", "auc": round(roc_auc_score(y, probs[f"risk_{e}"]), 3)}
            for e in ("low_mood", "sleep_disruption")]
    today = f["worse_mood_today"].notna()
    rows.append({"score": "same as today (reference)",
                 "auc": round(roc_auc_score(y[today], f.loc[today, "worse_mood_today"]), 3)})
    out = pd.DataFrame(rows)
    out["rows"], out["people"] = len(f), f["person_id"].nunique()
    return out


def predict_demo(model: dict, demo_days: pd.DataFrame) -> pd.DataFrame:
    d, _ = sim_features(demo_days, model["floors"])
    probs, contrib = risk(model, d)
    out = pd.concat([d[["astronaut_id", "mission_day"]], probs.round(3), explain(model, d, contrib)], axis=1)
    return out.sort_values(["mission_day", "astronaut_id"]).reset_index(drop=True)


def main() -> None:
    cal = sim.calibrate(pd.read_csv(PROCESSED / "daily.csv"), pd.read_csv(PROCESSED / "nhanes_reference.csv"))
    train_days, _ = sim.training_missions(cal, TRAIN_MISSIONS, TRAIN_SEED)
    test_days, _ = sim.training_missions(cal, TEST_MISSIONS, TEST_SEED)
    model = train(train_days)
    MODEL_PATH.parent.mkdir(exist_ok=True)
    MODEL_PATH.write_text(json.dumps(model, indent=1))
    print(f"model -> {MODEL_PATH.relative_to(ROOT)}")
    print("\nTest: 100 new simulated missions (seed never used in training)")
    print(evaluate(model, test_days).to_string(index=False))
    print("\nReal people (PMData), target: tomorrow's mood worse than usual")
    print(real_check(model).to_string(index=False))
    _, demo_days, _ = sim.demo_mission(cal)
    pred = predict_demo(model, demo_days)
    pred.to_csv(PROCESSED / "sim" / "predictions.csv", index=False)
    print(f"\nsim/predictions.csv -> {len(pred)} rows")


if __name__ == "__main__":
    main()
