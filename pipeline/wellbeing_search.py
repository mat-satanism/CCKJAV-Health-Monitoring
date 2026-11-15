"""Search for a better wellbeing forecast, scored honestly (see docs/wellbeing-model.md).

    python -m pipeline.wellbeing_search mood           # every variant, within-person AUC on 3 splits of people
    python -m pipeline.wellbeing_search mood nested    # "try all, keep the best" with the choice made on training people only

Variants: composite features (wellbeing index, sleep debt, training load ACWR, interactions, days since the last bad
day), a regression target (tomorrow minus usual) and personal centring of the score. Main score: within-person AUC.
"""
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline

warnings.filterwarnings("ignore")
from . import bayes_features
from . import wellbeing as w
from .features import BASELINE_DAYS, MIN_BASELINE_OBS, assign_folds

TASK = {"mood": "worse mood", "fatigue": "more tired (fatigue)", "readiness": "less ready (readiness)"}
SEEDS = (42, 1, 2)


def past_norm(g, col):
    return g[col].transform(lambda x: x.shift(1).rolling(BASELINE_DAYS, min_periods=MIN_BASELINE_OBS).median())


def _days_since(x: pd.Series) -> pd.Series:
    out, n = [], np.nan
    for v in x:
        n = 0 if v == 1 else (n + 1 if not np.isnan(n) else np.nan)
        out.append(n)
    return pd.Series(out, index=x.index)


def composites(f: pd.DataFrame, target: str) -> pd.DataFrame:
    f = f.sort_values(["person_id", "date"]).copy()
    g = f.groupby("person_id")
    # wellbeing index: mean z of the morning answers (higher = better)
    zc = [c for c in ("mood_z", "fatigue_z", "stress_z") if c in f]
    f["sq_z"] = (f["sleep_quality"] - past_norm(g, "sleep_quality"))
    f["wb_index"] = f[zc + ["sq_z"]].mean(axis=1)
    f["wb_index_3"] = f.groupby("person_id")["wb_index"].transform(lambda x: x.rolling(3, min_periods=2).mean())
    f["wb_index_d1"] = f["wb_index"] - f.groupby("person_id")["wb_index"].shift(1)
    # sleep debt over 3 days vs own norm (self-report, then device)
    for s in ("sleep_hours", "sleep_hours_device"):
        deficit = (past_norm(g, s) - f[s]).clip(lower=0)
        f[f"{s}_debt3"] = deficit.groupby(f["person_id"]).transform(lambda x: x.rolling(3, min_periods=2).sum())
    # training load: acute (7 d) over chronic (28 d)
    ex = g["exercise_min"]
    f["acwr"] = ex.transform(lambda x: x.rolling(7, min_periods=4).mean()) / \
        ex.transform(lambda x: x.rolling(28, min_periods=14).mean()).replace(0, np.nan)
    # interactions
    f["hr_up_x_short_sleep"] = f["heart_rate_z"].clip(lower=0) * (-f["sleep_hours_device_z"]).clip(lower=0)
    f["stress_x_fatigue"] = (-f["stress_z"]).clip(lower=0) * (-f["fatigue_z"]).clip(lower=0)
    # days since this person's last below-usual day of the target (known on the day it happens)
    below = (f[target] < g[target].transform(
        lambda x: x.rolling(BASELINE_DAYS, min_periods=MIN_BASELINE_OBS).median())).astype(float)
    f["days_since_bad"] = below.groupby(f["person_id"]).transform(_days_since)
    # regression target: tomorrow minus usual (same usual as the class target)
    usual = g[target].transform(lambda x: x.rolling(BASELINE_DAYS, min_periods=MIN_BASELINE_OBS).median())
    f[f"r_{target}"] = g[target].shift(-1) - usual
    return f


COMPOSITE = {
    "wb": ["wb_index", "wb_index_3", "wb_index_d1"],
    "debt": ["sleep_hours_debt3", "sleep_hours_device_debt3"],
    "acwr": ["acwr"],
    "inter": ["hr_up_x_short_sleep", "stress_x_fatigue"],
    "since": ["days_since_bad"],
}


def fit_scores(d, cols, target, fold_col, kind="clf", centre=False):
    s = np.full(len(d), np.nan)
    signals = sorted({c.rsplit("_bz", 1)[0] for c in cols if "_bz" in c})
    refit = bool(bayes_features.fitted_signals(signals))
    x = d[cols].to_numpy(float)
    for k in sorted(d[fold_col].unique()):
        t = (d[fold_col] == k).to_numpy()
        if refit:   # learned norm priors from the training people of this fold only (docs/wellbeing-model.md)
            x = bayes_features.refit_for_fold(d, signals, d[fold_col] != k)[cols].to_numpy(float)
        if kind == "clf":
            m = make_pipeline(SimpleImputer(strategy="median", add_indicator=True), RandomForestClassifier(**w.FOREST))
            m.fit(x[~t], d[target].to_numpy(int)[~t])
            s[t] = m.predict_proba(x[t])[:, 1]
        else:   # regression on tomorrow minus usual; low = worse, so score = minus prediction
            rt = d[f"r_{target.removeprefix('y_')}"].to_numpy(float)
            m = make_pipeline(SimpleImputer(strategy="median", add_indicator=True),
                              RandomForestRegressor(**{**w.FOREST, "max_features": 0.5}))
            m.fit(x[~t], rt[~t])
            s[t] = -m.predict(x[t])
    if centre:   # subtract this person's running mean of past scores: only the change of the day is left
        ser = pd.Series(s).groupby(d["person_id"].to_numpy())
        prev = ser.transform(lambda v: v.shift(1).expanding(min_periods=5).mean())
        s = s - prev.fillna(pd.Series(s).groupby(d["person_id"].to_numpy()).transform("mean")).to_numpy()
    return s


def within(d, y, s):
    return float(np.mean(list(w.within_person_auc(d["person_id"].to_numpy(), y, s).values())))


def prepare(target):
    t = next(x for x in w.TASKS if x.name == TASK[target])
    f = composites(w.load("pmdata"), target)
    d = f[f[t.target].notna() & f[t.reference].notna()].reset_index(drop=True)
    for seed in SEEDS:
        d[f"fold_{seed}"] = d["person_id"].map(assign_folds(d["person_id"].unique(), seed=seed))
    return t, d


def variants(d, target):
    base_all = w.feature_columns("pmdata", d)
    ci = w.check_in_only(base_all)
    hist = [c for c in d.columns if c.endswith(w.HISTORY)]
    start = ci + hist if target == "mood" else base_all      # current best per target
    v = {"current": (start, "clf", False)}
    for k, cols in COMPOSITE.items():
        v[f"+{k}"] = (start + cols, "clf", False)
    allc = [c for cols in COMPOSITE.values() for c in cols]
    v["+all composites"] = (start + allc, "clf", False)
    v["regression"] = (start, "reg", False)
    v["centred"] = (start, "clf", True)
    v["all + regression"] = (start + allc, "reg", False)
    return v


def explore(target):
    t, d = prepare(target)
    y = d[t.target].to_numpy(int)
    rows = [{"variant": "same as today", "within": round(within(d, y, d[t.reference].to_numpy(float)), 3)}]
    for name, (cols, kind, centre) in variants(d, target).items():
        per = [within(d, y, fit_scores(d, cols, t.target, f"fold_{s}", kind, centre)) for s in SEEDS]
        rows.append({"variant": name, "within": round(np.mean(per), 3), "min": round(min(per), 3), "max": round(max(per), 3)})
        print(rows[-1], flush=True)
    return pd.DataFrame(rows)


def nested(target, seed=42):
    """Honest estimate of 'try all variants, keep the best': selection uses only training people."""
    t, d = prepare(target)
    y = d[t.target].to_numpy(int)
    vs = variants(d, target)
    folds = d["person_id"].map(assign_folds(d["person_id"].unique(), seed=seed))
    final = np.full(len(d), np.nan)
    picks = []
    for k in sorted(folds.unique()):
        outer = (folds == k).to_numpy()
        inner = d[~outer].reset_index(drop=True)
        inner["fold_in"] = inner["person_id"].map(assign_folds(inner["person_id"].unique(), seed=seed, n_folds=4))
        yi = inner[t.target].to_numpy(int)
        best = max(vs, key=lambda n: within(inner, yi, fit_scores(inner, vs[n][0], t.target, "fold_in", vs[n][1], vs[n][2])))
        picks.append(best)
        d["_f"] = np.where(outer, 1, 0)
        cols, kind, centre = vs[best]
        final[outer] = fit_scores(d, cols, t.target, "_f", kind, centre)[outer]
    ref = d[t.reference].to_numpy(float)
    wa, wr = w.within_person_auc(d["person_id"].to_numpy(), y, final), w.within_person_auc(d["person_id"].to_numpy(), y, ref)
    print(target, "picks:", picks)
    print(target, "nested within AUC:", round(np.mean(list(wa.values())), 3), "reference:", round(np.mean(list(wr.values())), 3),
          "diff 95%:", w.within_bootstrap(wa, wr))


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "mood"
    if len(sys.argv) > 2 and sys.argv[2] == "nested":
        nested(target)
    else:
        print(explore(target).to_string(index=False))
