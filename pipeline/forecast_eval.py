"""Which 7-day forecast should the app draw on its charts? Fitted and scored on real people.

    python -m pipeline.forecast_eval

For every person and indicator (PMData, LifeSnaps), at every day with at least 14 earlier values, each method
forecasts the next 7 values from the past only, like the app does (values in time order, gaps skipped).
Error = |forecast - actual| / the person's usual spread (std of the 14-value window), so pulse, sleep and mood can
be averaged; reported relative to "same as today" (the last value): below 1 is better.

The app's settings per indicator (`FORECAST` in backend/app/analytics.py) are fitted here on training people
only (folds 0-3) and scored on the other people (fold 4). The script fails if the code and the fit disagree.
"""
import sys

import numpy as np
import pandas as pd

from .common import PROCESSED, ROOT
from .features import TEST_FOLD, assign_folds

sys.path.insert(0, str(ROOT / "backend"))
from app import analytics  # pyright: ignore[reportMissingImports]  (backend/ is put on the path above)

HORIZON = 7
WINDOW = analytics.BASELINE_DAYS
PERSISTENCE_GRID = [0.0, 0.2, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
COVERAGE = 0.8
SERIES = [   # (indicator in the app, daily.csv column, dataset)
    ("heart_rate", "heart_rate", "pmdata"), ("heart_rate", "heart_rate", "lifesnaps"),
    ("sleep_hours", "sleep_hours", "pmdata"), ("sleep_hours", "sleep_hours_device", "lifesnaps"),
    ("mood", "mood", "pmdata"),
    ("exercise_min", "exercise_min", "pmdata"), ("exercise_min", "exercise_min", "lifesnaps"),
    ("hrv_ms", "hrv_ms", "lifesnaps"),
]
HS = np.arange(1, HORIZON + 1)


def series() -> list[tuple[str, str, np.ndarray]]:
    daily = pd.read_csv(PROCESSED / "daily.csv").sort_values(["person_id", "date"])
    out = []
    for ind, col, ds in SERIES:
        d = daily[(daily["source_dataset"] == ds) & daily[col].notna()]
        for pid, g in d.groupby("person_id"):
            v = g[col].to_numpy(float)
            if len(v) >= WINDOW + HORIZON:
                out.append((ind, pid, v))
    return out


def origins(data) -> pd.DataFrame:
    """One row per (series, forecast day): the past window summary and the 7 real values that followed."""
    rows = []
    for ind, pid, v in data:
        for t in range(WINDOW, len(v) - HORIZON + 1):
            w = v[t - WINDOW:t]
            rows.append({"indicator": ind, "person": pid, "norm": float(np.median(w)),
                         "spread": float(np.std(w)) or 1.0, "last": v[t - 1], "past": v[:t], "future": v[t:t + HORIZON]})
    return pd.DataFrame(rows)


def _back_to_norm(o: pd.DataFrame, phi: float) -> np.ndarray:
    gap = (o["last"] - o["norm"]).to_numpy()[:, None]
    return o["norm"].to_numpy()[:, None] + gap * phi ** HS


def _err(o: pd.DataFrame, pred: np.ndarray) -> float:
    fut = np.stack(o["future"].to_numpy())
    return float((np.abs(pred - fut).mean(axis=1) / o["spread"].to_numpy()).mean())


def fit(o: pd.DataFrame) -> dict:
    """Per indicator: the persistence with the lowest error, then the band width that holds 80% of real values."""
    out = {}
    for ind, g in o.groupby("indicator"):
        phi = min(PERSISTENCE_GRID, key=lambda p: _err(g, _back_to_norm(g, p)))
        unit = np.sqrt((1 - phi ** (2 * HS)) + 1 / WINDOW) * g["spread"].to_numpy()[:, None]
        ratio = np.abs(np.stack(g["future"].to_numpy()) - _back_to_norm(g, phi)) / unit
        out[ind] = {"persistence": phi, "band": round(float(np.quantile(ratio, COVERAGE)), 2)}
    return out


METHODS = {
    "current (straight line)": lambda past, _ind: analytics.linear_forecast(list(past), HORIZON),
    "same as today": lambda past, _ind: [past[-1]] * HORIZON,
    "usual level (median 14 d)": lambda past, _ind: [float(np.median(past[-WINDOW:]))] * HORIZON,
    "back to own norm (new)": lambda past, ind: analytics.forecast(list(past), HORIZON, ind),
}


def score(o: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    errs = {}
    for name, f in METHODS.items():
        pred = np.stack([np.asarray(f(p, i), float) for p, i in zip(o["past"], o["indicator"])])
        errs[name] = pd.Series(np.abs(pred - np.stack(o["future"].to_numpy())).mean(axis=1)
                               / o["spread"].to_numpy()).groupby(o["indicator"].to_numpy()).mean()
    table = pd.DataFrame(errs)
    table.loc["ALL (mean of indicators)"] = table.mean()
    rel = table.div(table["same as today"], axis=0).round(3)
    inside = []
    for p, i, fut in zip(o["past"], o["indicator"], o["future"]):
        band = analytics.forecast_band(list(p), HORIZON, i)
        inside.append(np.mean([lo <= y <= hi for (_, lo, hi), y in zip(band, fut)]))
    cover = pd.Series(inside).groupby(o["indicator"].to_numpy()).mean().round(3)
    return rel, cover


def simulation_check() -> tuple[pd.DataFrame, pd.Series]:
    """Tried for a per-astronaut 'tomorrow' view: the same forecast on 30 simulated missions (not shipped)."""
    from . import model as M
    from . import simulation as sim

    cal = sim.calibrate(pd.read_csv(PROCESSED / "daily.csv"), pd.read_csv(PROCESSED / "nhanes_reference.csv"))
    days, _ = sim.training_missions(cal, 30, M.TEST_SEED)
    data = [(ind, f"{m}/{a}", g[ind].to_numpy(float))
            for ind in ("heart_rate", "sleep_hours", "mood", "exercise_min", "hrv_ms")
            for (m, a), g in days.sort_values("mission_day").groupby(["mission_id", "astronaut_id"])]
    return score(origins(data))


def main() -> None:
    if sys.argv[1:] == ["sim"]:
        rel, cover = simulation_check()
        print(rel.to_string(), "\n\nShare inside the 80% band:\n", cover.to_string())
        return
    data = series()
    people = sorted({p for _, p, _ in data})
    folds = assign_folds(people)
    o = origins(data)
    is_test = o["person"].map(folds).eq(TEST_FOLD)
    fitted = fit(o[~is_test])
    print(f"{len(data)} series, {len(people)} people, {len(o)} forecasts; "
          f"settings fitted on {o.loc[~is_test, 'person'].nunique()} people, scored on {o.loc[is_test, 'person'].nunique()}")
    print("fitted settings:", fitted)
    rel, cover = score(o[is_test].reset_index(drop=True))
    with pd.option_context("display.width", 200, "display.max_columns", 10):
        print("\nError relative to 'same as today', test people (< 1 is better):")
        print(rel.to_string())
        print(f"\nShare of real values inside the {COVERAGE:.0%} band, test people:")
        print(cover.to_string())
    if fitted != analytics.FORECAST:
        sys.exit(f"\nbackend/app/analytics.py FORECAST differs from the fit above: update it.\ncode: {analytics.FORECAST}")


if __name__ == "__main__":
    main()
