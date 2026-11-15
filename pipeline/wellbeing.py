"""Wellbeing forecast on real people: can today's wearable data and check-in predict a worse day tomorrow?

    python -m pipeline.wellbeing          # after python -m pipeline.build
    python -m pipeline.wellbeing export   # forecasts for the app's real-data demo -> data/processed/wellbeing_demo.json

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
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import bayes_features
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
CHECK_IN = ["mood", "fatigue", "stress", "readiness", "sleep_quality", "soreness", "sleep_hours"]
NORM = "bayes"   # inputs against the app's Bayesian personal norm (docs/personal-norm.md); "median" = old rule
# yesterday's answer, change since yesterday, worst of the last 3 days, days since the last below-usual day
HISTORY = ("_lag1", "_d1", "_min3", "_since_low")


def add_pmdata_targets(f: pd.DataFrame, cols: tuple[str, ...] = ("mood", "fatigue", "readiness")) -> pd.DataFrame:
    """Add y_<col> and ref_<col> (mood, fatigue, readiness by default). Rows are a full daily calendar per person."""
    f = f.sort_values(["person_id", "date"]).copy()
    for col in cols:
        g = f.groupby("person_id")[col]
        usual = g.transform(lambda x: x.rolling(BASELINE_DAYS, min_periods=MIN_BASELINE_OBS).median())
        tomorrow = g.shift(-1)
        f[f"y_{col}"] = (tomorrow < usual).astype(float).where(tomorrow.notna() & usual.notna())
        f[f"ref_{col}"] = usual - f[col]          # how far below usual today: "same as today" as a score
        # Days since this person's last below-usual answer, counted up to today (today's answer is known today).
        # Chosen by the nested check (docs/wellbeing-model.md): it was the most picked addition for mood and fatigue.
        low = (f[col] < usual).astype(float)
        f[f"{col}_since_low"] = low.groupby(f["person_id"]).transform(_days_since)
    return f


def _days_since(x: pd.Series) -> pd.Series:
    out, n = [], np.nan
    for v in x:
        n = 0.0 if v == 1 else (n + 1 if not np.isnan(n) else np.nan)
        out.append(n)
    return pd.Series(out, index=x.index)


def add_history(f: pd.DataFrame) -> pd.DataFrame:
    """Last days of the check-in. Only days up to today; rows are a full daily calendar per person.

    Tried and left out (docs/wellbeing-model.md): how jumpy a person usually is and their share of bad days.
    They raise the pooled AUC by telling people apart, not by spotting the bad day of one person.
    """
    f = f.sort_values(["person_id", "date"]).copy()
    g = f.groupby("person_id")
    for c in CHECK_IN:
        f[f"{c}_lag1"] = g[c].shift(1)
        f[f"{c}_d1"] = f[c] - f[f"{c}_lag1"]
        f[f"{c}_min3"] = g[c].transform(lambda x: x.rolling(3, min_periods=2).min())
    return f


def feature_columns(dataset: str, f: pd.DataFrame, norm: str | None = None) -> list[str]:
    """Inputs: each signal against the person's norm (Bayesian like the app by default, or the old 14-day median)."""
    signals = PM_SIGNALS if dataset == "pmdata" else LS_SIGNALS
    kinds = ("_z", "_dev3") if (norm or NORM) == "median" else ("_bz", "_bz3")
    cols = [f"{s}{k}" for s in signals for k in kinds]
    if dataset == "pmdata":
        cols += ["sleep_quality", "soreness", "readiness", "ref_mood", "ref_fatigue", "ref_readiness"]
    else:
        cols += ["neg_emotion_today"]
    cols.append("weekend")
    return [c for c in cols if c in f.columns]


def load(dataset: str) -> pd.DataFrame:
    f = pd.read_csv(PROCESSED / f"features_{dataset}.csv")
    if dataset == "pmdata":
        f = add_history(add_pmdata_targets(f))
    f = bayes_features.add_bayes(f, PM_SIGNALS if dataset == "pmdata" else LS_SIGNALS)
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
    """Each row scored by a model trained only on the other folds' people.

    Inputs whose norm prior is learned from people (steps, fatigue, stress; LifeSnaps signals) are recomputed for
    every fold with priors from the other folds only, so a scored person never shapes their own inputs.
    """
    out = {name: np.full(len(f), np.nan) for name in models()}
    y = f[target].to_numpy(int)
    signals = sorted({c.rsplit("_bz", 1)[0] for c in cols if "_bz" in c})
    refit = bool(bayes_features.fitted_signals(signals))
    x = f[cols].to_numpy(float)
    for fold in sorted(f["fold"].unique()):
        test = (f["fold"] == fold).to_numpy()
        if refit:
            x = bayes_features.refit_for_fold(f, signals, f["fold"] != fold)[cols].to_numpy(float)
        for name, m in models().items():
            m.fit(x[~test], y[~test])
            out[name][test] = m.predict_proba(x[test])[:, 1]
    return out


def within_person_auc(people: np.ndarray, y: np.ndarray, s: np.ndarray) -> dict[str, float]:
    """AUC inside each person (people with both kinds of days): does it find the bad day of this person?"""
    out = {}
    for p in np.unique(people):
        i = people == p
        if len(np.unique(y[i])) == 2:
            out[p] = float(roc_auc_score(y[i], s[i]))
    return out


def within_bootstrap(a: dict[str, float], b: dict[str, float] | None = None,
                     n: int = N_BOOT, seed: int = SEED) -> tuple[float, float]:
    """95% interval of the mean within-person AUC (or of its difference), resampling people."""
    ids = sorted(a)
    diff = np.array([a[p] - (b[p] if b else 0.0) for p in ids])
    rng = np.random.default_rng(seed)
    means = [diff[rng.integers(0, len(ids), len(ids))].mean() for _ in range(n)]
    lo, hi = np.percentile(means, [2.5, 97.5])
    return round(float(lo), 3), round(float(hi), 3)


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
    check_in = check_in_only(cols)
    scores["random forest, check-in only"] = out_of_person_scores(d, check_in, task.target)["random forest"]
    if task.dataset == "pmdata":
        history = [c for c in d.columns if c.endswith(HISTORY)]
        scores["random forest, check-in + last days"] = out_of_person_scores(
            d, check_in + history, task.target)["random forest"]
    ref_within = within_person_auc(people, y, ref)
    rows = []
    for name, s in scores.items():
        auc = round(float(roc_auc_score(y, s)), 3)
        lo, hi = person_bootstrap(people, y, s)
        within = within_person_auc(people, y, s)
        row = {"task": task.name, "dataset": task.dataset, "method": name, "auc": auc, "auc_95": f"{lo}-{hi}",
               "pr_auc": round(float(average_precision_score(y, s)), 3),
               "within_auc": round(float(np.mean(list(within.values()))), 3)}
        if name != "same as today (reference)":
            dlo, dhi = person_bootstrap(people, y, s, ref)
            row["vs_reference_95"] = f"{dlo:+.3f}..{dhi:+.3f}"
            wlo, whi = within_bootstrap(within, ref_within)
            row["within_vs_reference_95"] = f"{wlo:+.3f}..{whi:+.3f}"
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
    import json
    import sys

    if sys.argv[1:] == ["export"]:
        out = export()
        EXPORT_FILE.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {EXPORT_FILE} ({len(out['days'])} days)", json.dumps(out["models"], indent=1))
        return
    if sys.argv[1:] == ["crew"]:
        print(json.dumps(crew_scores(), indent=1))
        return
    scores, signals = run()
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(scores.to_string(index=False))
        print()
        print(signals.to_string(index=False))



# ---------------------------------------------------------------------------------------------
# Export for the app: forecasts for the real-data demo person, from models that never saw them.
#
#     python -m pipeline.wellbeing export     -> data/processed/wellbeing_demo.json
# ---------------------------------------------------------------------------------------------

EXPORT_FILE = PROCESSED / "wellbeing_demo.json"
MIN_REASON = 0.01   # a sign is named only if it adds at least 1 percentage point to the risk
EXPORT_TASKS = {   # target -> (task name, inputs): the best honest variant per target (docs/wellbeing-model.md)
    "mood": ("worse mood", "check-in + last days"),
    "fatigue": ("more tired (fatigue)", "check-in + last days"),
}
LABELS = {
    "mood": "mood (1-5)", "fatigue": "energy (1-5, 5 = fresh)", "stress": "calm (1-5, 5 = relaxed)",
    "readiness": "readiness (0-10)", "sleep_quality": "sleep quality (1-5)", "soreness": "soreness (1-5, 5 = none)",
    "sleep_hours": "sleep, self-report (h)", "sleep_hours_device": "sleep, wristband (h)",
    "heart_rate": "resting pulse (bpm)", "exercise_min": "exercise (min)", "steps": "steps",
}


def export_columns(inputs: str, d: pd.DataFrame) -> list[str]:
    cols = feature_columns("pmdata", d)
    if inputs == "check-in + last days":
        return check_in_only(cols) + [c for c in d.columns if c.endswith(HISTORY)]
    return cols


def describe(col: str, value: float) -> str:
    """One input in plain words, e.g. 'mood (1-5) 1.5 below usual today'."""
    if col == "weekend":
        return "weekend" if value >= 0.5 else "weekday"
    if col.startswith("ref_"):
        name = LABELS[col[4:]]
        return f"{name} {abs(value):.1f} {'below' if value > 0 else 'above'} usual today"
    if col.endswith(("_bz", "_bz3")):
        name = LABELS[col.rsplit("_", 1)[0]]
        when = "today" if col.endswith("_bz") else "on average over the last 3 days"
        return f"{name} {abs(value):.1f} spreads {'below' if value < 0 else 'above'} usual {when}"
    for suffix, text in (("_z", "today"), ("_dev3", "over the last 3 days")):
        if col.endswith(suffix):
            name = LABELS[col[: -len(suffix)]]
            if suffix == "_z":
                return f"{name} {abs(value):.1f} spreads {'below' if value < 0 else 'above'} usual {text}"
            return f"{name} {abs(value):.1f} {'below' if value < 0 else 'above'} usual {text}"
    if col.endswith("_lag1"):
        return f"{LABELS[col[:-5]]} yesterday: {value:g}"
    if col.endswith("_d1"):
        return f"{LABELS[col[:-3]]} {value:+g} since yesterday"
    if col.endswith("_min3"):
        return f"lowest {LABELS[col[:-5]]} in 3 days: {value:g}"
    if col.endswith("_since_low"):
        return f"{value:g} {'day' if value == 1 else 'days'} since {LABELS[col[:-10]]} was last below usual"
    return f"{LABELS.get(col, col)} today: {value:g}"


def forecast_person(d: pd.DataFrame, cols: list[str], target: str, person: str, top: int = 3):
    """Train on everyone but `person`, then forecast their days with SHAP reasons (only signs that raise the risk)."""
    return forecast_rows(d[d["person_id"] != person], d[d["person_id"] == person], cols, target, top)


def forecast_rows(train: pd.DataFrame, test: pd.DataFrame, cols: list[str], target: str, top: int = 3):
    """Fit on `train`, forecast every row of `test` with up to `top` SHAP reasons and what happened next."""
    import shap

    imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    forest = RandomForestClassifier(**FOREST).fit(imputer.fit_transform(train[cols]), train[target].to_numpy(int))
    x = imputer.transform(test[cols])
    prob = forest.predict_proba(x)[:, 1]
    contrib = shap.TreeExplainer(forest).shap_values(x, check_additivity=False)
    contrib = contrib[1] if isinstance(contrib, list) else contrib[..., 1]
    usual = float(train[target].mean())
    out = []
    for i, (_, row) in enumerate(test.iterrows()):
        order = [j for j in np.argsort(-contrib[i])
                 if contrib[i, j] >= MIN_REASON and pd.notna(row[cols[j]])][:top]
        out.append({"probability": round(float(prob[i]), 3), "times_usual": round(float(prob[i]) / usual, 1),
                    "reasons": [describe(cols[j], float(row[cols[j]])) for j in order],
                    "happened": None if pd.isna(row.get(target)) else bool(row[target])})
    return out, usual


def export() -> dict:
    from .demo import DEMO_DAYS, DEMO_PERSON, DEMO_START

    f = load("pmdata")
    start = pd.Timestamp(DEMO_START)
    days = {}
    models_info = {}
    for key, (name, inputs) in EXPORT_TASKS.items():
        task = next(t for t in TASKS if t.name == name)
        d = f[f[task.target].notna() | (f["person_id"] == DEMO_PERSON)].reset_index(drop=True)
        cols = export_columns(inputs, d)
        train = d[d[task.target].notna() & d[task.reference].notna()].reset_index(drop=True)
        people, y = train["person_id"].to_numpy(), train[task.target].to_numpy(int)
        model_within = within_person_auc(people, y, out_of_person_scores(train, cols, task.target)["random forest"])
        ref_within = within_person_auc(people, y, train[task.reference].to_numpy(float))
        fit_on = pd.concat([train[train["person_id"] != DEMO_PERSON], d[d["person_id"] == DEMO_PERSON]])
        window = fit_on["person_id"].ne(DEMO_PERSON) | fit_on["date"].between(
            DEMO_START, (start + pd.Timedelta(days=DEMO_DAYS - 1)).strftime("%Y-%m-%d"))
        fit_on = fit_on[window].reset_index(drop=True)
        rows, usual = forecast_person(fit_on, cols, task.target, DEMO_PERSON)
        dates = fit_on.loc[fit_on["person_id"] == DEMO_PERSON, "date"]
        for date, r in zip(dates, rows):
            day = (pd.Timestamp(date) - start).days + 1
            days.setdefault(day, {"mission_day": day})[key] = r
        models_info[key] = {
            "question": f"Tomorrow: {name}?", "inputs": inputs, "usual_rate": round(usual, 3),
            "within_person_auc": round(float(np.mean(list(model_within.values()))), 3),
            "same_as_today_auc": round(float(np.mean(list(ref_within.values()))), 3),
        }
    return {
        "person": DEMO_PERSON, "source": "PMData (real people); the demo person was never in training",
        "note": "Forecast, not a diagnosis. Scored on people the model never saw: docs/wellbeing-model.md",
        "models": models_info, "days": [days[k] for k in sorted(days)],
    }



# ---------------------------------------------------------------------------------------------
# Tried, NOT shipped: "Tomorrow's outlook" for every crew member (simulated mission).
#
#     python -m pipeline.wellbeing crew
#
# The crew has no fatigue, stress or readiness answers, so this model reads only what the crew has (mood,
# sleep, resting pulse, exercise against the Bayesian norm), trained on real PMData people. It beats "same as
# today" on real people but NOT on the simulated crew, whose mood only copies simple day-to-day persistence.
# Why and what would fix it: docs/wellbeing-model.md, "Tried for the crew, not shipped".
# ---------------------------------------------------------------------------------------------

CREW_SIGNALS = ["mood", "sleep_hours", "heart_rate", "exercise_min"]


def crew_columns() -> list[str]:
    return [f"{s}_{k}" for s in CREW_SIGNALS for k in ("bz", "bz3")] + ["ref_mood"]


def crew_frame(days: pd.DataFrame) -> pd.DataFrame:
    """Simulated crew days in the shape of the PMData table: one row per person-day, inputs and target."""
    f = days.rename(columns={"astronaut_id": "person_id"}).copy()
    f["date"] = f["mission_day"]
    f = add_pmdata_targets(f, ("mood",))
    return bayes_features.add_bayes(f.assign(is_test=False), CREW_SIGNALS)


def crew_scores() -> dict:
    """Within-person AUC of the crew model: on real people (scored out of person) and on 30 simulated missions."""
    from . import model as M
    from . import simulation as sim

    task = next(t for t in TASKS if t.name == "worse mood")
    real = load("pmdata")
    real = real[real[task.target].notna() & real[task.reference].notna()].reset_index(drop=True)
    y, people = real[task.target].to_numpy(int), real["person_id"].to_numpy()
    model = within_person_auc(people, y, out_of_person_scores(real, crew_columns(), task.target)["random forest"])
    ref = within_person_auc(people, y, real[task.reference].to_numpy(float))
    lo, hi = within_bootstrap(model, ref)
    cal = sim.calibrate(pd.read_csv(PROCESSED / "daily.csv"), pd.read_csv(PROCESSED / "nhanes_reference.csv"))
    days, _ = sim.training_missions(cal, 30, M.TEST_SEED)
    s = crew_frame(days.assign(astronaut_id=days["mission_id"] + "/" + days["astronaut_id"]))
    s = s[s["y_mood"].notna() & s["ref_mood"].notna()].reset_index(drop=True)
    rows, _ = forecast_rows(real, s, crew_columns(), "y_mood", top=0)
    sp, sy = s["person_id"].to_numpy(), s["y_mood"].to_numpy(int)
    sim_model = within_person_auc(sp, sy, np.array([r["probability"] for r in rows]))
    sim_ref = within_person_auc(sp, sy, s["ref_mood"].to_numpy(float))
    mean = lambda d: round(float(np.mean(list(d.values()))), 3)
    return {"real_people": {"model": mean(model), "same_as_today": mean(ref), "difference_95": [lo, hi]},
            "simulated_crew": {"model": mean(sim_model), "same_as_today": mean(sim_ref)}}



if __name__ == "__main__":
    main()
