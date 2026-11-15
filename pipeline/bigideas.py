"""BIG IDEAs Lab Glycemic Variability and Wearable Device Data (PhysioNet, v1.1.2): real day-to-day glucose.

16 adults aged 35-65 (HbA1c 5.2-6.4%, high-normal to prediabetic), Dexcom G6 sensor every 5 minutes for 8-10
days. License: Open Data Commons Attribution 1.0. https://physionet.org/content/big-ideas-glycemic-wearable/1.1.2/

We use one number per person per day: the morning glucose, the median of the sensor readings from 05:00 to 07:00
(before breakfast, close to fasting), when at least 12 readings (one hour) exist. From it, the crew simulation takes
how much one person's morning glucose changes from day to day (the level still comes from NHANES, healthy adults).
Download: python -m pipeline.get_data bigideas
"""
from pathlib import Path

import numpy as np
import pandas as pd

from .common import RAW

FOLDER = RAW / "bigideas"
MORNING_HOURS = (5, 7)        # 05:00-06:59
MIN_READINGS = 12             # one hour of 5-minute readings


def morning_glucose(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path)
    d = d[d["Event Type"] == "EGV"]
    x = pd.DataFrame({"t": pd.to_datetime(d["Timestamp (YYYY-MM-DDThh:mm:ss)"], errors="coerce"),
                      "g": pd.to_numeric(d["Glucose Value (mg/dL)"], errors="coerce")}).dropna()
    x = x[(x["t"].dt.hour >= MORNING_HOURS[0]) & (x["t"].dt.hour < MORNING_HOURS[1])]
    day = x.groupby(x["t"].dt.date)["g"].agg(["median", "count"]).reset_index()
    day = day[day["count"] >= MIN_READINGS]
    return pd.DataFrame({"person_id": "bi_" + path.stem.split("_")[-1], "date": day["t"].astype(str),
                         "glucose_morning": day["median"], "readings": day["count"]})


def load(folder: Path = FOLDER) -> pd.DataFrame:
    files = sorted(folder.glob("Dexcom_*.csv"))
    if not files:
        return pd.DataFrame(columns=["person_id", "date", "glucose_morning", "readings"])
    return pd.concat([morning_glucose(f) for f in files], ignore_index=True)


def day_to_day(table: pd.DataFrame) -> dict:
    """Median over people of the morning glucose spread and persistence (persistence clipped to 0-0.9, like the
    other calibrated signals: with 8-10 days a person's autocorrelation is mostly noise)."""
    per = table.sort_values("date").groupby("person_id")["glucose_morning"]
    sd = per.std().median()
    phi = per.apply(lambda s: s.reset_index(drop=True).autocorr(1)).median()
    return {"sd": round(float(sd), 1), "phi": round(float(np.clip(phi, 0.0, 0.9)), 2),
            "people": int(per.ngroups), "days": len(table)}
