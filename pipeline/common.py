"""Shared paths and the column layout of the daily table."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

# One row = one person on one day. Self-reports and device values live in
# separate columns on purpose: they are not the same measurement.
DAILY_COLUMNS = [
    "person_id",
    "source_dataset",
    "date",
    "day",                 # 1 = the person's first day in the dataset
    "heart_rate",          # resting heart rate, bpm (device)
    "sleep_hours",         # self-reported sleep, hours
    "sleep_hours_device",  # sleep measured by the device, hours
    "sleep_quality",       # self-report, 1-5 (PMData; NASA OCHMO uses 1-7, not converted)
    "mood",                # self-report, 1-5 (PMData)
    "fatigue",             # self-report, 1-5 (PMData)
    "stress",              # self-report, 1-5 (PMData)
    "soreness",            # self-report, 1-5 (PMData)
    "readiness",           # self-report, 0-10 (PMData)
    "stress_score",        # device stress score, 0-100 (LifeSnaps)
    "exercise_min",        # moderately + very active minutes (device)
    "steps",               # steps per day (device)
    "temp_skin",           # nightly skin temperature, deg C (device, LifeSnaps)
    # Short mood survey in LifeSnaps: 1 = the person ticked this feeling that day, 0 = did not.
    "emo_alert", "emo_happy", "emo_neutral", "emo_relaxed", "emo_sad", "emo_tense", "emo_tired",
]


# Values outside these ranges are impossible for the scale or the body and are
# set to empty (not clipped): e.g. PMData has a few 0 answers on its 1-5 scales,
# and Fitbit sometimes logs a 17-24 hour "sleep".
VALID_RANGES = {
    "sleep_quality": (1, 5), "mood": (1, 5), "fatigue": (1, 5), "stress": (1, 5), "soreness": (1, 5),
    "readiness": (0, 10),
    "sleep_hours": (0.5, 16), "sleep_hours_device": (0.5, 16),
    "heart_rate": (30, 220),
    "stress_score": (0, 100),
    "temp_skin": (20, 42),
}


def drop_impossible(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col, (lo, hi) in VALID_RANGES.items():
        if col in df.columns:
            df[col] = df[col].where(df[col].between(lo, hi))
    return df


def finish_daily(df: pd.DataFrame, dataset: str) -> pd.DataFrame:
    """Drop impossible values, add dataset name and day index, put columns in the shared order."""
    df = drop_impossible(df)
    df["source_dataset"] = dataset
    if "day" not in df.columns:
        first = df.groupby("person_id")["date"].transform("min")
        df["day"] = (df["date"] - first).dt.days + 1
    for col in DAILY_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    return df[DAILY_COLUMNS].sort_values(["person_id", "day"]).reset_index(drop=True)
