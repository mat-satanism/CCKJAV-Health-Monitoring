"""Tests for the model feature tables: no leakage from the future, honest "tomorrow", people never shared between folds."""
import numpy as np
import pandas as pd
import pytest

from pipeline import features

LOOKS_AHEAD = {"mood_next", "target_worse_mood", "target_neg_emotion"}  # these are allowed to depend on t + 1


def _person(values: dict[int, dict], start="2020-01-01") -> pd.DataFrame:
    """values: {day_number: {column: value}}; days not listed are missing records."""
    first = pd.Timestamp(start)
    rows = [{"date": first + pd.Timedelta(days=d - 1), "person_id": "p", **cols} for d, cols in values.items()]
    return pd.DataFrame(rows)


def _pm(g: pd.DataFrame) -> pd.DataFrame:
    return features.person_features("p", "pmdata", g, ["heart_rate", "mood"], [], features.pmdata_targets)


def test_baseline_uses_only_days_before_today():
    g = _person({d: {"heart_rate": 60.0, "mood": 3.0} for d in range(1, 11)} | {11: {"heart_rate": 100.0, "mood": 3.0}})
    out = _pm(g).set_index("day")
    assert out.loc[11, "heart_rate_base"] == 60.0     # today's spike is not in its own norm
    assert out.loc[11, "heart_rate_dev"] == 40.0


def test_no_norm_without_enough_history():
    g = _person({d: {"heart_rate": 60.0, "mood": 3.0} for d in range(1, 7)})   # 6 days only
    out = _pm(g)
    assert out["heart_rate_base"].isna().all()


def test_changing_the_future_does_not_change_earlier_features():
    rng = np.random.default_rng(0)
    base = {d: {"heart_rate": float(rng.normal(60, 3)), "mood": float(rng.integers(2, 5))} for d in range(1, 31)}
    altered = {d: (dict(v) if d <= 15 else {"heart_rate": 150.0, "mood": 1.0}) for d, v in base.items()}
    a, b = _pm(_person(base)), _pm(_person(altered))
    cols = [c for c in a.columns if c not in LOOKS_AHEAD]
    pd.testing.assert_frame_equal(a.loc[a["day"] <= 15, cols], b.loc[b["day"] <= 15, cols])


def test_tomorrow_is_the_next_calendar_day_not_the_next_record():
    # records on days 1..10, then 12 (day 11 missing): day 10's tomorrow does not exist
    g = _person({d: {"heart_rate": 60.0, "mood": 3.0} for d in range(1, 11)} | {12: {"heart_rate": 60.0, "mood": 1.0}})
    out = _pm(g).set_index("day")
    assert len(out) == 12                      # the gap day is kept as an empty row
    assert pd.isna(out.loc[10, "mood_next"])
    assert pd.isna(out.loc[10, "target_worse_mood"])


def test_worse_mood_target_compares_tomorrow_with_the_persons_usual():
    moods = {d: {"heart_rate": 60.0, "mood": 3.0} for d in range(1, 11)}
    moods[11] = {"heart_rate": 60.0, "mood": 2.0}   # worse than the usual 3
    moods[12] = {"heart_rate": 60.0, "mood": 3.0}   # as usual
    out = _pm(_person(moods)).set_index("day")
    assert out.loc[10, "target_worse_mood"] == 1.0
    assert out.loc[11, "target_worse_mood"] == 0.0


def test_negative_emotion_target_needs_all_three_answers():
    cols = ["emo_sad", "emo_tense", "emo_tired"]
    g = _person({1: dict.fromkeys(cols, 0.0), 2: {"emo_sad": 0.0, "emo_tense": 1.0, "emo_tired": 0.0},
                 3: {"emo_sad": 0.0, "emo_tense": np.nan, "emo_tired": 0.0}, 4: dict.fromkeys(cols, 0.0)})
    out = features.person_features("p", "lifesnaps", g, [], [], features.lifesnaps_targets).set_index("day")
    assert out.loc[1, "target_neg_emotion"] == 1.0    # day 2: tense
    assert pd.isna(out.loc[2, "target_neg_emotion"])  # day 3: one answer missing, so unknown
    assert out.loc[3, "target_neg_emotion"] == 0.0    # day 4: all three answered, none ticked
    assert pd.isna(out.loc[4, "target_neg_emotion"])  # no day 5


def test_folds_are_deterministic_and_balanced():
    people = [f"p{i}" for i in range(16)]
    a, b = features.assign_folds(people), features.assign_folds(list(reversed(people)))
    assert a == b
    sizes = pd.Series(a).value_counts()
    assert set(a) == set(people) and sizes.max() - sizes.min() <= 1 and len(sizes) == features.N_FOLDS


def _daily(n_people=10, days=40) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    rows = []
    for p in range(n_people):
        for d in range(days):
            rows.append({"person_id": f"pm_{p}", "source_dataset": "pmdata",
                         "date": (pd.Timestamp("2020-01-01") + pd.Timedelta(days=d)).strftime("%Y-%m-%d"),
                         "heart_rate": 60.0 if p == 0 else float(rng.normal(60, 3)),   # person 0: flat, spread 0
                         "sleep_hours_device": float(rng.normal(7, 1)), "exercise_min": float(rng.integers(0, 90)),
                         "steps": float(rng.integers(2000, 12000)), "sleep_hours": float(rng.normal(7, 1)),
                         "mood": float(rng.integers(2, 5)), "fatigue": 3.0, "stress": 3.0,
                         "sleep_quality": 3.0, "soreness": 2.0, "readiness": 5.0})
    return pd.DataFrame(rows)


def test_each_person_is_in_exactly_one_fold_and_z_scores_are_finite():
    f = features.build_dataset(_daily(), "pmdata", features.PMDATA_FEATURES, features.PMDATA_PLAIN,
                               features.pmdata_targets)
    assert (f.groupby("person_id")["fold"].nunique() == 1).all()
    assert f["is_test"].eq(f["fold"] == features.TEST_FOLD).all()
    z = f[[c for c in f.columns if c.endswith("_z")]]
    assert not np.isinf(z.to_numpy(dtype=float)).any()          # a flat series does not divide by zero
    assert f.loc[f["person_id"] == "pm_0", "heart_rate_z"].dropna().abs().max() == pytest.approx(0.0)
