"""Tests for the real-data wellbeing forecast: honest targets, people never scored by a model that saw them."""
import numpy as np
import pandas as pd

from pipeline import wellbeing


def _table(n_people=10, days=40, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_people):
        for d in range(days):
            rows.append({"person_id": f"p{p}", "date": f"2020-01-{1 + d:02d}" if d < 31 else f"2020-02-{d - 30:02d}",
                         "dow": d % 7, "fold": p % 5,
                         "mood": float(rng.integers(1, 6)), "fatigue": float(rng.integers(1, 6)),
                         "readiness": float(rng.integers(0, 11)), "heart_rate_z": rng.normal()})
    return pd.DataFrame(rows)


def test_target_is_tomorrow_below_usual():
    f = _table(n_people=1, days=20)
    f["mood"] = 4.0
    f.loc[15, "mood"] = 2.0                       # day 16 is a bad day
    out = wellbeing.add_pmdata_targets(f)
    assert out.loc[14, "y_mood"] == 1.0            # predicted from day 15: tomorrow is worse
    assert out.loc[15, "y_mood"] == 0.0            # back to usual the day after
    assert out.loc[15, "ref_mood"] == 2.0          # today 2 below usual: "same as today" says worse
    assert out.loc[:5, "y_mood"].isna().all()      # no usual level yet (fewer than 7 days)


def test_targets_do_not_cross_people():
    f = _table(n_people=2, days=20)
    out = wellbeing.add_pmdata_targets(f)
    last = out.groupby("person_id").tail(1)
    assert last["y_mood"].isna().all()             # the last day has no tomorrow, not the next person's day 1


def test_each_person_is_scored_by_a_model_that_never_saw_them():
    f = wellbeing.add_pmdata_targets(_table())
    d = f[f["y_mood"].notna()].reset_index(drop=True)
    cols = ["heart_rate_z", "ref_mood"]
    a = wellbeing.out_of_person_scores(d, cols, "y_mood")
    flipped = d.copy()
    held = flipped["fold"] == 0
    flipped.loc[held, "y_mood"] = 1 - flipped.loc[held, "y_mood"]   # change the answers of fold 0 only
    b = wellbeing.out_of_person_scores(flipped, cols, "y_mood")
    for name in a:
        np.testing.assert_allclose(a[name][held], b[name][held])   # fold 0's own labels never reached its model


def test_check_in_only_drops_every_wearable_input():
    cols = wellbeing.feature_columns("pmdata", wellbeing.add_pmdata_targets(_table()).assign(
        **{c: 0.0 for c in ["steps_z", "steps_dev3", "mood_z", "sleep_hours_z", "sleep_hours_device_z", "weekend"]}))
    kept = wellbeing.check_in_only(cols)
    assert "steps_z" not in kept and "heart_rate_z" not in kept and "sleep_hours_device_z" not in kept
    assert "mood_z" in kept and "sleep_hours_z" in kept   # self-reported sleep stays
