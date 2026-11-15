"""The early-warning comparison counts what it says: flags before an event, how early, flags in a calm week."""
import pandas as pd

from pipeline import early_warning as ew


def test_summary_counts_flags_before_events_and_in_calm_weeks():
    days = pd.DataFrame([{"mission_id": "m", "astronaut_id": a, "mission_day": d, "event_free": d <= 15}
                         for a in ("x", "y") for d in range(1, 31)])
    events = pd.DataFrame([{"mission_id": "m", "type": "infection", "who": "x", "onset_day": 20}])
    t = days.set_index(["mission_id", "astronaut_id", "mission_day"])[[]].copy()
    for col in ew.METHODS:
        t[col] = False
    t.loc[("m", "x", 17), "rules"] = True          # 3 days before the start
    t.loc[("m", "y", 12), "rules"] = True          # a calm-week flag for y
    t.loc[("m", "x", 20), "model_3x"] = True       # on the day itself
    out = ew.summary(t.sort_index(), days, events).set_index("method")
    rules, m3, m5 = (out.loc[ew.METHODS[k]] for k in ("rules", "model_3x", "model_5x"))
    assert rules["flagged_before_events"] == 1.0 and rules["median_days_ahead"] == 3
    assert rules["flagged_in_a_calm_week"] == 0.5   # y flagged, x not
    assert m3["median_days_ahead"] == 0 and m3["flagged_in_a_calm_week"] == 0
    assert m5["flagged_before_events"] == 0
