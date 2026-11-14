"""Build the tidy tables in data/processed/ from data/raw/.

    python -m pipeline.get_data   # once
    python -m pipeline.build

Writes:
    daily.csv               one row per person per day (PMData, LifeSnaps, MMASH)
    inspiration4_blood.csv  one row per crew member, timepoint and analyte, with lab ranges
    nhanes_reference.csv    population percentiles for blood pressure, pulse and glucose
"""
import pandas as pd

from . import inspiration4, lifesnaps, mmash, nhanes, pmdata
from .common import PROCESSED


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)

    daily = pd.concat([pmdata.load(), lifesnaps.load(), mmash.load()], ignore_index=True)
    daily["date"] = daily["date"].dt.strftime("%Y-%m-%d")
    daily.to_csv(PROCESSED / "daily.csv", index=False, float_format="%.2f")
    print(f"daily.csv               {len(daily):>6} rows, {daily['person_id'].nunique()} people")
    print(daily.groupby("source_dataset")["person_id"].agg(["count", "nunique"]).to_string())

    blood = inspiration4.load()
    blood.to_csv(PROCESSED / "inspiration4_blood.csv", index=False)
    print(f"inspiration4_blood.csv  {len(blood):>6} rows, {blood['analyte'].nunique()} analytes")

    ref = nhanes.load()
    ref.to_csv(PROCESSED / "nhanes_reference.csv", index=False)
    print(f"nhanes_reference.csv    {len(ref):>6} rows")
    print(ref[["indicator", "n", "p01", "p05", "p50", "p95", "p99"]].to_string(index=False))


if __name__ == "__main__":
    main()
