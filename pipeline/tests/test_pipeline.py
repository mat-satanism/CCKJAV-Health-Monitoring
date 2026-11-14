"""Unit tests on tiny hand-made inputs: no downloaded data needed."""
import numpy as np
import pandas as pd
import pytest

from pipeline import inspiration4, lifesnaps, nhanes, pmdata
from pipeline.common import DAILY_COLUMNS, finish_daily


def test_wellness_keeps_last_answer_per_local_day():
    raw = pd.DataFrame({
        # 23:30 UTC on 1 Nov is already 2 Nov in Oslo.
        "effective_time_frame": ["2019-11-01T08:00:00Z", "2019-11-01T23:30:00Z", "2019-11-02T09:00:00Z"],
        "mood": [3, 1, 4], "fatigue": [3, 3, 3], "stress": [3, 3, 3], "sleep_quality": [3, 3, 3],
        "readiness": [5, 5, 5], "soreness": [2, 2, 2], "sleep_duration_h": [7, 6, 8],
    })
    out = pmdata.wellness(raw)
    assert out["date"].dt.strftime("%Y-%m-%d").tolist() == ["2019-11-01", "2019-11-02"]
    assert out["mood"].tolist() == [3, 4]  # the 9:00 answer replaced the 23:30 one


def test_resting_heart_rate_drops_zero():
    rec = [{"dateTime": "2019-11-01 00:00:00", "value": {"value": 0}},
           {"dateTime": "2019-11-02 00:00:00", "value": {"value": 55.5}}]
    assert pmdata.resting_heart_rate(rec)["heart_rate"].tolist() == [55.5]


def test_main_sleep_skips_naps():
    rec = [{"dateOfSleep": "2019-11-02", "minutesAsleep": 420, "mainSleep": True},
           {"dateOfSleep": "2019-11-02", "minutesAsleep": 30, "mainSleep": False}]
    assert pmdata.main_sleep(rec)["sleep_hours_device"].tolist() == [7.0]


def test_finish_daily_drops_impossible_values_and_counts_days():
    df = pd.DataFrame({
        "person_id": ["a", "a"],
        "date": pd.to_datetime(["2020-01-01", "2020-01-03"]),
        "mood": [0, 4], "sleep_hours_device": [24.4, 7.0],
    })
    out = finish_daily(df, "test")
    assert list(out.columns) == DAILY_COLUMNS
    assert out["day"].tolist() == [1, 3]
    assert out["mood"].isna().tolist() == [True, False]
    assert out["sleep_hours_device"].isna().tolist() == [True, False]


def test_lifesnaps_zero_sleep_is_missing_and_exercise_sums():
    raw = pd.DataFrame({
        "id": ["x", "x"], "date": ["2021-05-01", "2021-05-02"], "resting_hr": [60, 61],
        "minutesAsleep": [0, 420], "moderately_active_minutes": [10, np.nan],
        "very_active_minutes": [5, np.nan], "steps": [1000, 2000],
        "nightly_temperature": [33.5, 33.9], "stress_score": [70, 75],
    })
    out = lifesnaps.tidy(raw)
    assert out["sleep_hours_device"].isna().tolist() == [True, False]
    assert out["exercise_min"].tolist()[0] == 15
    assert pd.isna(out["exercise_min"].tolist()[1])


@pytest.mark.parametrize("name, crew, timepoint, days, phase", [
    ("C001_serum_L-3", "C001", "L-3", -3, "pre-flight"),
    ("C004_whole-blood_R+194_cbc", "C004", "R+194", 194, "post-flight"),
])
def test_parse_sample(name, crew, timepoint, days, phase):
    assert inspiration4.parse_sample(name) == {
        "crew_id": crew, "timepoint": timepoint, "days_from_flight": days, "phase": phase}


def test_inspiration4_columns_units_and_flags():
    raw = pd.DataFrame({
        "Sample Name": ["C001_serum_L-3"],
        "glucose_value_milligram_per_deciliter": [40],
        "glucose_range_min_milligram_per_deciliter": [65],
        "glucose_range_max_milligram_per_deciliter": [99],
        "alt_value_units_per_liter": [20],
        "alt_range_min_units_per_liter": [6],
        "alt_max_units_per_liter": [29],          # ALT/AST spell max without "range_"
        "hemoglobin_value_percent": [14.0],       # really g/dL
        "hemoglobin_range_min_percent": [13.2],
        "hemoglobin_range_max_percent": [17.1],
        "egfr_value_ml": [90], "egfr_range_min_ml": [60], "egfr_range_max_ml": ["N/A"],
    })
    out = inspiration4.tidy(raw, "cmp").set_index("analyte")
    assert out.loc["glucose", "flag"] == "low"
    assert out.loc["alt", "ref_max"] == 29
    assert out.loc["hemoglobin", "unit"] == "gram_per_deciliter"
    assert pd.isna(out.loc["egfr", "ref_max"])


def test_weighted_percentiles_equal_weights_match_median():
    values = [1, 2, 3, 4, 5]
    assert nhanes.weighted_percentiles(values, [1] * 5, [50]) == [3.0]


def test_weighted_percentiles_follow_weights():
    # The value 10 carries almost all the weight, so the median sits next to 10
    # (interpolated between the weight midpoints of 1 and 10).
    assert nhanes.weighted_percentiles([1, 10], [1, 99], [50])[0] == pytest.approx(9.91)
