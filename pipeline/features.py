"""Feature tables for the model: one file per dataset (PMData, LifeSnaps).

Each row is one person on one calendar day t. Days with no record are kept as empty rows,
so "tomorrow" is always t + 1 day and never "the next record".

Leakage rules (tested in pipeline/tests):
- features of day t use only days up to t; the personal baseline uses days t-14 .. t-1;
- the target is the state on day t + 1;
- people are split into folds before anything is learned: no person is in two folds.

Why two files and not one: the targets differ (PMData: 1-5 mood scale, LifeSnaps: yes/no feelings),
so the datasets are kept apart and only compared with themselves.
"""
from collections.abc import Callable

import numpy as np
import pandas as pd

BASELINE_DAYS = 14        # personal norm = median of the previous 14 days (provisional, see docs/data.md)
MIN_BASELINE_OBS = 7      # no norm if fewer than 7 of those days have a value
RECENT_DAYS = 3           # *_dev3 = mean deviation over the last 3 days
MIN_SPREAD_PERCENTILE = 10  # z-scores never divide by less than this percentile of the training spreads
SEED = 42
N_FOLDS = 5
TEST_FOLD = 4             # held-out people; folds 0-3 are for training and cross-validation

PMDATA_FEATURES = ["heart_rate", "sleep_hours_device", "exercise_min", "steps",
                   "sleep_hours", "mood", "fatigue", "stress"]
PMDATA_PLAIN = ["sleep_quality", "soreness", "readiness"]  # today's value only, no baseline
LIFESNAPS_FEATURES = ["heart_rate", "sleep_hours_device", "exercise_min", "steps", "stress_score", "temp_skin"]
NEGATIVE_FEELINGS = ["emo_sad", "emo_tense", "emo_tired"]


def pmdata_targets(grid: pd.DataFrame, out: pd.DataFrame) -> None:
    """target_worse_mood = tomorrow's mood is below this person's usual (median of the last 14 days, today included)."""
    mood = grid["mood"].astype(float)
    ref = mood.rolling(BASELINE_DAYS, min_periods=MIN_BASELINE_OBS).median()
    tomorrow = mood.shift(-1)
    out["mood_ref"] = ref
    out["mood_next"] = tomorrow
    out["target_worse_mood"] = (tomorrow < ref).astype(float).where(tomorrow.notna() & ref.notna())
    # for the "same as today" baseline
    out["worse_mood_today"] = (mood < ref).astype(float).where(mood.notna() & ref.notna())


def lifesnaps_targets(grid: pd.DataFrame, out: pd.DataFrame) -> None:
    """target_neg_emotion = tomorrow the person ticked sad, tense/anxious or tired. Empty unless all three were answered."""
    negative = grid[NEGATIVE_FEELINGS].astype(float).max(axis=1, skipna=False)
    out["neg_emotion_today"] = negative
    out["target_neg_emotion"] = negative.shift(-1)


def person_features(person_id: str, dataset: str, g: pd.DataFrame, features: list[str],
                    plain: list[str], add_targets: Callable[[pd.DataFrame, pd.DataFrame], None]) -> pd.DataFrame:
    g = g.sort_values("date").set_index("date")
    grid = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="D"))
    grid.index.name = "date"

    out = pd.DataFrame(index=grid.index)
    out["person_id"] = person_id
    out["source_dataset"] = dataset
    out["day"] = (grid.index - grid.index[0]).days + 1
    out["dow"] = grid.index.day_of_week
    for col in features:
        x = grid[col].astype(float)
        window = x.shift(1).rolling(BASELINE_DAYS, min_periods=MIN_BASELINE_OBS)  # days before today only
        base = window.median()
        dev = x - base
        out[col] = x
        out[f"{col}_base"] = base
        out[f"{col}_dev"] = dev
        out[f"{col}_dev3"] = dev.rolling(RECENT_DAYS, min_periods=2).mean()
        out[f"{col}_spread"] = window.std()
    for col in plain:
        out[col] = grid[col].astype(float)
    add_targets(grid, out)
    return out.reset_index()


def assign_folds(person_ids, seed: int = SEED, n_folds: int = N_FOLDS) -> dict[str, int]:
    """Shuffle people with a fixed seed, then deal them into folds. Same input, same folds."""
    ids = sorted(person_ids)
    np.random.default_rng(seed).shuffle(ids)
    return {pid: i % n_folds for i, pid in enumerate(ids)}


def build_dataset(daily: pd.DataFrame, dataset: str, features: list[str], plain: list[str],
                  add_targets: Callable[[pd.DataFrame, pd.DataFrame], None]) -> pd.DataFrame:
    d = daily[daily["source_dataset"] == dataset].copy()
    d["date"] = pd.to_datetime(d["date"])
    frames = [person_features(pid, dataset, g, features, plain, add_targets) for pid, g in d.groupby("person_id")]
    f = pd.concat(frames, ignore_index=True)

    f["fold"] = f["person_id"].map(assign_folds(f["person_id"].unique()))
    f["is_test"] = f["fold"] == TEST_FOLD

    # z = deviation / spread. The floor comes from training folds only, so test people stay unseen.
    train = f[~f["is_test"]]
    for col in features:
        spreads = train[f"{col}_spread"]
        positive = spreads[spreads > 0].dropna()
        floor = float(np.percentile(positive, MIN_SPREAD_PERCENTILE)) if len(positive) else 1.0
        f[f"{col}_z"] = f[f"{col}_dev"] / f[f"{col}_spread"].clip(lower=floor)
        f = f.drop(columns=f"{col}_spread")

    first = ["person_id", "source_dataset", "date", "day", "dow", "fold", "is_test"]
    rest = [c for c in f.columns if c not in first]
    f = f[first + rest].sort_values(["person_id", "date"]).reset_index(drop=True)
    f["date"] = f["date"].dt.strftime("%Y-%m-%d")
    return f


def build_all(daily: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "features_pmdata.csv": build_dataset(daily, "pmdata", PMDATA_FEATURES, PMDATA_PLAIN, pmdata_targets),
        "features_lifesnaps.csv": build_dataset(daily, "lifesnaps", LIFESNAPS_FEATURES, [], lifesnaps_targets),
    }
