"""Build the tidy tables in data/processed/ from data/raw/.

    python -m pipeline.get_data   # once
    python -m pipeline.build

Writes:
    daily.csv               one row per person per day (PMData, LifeSnaps, MMASH)
    features_pmdata.csv     one row per person per calendar day with norm-based features and tomorrow's target
    features_lifesnaps.csv  same for LifeSnaps (see pipeline/features.py)
    demo_mission.csv        30 real days of one person in the backend's Measurement format
    inspiration4_blood.csv  one row per crew member, timepoint and analyte, with lab ranges
    nhanes_reference.csv    population percentiles for blood pressure, pulse and glucose (glucose: without diabetes)
    sim/crew.csv, sim/days.csv, sim/events.csv
                            SYNTHETIC demo crew mission calibrated on real data (docs/simulation.md)
"""
import pandas as pd

from . import demo, features, inspiration4, lifesnaps, mmash, nhanes, pmdata, simulation
from .common import PROCESSED


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)

    daily = pd.concat([pmdata.load(), lifesnaps.load(), mmash.load()], ignore_index=True)
    daily["date"] = daily["date"].dt.strftime("%Y-%m-%d")
    daily.to_csv(PROCESSED / "daily.csv", index=False, float_format="%.2f")
    print(f"daily.csv               {len(daily):>6} rows, {daily['person_id'].nunique()} people")
    print(daily.groupby("source_dataset")["person_id"].agg(["count", "nunique"]).to_string())

    for name, table in features.build_all(daily).items():
        table.to_csv(PROCESSED / name, index=False, float_format="%.3f")
        target = next(c for c in table.columns if c.startswith("target_"))
        usable = table[target].notna()
        print(f"{name:<23} {len(table):>6} calendar days, {table['person_id'].nunique()} people; "
              f"{int(usable.sum())} days with tomorrow's target ({table.loc[usable, 'person_id'].nunique()} people)")

    blood = inspiration4.load()
    blood.to_csv(PROCESSED / "inspiration4_blood.csv", index=False)
    print(f"inspiration4_blood.csv  {len(blood):>6} rows, {blood['analyte'].nunique()} analytes")

    ref = nhanes.load()
    ref.to_csv(PROCESSED / "nhanes_reference.csv", index=False)
    print(f"nhanes_reference.csv    {len(ref):>6} rows")
    print(ref[["indicator", "n", "p01", "p05", "p50", "p95", "p99"]].to_string(index=False))

    demo_rows = demo.demo_mission(daily, nhanes_reference=ref)
    demo_rows.to_csv(PROCESSED / "demo_mission.csv", index=False)
    print(f"demo_mission.csv        {len(demo_rows):>6} rows ({demo.DEMO_PERSON}, from {demo.DEMO_START}; "
          f"{int((demo_rows['source'] == 'synthetic').sum())} synthetic)")

    # Synthetic crew mission, calibrated on daily.csv (PMData) and the NHANES reference above.
    cal = simulation.calibrate(daily, ref)
    crew, days, events = simulation.demo_mission(cal)
    out = PROCESSED / "sim"
    out.mkdir(exist_ok=True)
    crew.to_csv(out / "crew.csv", index=False)
    days.to_csv(out / "days.csv", index=False)
    events.to_csv(out / "events.csv", index=False)
    simulation.demo_tasks().to_csv(out / "tasks.csv", index=False)
    print(f"sim/                    demo mission: {len(crew)} crew, {days['mission_day'].max()} days, {len(events)} events")
    check, _ = simulation.training_missions(cal, 200, seed=7)
    print("synthetic event-free days vs real PMData (median over people):")
    print(simulation.compare_with_real(cal, daily, check).to_string(index=False))


if __name__ == "__main__":
    main()
