"""PMData (Simula): Fitbit + daily self-reports for 16 people, Nov 2019 - Mar 2020."""
import json
import re
import zipfile
from functools import reduce
from io import BytesIO
from pathlib import Path

import pandas as pd

from .common import RAW, finish_daily

ZIP_PATH = RAW / "pmdata" / "pmdata.zip"
# Participants were in Norway; self-report timestamps are UTC, so the calendar
# day is taken in local time.
LOCAL_TZ = "Europe/Oslo"


def wellness(raw: pd.DataFrame) -> pd.DataFrame:
    """Daily self-report. If a person answered twice on one day, keep the last answer."""
    ts = pd.to_datetime(raw["effective_time_frame"], utc=True)
    df = raw.assign(_ts=ts, date=ts.dt.tz_convert(LOCAL_TZ).dt.tz_localize(None).dt.normalize())
    df = df.sort_values("_ts").drop_duplicates("date", keep="last")
    df = df.rename(columns={"sleep_duration_h": "sleep_hours"})
    cols = ["date", "mood", "fatigue", "stress", "sleep_quality", "readiness", "soreness", "sleep_hours"]
    return df[cols].astype({c: "float" for c in cols[1:]})


def resting_heart_rate(records: list[dict]) -> pd.DataFrame:
    """Fitbit resting HR per day. A value of 0 means 'no measurement' and is dropped."""
    df = pd.DataFrame(
        {"date": [r["dateTime"] for r in records], "heart_rate": [r["value"]["value"] for r in records]}
    )
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df[df["heart_rate"] > 0]


def daily_value(records: list[dict], name: str) -> pd.DataFrame:
    """Fitbit files of the form [{"dateTime": ..., "value": "12"}], summed per day."""
    df = pd.DataFrame({"date": [r["dateTime"] for r in records], name: [float(r["value"]) for r in records]})
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df.groupby("date", as_index=False)[name].sum()


def main_sleep(records: list[dict]) -> pd.DataFrame:
    """Hours asleep in the main sleep of each night (naps are left out)."""
    rows = [(r["dateOfSleep"], r["minutesAsleep"]) for r in records if r.get("mainSleep", True)]
    df = pd.DataFrame(rows, columns=["date", "minutes"])
    df["date"] = pd.to_datetime(df["date"])
    out = df.groupby("date", as_index=False)["minutes"].sum()
    out["sleep_hours_device"] = out.pop("minutes") / 60
    return out[out["sleep_hours_device"] > 0]


def _person(z: zipfile.ZipFile, names: set[str], pid: str) -> pd.DataFrame | None:
    def js(name):
        path = f"{pid}/fitbit/{name}"
        return json.loads(z.read(path)) if path in names else None

    parts = []
    wpath = f"{pid}/pmsys/wellness.csv"
    if wpath in names:
        parts.append(wellness(pd.read_csv(BytesIO(z.read(wpath)))))
    if (rec := js("resting_heart_rate.json")) is not None:
        parts.append(resting_heart_rate(rec))
    if (rec := js("sleep.json")) is not None:
        parts.append(main_sleep(rec))
    if (rec := js("steps.json")) is not None:
        parts.append(daily_value(rec, "steps"))
    active = [daily_value(r, n) for n in ("moderately", "very")
              if (r := js(f"{n}_active_minutes.json")) is not None]
    if active:
        ex = reduce(lambda a, b: a.merge(b, on="date", how="outer"), active)
        ex["exercise_min"] = ex.drop(columns="date").sum(axis=1, min_count=1)
        parts.append(ex[["date", "exercise_min"]])
    if not parts:
        return None
    df = reduce(lambda a, b: a.merge(b, on="date", how="outer"), parts)
    df["person_id"] = f"pm_{pid}"
    return df


def load(zip_path: Path = ZIP_PATH) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
        pids = sorted({m.group(1) for n in names if (m := re.match(r"(p\d{2})/", n))})
        frames = [f for pid in pids if (f := _person(z, names, pid)) is not None]
    return finish_daily(pd.concat(frames, ignore_index=True), "pmdata")
