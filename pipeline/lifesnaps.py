"""LifeSnaps (Zenodo record 7229547): Fitbit Sense data for 71 people, 2021-2022."""
from pathlib import Path

import pandas as pd

from .common import RAW, finish_daily

CSV_PATH = RAW / "lifesnaps" / "csv" / "daily_fitbit_sema_df_unprocessed.csv"


def tidy(raw: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame({
        "person_id": "ls_" + raw["id"].astype(str),
        "date": pd.to_datetime(raw["date"]).dt.normalize(),
        "heart_rate": raw["resting_hr"],
        # 0 minutes asleep means the watch was not worn that night.
        "sleep_hours_device": raw["minutesAsleep"].where(raw["minutesAsleep"] > 0) / 60,
        "exercise_min": raw[["moderately_active_minutes", "very_active_minutes"]].sum(axis=1, min_count=1),
        "steps": raw["steps"],
        "temp_skin": raw["nightly_temperature"],
        "stress_score": raw["stress_score"],
    })
    return finish_daily(df, "lifesnaps")


def load(csv_path: Path = CSV_PATH) -> pd.DataFrame:
    return tidy(pd.read_csv(csv_path))
