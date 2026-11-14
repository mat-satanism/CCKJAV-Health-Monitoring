"""Tests for the risk model. Trains on a small set of simulated missions to stay fast."""
import json

import numpy as np
import pandas as pd
import pytest

from pipeline import model as M
from pipeline import simulation as sim
from pipeline.common import PROCESSED


@pytest.fixture(scope="module")
def cal():
    return sim.calibrate(pd.read_csv(PROCESSED / "daily.csv"), pd.read_csv(PROCESSED / "nhanes_reference.csv"))


@pytest.fixture(scope="module")
def trained(cal):
    train_days, _ = sim.training_missions(cal, 150, seed=21)
    return M.train(train_days)          # (settings, forests)


def test_features_do_not_look_into_the_future(cal):
    days, _ = sim.training_missions(cal, 2, seed=3)
    changed = days.copy()
    later = changed["mission_day"] > 20
    changed.loc[later, ["heart_rate", "temp", "sleep_hours"]] += [30, 2, -5]
    a, _ = M.sim_features(days, floors={i: 1.0 for i in sim.INDICATORS})
    b, _ = M.sim_features(changed, floors={i: 1.0 for i in sim.INDICATORS})
    early = a["mission_day"] <= 20
    cols = [c for c in M.feature_columns() if not c.startswith("crew_")]
    pd.testing.assert_frame_equal(a.loc[early, cols], b.loc[early, cols])


def test_risks_are_probabilities_and_settings_are_plain_json(trained, cal):
    settings, forests = trained
    days, _ = sim.training_missions(cal, 3, seed=8)
    d, _ = M.sim_features(days, settings["floors"])
    probs, contrib = M.risk(forests, d)
    assert probs.to_numpy().min() >= 0 and probs.to_numpy().max() <= 1
    assert json.loads(json.dumps(settings)) == settings
    # SHAP: the usual risk plus the contributions add up to the prediction
    for event, forest in forests.items():
        expected = float(np.ravel(M.shap.TreeExplainer(forest).expected_value)[1])
        np.testing.assert_allclose(expected + contrib[event].sum(axis=1), probs[f"risk_{event}"], atol=1e-6)


def test_model_beats_the_simple_rule_on_new_missions(trained, cal):
    test_days, _ = sim.training_missions(cal, 60, seed=999)
    scores = M.evaluate(*trained, test_days)
    assert (scores["auc_model"] > scores["auc_rule_max_z"]).all()
    assert (scores["auc_model"] > 0.7).all()


def test_demo_warns_about_johns_infection_before_the_fever(trained, cal):
    _, demo_days, _ = sim.demo_mission(cal)
    pred = M.predict_demo(*trained, demo_days)
    john = pred[pred["astronaut_id"] == "john"].set_index("mission_day")
    assert john.loc[16, "risk_infection"] > john.loc[1:15, "risk_infection"].max()
    assert "Resting pulse" in john.loc[16, "signs_infection"]


def test_signs_only_list_features_that_push_risk_up(trained, cal):
    _, demo_days, _ = sim.demo_mission(cal)
    settings, forests = trained
    d, _ = M.sim_features(demo_days, settings["floors"])
    _, contrib = M.risk(forests, d)
    signs = M.explain(settings, d, contrib)
    quiet = np.where(contrib["infection"].max(axis=1) < M.MIN_SIGN)[0]
    assert (signs["signs_infection"].iloc[quiet] == "").all()
