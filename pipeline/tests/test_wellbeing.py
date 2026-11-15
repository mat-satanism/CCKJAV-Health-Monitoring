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


def test_last_days_features_use_only_the_past():
    f = _table(n_people=2, days=20)
    for c in ["stress", "sleep_quality", "soreness", "sleep_hours"]:
        f[c] = 3.0
    a = wellbeing.add_history(f)
    changed = f.copy()
    future = changed["date"] > "2020-01-10"
    changed.loc[future, ["mood", "fatigue", "readiness"]] = 1.0      # rewrite the future
    b = wellbeing.add_history(changed)
    past = a["date"] <= "2020-01-10"
    cols = [c for c in a.columns if c.endswith(wellbeing.HISTORY)]
    pd.testing.assert_frame_equal(a.loc[past, cols], b.loc[past, cols])
    p0 = a[a["person_id"] == "p1"].iloc[0]
    assert np.isnan(p0["mood_lag1"])                                 # no yesterday borrowed from another person


def test_within_person_auc_ignores_who_is_who():
    people = np.array(["a"] * 4 + ["b"] * 4)
    y = np.array([0, 0, 1, 1, 0, 0, 1, 1])
    s = np.array([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9])          # b always scores higher than a
    assert wellbeing.within_person_auc(people, y, s) == {"a": 1.0, "b": 1.0}


def test_composite_features_use_only_the_past():
    from pipeline import wellbeing_search as ws
    rng = np.random.default_rng(1)
    f = _table(n_people=2, days=40)
    for c in ["stress", "sleep_quality", "soreness", "sleep_hours", "sleep_hours_device", "exercise_min"]:
        f[c] = rng.normal(5, 1, len(f))
    for c in ["mood_z", "fatigue_z", "stress_z", "sleep_hours_device_z"]:
        f[c] = rng.normal(size=len(f))
    a = ws.composites(f, "mood")
    changed = f.copy()
    changed.loc[changed["date"] > "2020-01-20", ["mood", "sleep_hours", "exercise_min", "heart_rate_z"]] = 0.0
    b = ws.composites(changed, "mood")
    past = a["date"] <= "2020-01-20"
    cols = [c for group in ws.COMPOSITE.values() for c in group]
    pd.testing.assert_frame_equal(a.loc[past, cols], b.loc[past, cols])
