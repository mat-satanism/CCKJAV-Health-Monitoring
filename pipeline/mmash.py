"""MMASH (PhysioNet): about 24 hours of wearable data for 22 young men.

The files have no calendar dates, only day numbers (1, 2), so `date` stays empty.
"""
import re
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd

from .common import RAW, finish_daily

ZIP_PATH = RAW / "mmash" / "mmash-1.0.0.zip"


def _inner_zip(outer: zipfile.ZipFile) -> zipfile.ZipFile:
    name = next(n for n in outer.namelist() if n.endswith("/MMASH.zip"))
    return zipfile.ZipFile(BytesIO(outer.read(name)))


def _read_user_csv(z: zipfile.ZipFile, names: set[str], user: str, fname: str) -> pd.DataFrame | None:
    path = next((n for n in names if n.endswith(f"/{user}/{fname}")), None)
    return pd.read_csv(BytesIO(z.read(path))) if path else None


def person_days(sleep: pd.DataFrame | None, actigraph: pd.DataFrame | None) -> pd.DataFrame:
    parts = []
    if sleep is not None and len(sleep):
        s = sleep.groupby("In Bed Date", as_index=False)["Total Sleep Time (TST)"].sum()
        s.columns = ["day", "sleep_hours_device"]
        s["sleep_hours_device"] /= 60
        parts.append(s)
    if actigraph is not None and len(actigraph):
        a = actigraph.groupby("day", as_index=False)["Steps"].sum().rename(columns={"Steps": "steps"})
        parts.append(a)
    if not parts:
        return pd.DataFrame(columns=["day"])
    df = parts[0] if len(parts) == 1 else parts[0].merge(parts[1], on="day", how="outer")
    return df


def load(zip_path: Path = ZIP_PATH) -> pd.DataFrame:
    frames = []
    with zipfile.ZipFile(zip_path) as outer, _inner_zip(outer) as z:
        names = set(z.namelist())
        users = sorted({m.group(1) for n in names if (m := re.search(r"(user_\d+)/", n))},
                       key=lambda u: int(u.split("_")[1]))
        for user in users:
            df = person_days(_read_user_csv(z, names, user, "sleep.csv"),
                             _read_user_csv(z, names, user, "Actigraph.csv"))
            df["person_id"] = f"mm_{user}"
            frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    # Two users have a few actigraph rows with day = -29; the study only covers days 1-2.
    df = df[df["day"] >= 1]
    df["date"] = pd.NaT
    return finish_daily(df, "mmash")
