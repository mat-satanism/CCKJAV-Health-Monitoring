"""Tests for the crew simulator. Uses the committed data/processed tables for calibration."""
from itertools import pairwise

import pandas as pd
import pytest

from pipeline import simulation as sim
from pipeline.common import PROCESSED


@pytest.fixture(scope="module")
def cal():
    return sim.calibrate(pd.read_csv(PROCESSED / "daily.csv"), pd.read_csv(PROCESSED / "nhanes_reference.csv"))


@pytest.fixture(scope="module")
def demo(cal):
    return sim.demo_mission(cal)


def test_same_seed_gives_the_same_mission(cal):
    a, _ = sim.training_missions(cal, 3, seed=11)
    b, _ = sim.training_missions(cal, 3, seed=11)
    pd.testing.assert_frame_equal(a, b)


def test_demo_crew_is_calibrated_on_real_people(cal, demo):
    crew, _, _ = demo
    assert set(crew["calibrated_from"]) <= set(cal.pool)
    assert "medical" in crew.set_index("astronaut_id").loc["amara", "skills"]


def test_everything_is_labelled_synthetic(demo):
    _, days, _ = demo
    assert (days["source"] == "synthetic").all()


def test_first_15_days_are_event_free(cal):
    days, events = sim.training_missions(cal, 50, seed=3)
    assert days.loc[days["mission_day"] <= sim.EVENT_FREE_DAYS, "event_free"].all()
    assert (events["prodrome_start"] > sim.EVENT_FREE_DAYS).all()


def test_label_marks_the_two_days_before_onset(demo):
    _, days, _ = demo
    john = days[days["astronaut_id"] == "john"].set_index("mission_day")["label_infection_48h"]
    assert john.loc[[16, 17]].tolist() == [1, 1]          # infection starts on day 18
    assert john.loc[[15, 18, 19]].tolist() == [0, 0, 0]


def test_early_signs_come_before_the_fever(demo):
    _, days, _ = demo
    john = days[days["astronaut_id"] == "john"].set_index("mission_day")
    calm = john.loc[1:15]
    assert john.loc[16:17, "temp"].mean() > calm["temp"].mean()
    assert john.loc[16:17, "heart_rate"].mean() > calm["heart_rate"].mean()
    assert john.loc[18, "temp"] >= 38.0 and "fever" in john.loc[18, "symptoms"]


def test_crew_event_hits_everyone(demo):
    _, days, _ = demo
    day25 = days[days["mission_day"] == 25]
    assert day25["symptoms"].str.contains("headache").all()


def test_values_stay_in_plausible_ranges(cal):
    days, _ = sim.training_missions(cal, 50, seed=5)
    assert days["mood"].between(1, 5).all()
    assert days["sleep_hours"].between(1, 13).all()
    assert days["exercise_min"].ge(0).all()
    assert days["temp"].between(34, 41).all()
    assert days["heart_rate"].between(30, 130).all()


def test_synthetic_normal_days_look_like_real_people(cal):
    days, _ = sim.training_missions(cal, 200, seed=7)
    cmp = sim.compare_with_real(cal, pd.read_csv(PROCESSED / "daily.csv"), days).set_index("indicator")
    for ind in sim.FROM_PMDATA:
        assert cmp.loc[ind, "sim_mean"] == pytest.approx(cmp.loc[ind, "real_mean"], rel=0.1)
        assert cmp.loc[ind, "sim_spread"] == pytest.approx(cmp.loc[ind, "real_spread"], rel=0.35)


def test_every_crew_member_has_a_weekly_private_medical_conference():
    tasks = sim.demo_tasks()
    pmc = tasks[tasks["kind"] == "pmc"]
    for member in sim.DEMO_CREW:
        days = pmc.loc[pmc["assignee"] == member["astronaut_id"], "mission_day"].tolist()
        assert days and all(b - a == 7 for a, b in pairwise(days))
