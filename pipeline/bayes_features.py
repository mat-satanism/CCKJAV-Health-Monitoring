"""Model inputs measured against the app's Bayesian personal norm, not the old 14-day median.

The app colours every status with the Bayesian norm (backend/app/status.py, docs/personal-norm.md): a population
prior updated with the person's last 14 values, so both their level and their own day-to-day spread are learned.
This module gives the models the same view, so "unusual for this person" means the same thing everywhere:

    <signal>_bz     today's distance from the Bayesian norm, in the person's predictive scale
    <signal>_bz3    the same, mean of the last 3 days

Only values before today enter the norm. Priors: the app's own (models/norm_priors.json) where the app has the
indicator; otherwise fitted on the training people's days (folds 0-3), never on held-out people.
"""
import json
import math
import sys

import numpy as np
import pandas as pd

from .common import ROOT

sys.path.insert(0, str(ROOT / "backend"))
from app import status  # pyright: ignore[reportMissingImports]  (backend/ is put on the path above)

APP_PRIOR = {   # model signal -> app indicator whose prior applies
    "heart_rate": "heart_rate", "sleep_hours": "sleep_hours", "sleep_hours_device": "sleep_hours",
    "mood": "mood", "exercise_min": "exercise_min", "hrv_ms": "hrv_ms",
}
APP_PRIORS = json.loads((ROOT / "models" / "norm_priors.json").read_text())["indicators"]


def bayes_norm(window: list[float], prior: dict) -> tuple[float, float] | None:
    """Center and predictive scale for the next value; the same formulas as status.predictive."""
    n = len(window)
    if n < status.BAYES_MIN:
        return None
    sigma2, tau2 = prior["sigma"] ** 2, max(prior["tau0"], 1e-6) ** 2
    k0, b0 = sigma2 / tau2, sigma2 * (status.ALPHA0 - 1)
    ybar = sum(window) / n
    ss = sum((y - ybar) ** 2 for y in window)
    kn, an = k0 + n, status.ALPHA0 + n / 2
    mn = (k0 * prior["m0"] + n * ybar) / kn
    bn = b0 + ss / 2 + k0 * n * (ybar - prior["m0"]) ** 2 / (2 * kn)
    return mn, math.sqrt(bn * (kn + 1) / (an * kn))


def fit_prior(f: pd.DataFrame, col: str) -> dict:
    """Typical level, how much people differ, typical day-to-day spread; like pipeline/norm.py fit_priors."""
    g = f.groupby("person_id")[col]
    means, variances = g.mean().dropna(), g.var().dropna()
    return {"m0": float(means.mean()), "tau0": float(means.std()), "sigma": float(np.sqrt(variances.mean()))}


def priors_for(f: pd.DataFrame, signals: list[str]) -> dict[str, dict]:
    train = f[~f["is_test"]]
    return {s: APP_PRIORS[APP_PRIOR[s]] if s in APP_PRIOR else fit_prior(train, s) for s in signals}


def add_bayes(f: pd.DataFrame, signals: list[str]) -> pd.DataFrame:
    """Add <signal>_bz and <signal>_bz3. Rows are a full daily calendar per person; gaps are skipped like the app."""
    f = f.sort_values(["person_id", "date"]).copy()
    priors = priors_for(f, signals)
    for s in signals:
        bz = np.full(len(f), np.nan)
        pos = 0
        for _, g in f.groupby("person_id", sort=False):
            past: list[float] = []
            for i, x in enumerate(g[s].to_numpy(float)):
                if not np.isnan(x):
                    norm = bayes_norm(past[-status.NORM_DAYS:], priors[s])
                    if norm is not None:
                        bz[pos + i] = (x - norm[0]) / norm[1]
                    past.append(x)
            pos += len(g)
        f[f"{s}_bz"] = bz
        f[f"{s}_bz3"] = pd.Series(bz, index=f.index).groupby(f["person_id"]).transform(
            lambda x: x.rolling(3, min_periods=2).mean())
    return f
