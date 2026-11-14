"""Bayesian personal norm (backend/app/status.py) with the priors from pipeline/norm.py."""
import sys

import pandas as pd

from pipeline import norm
from pipeline.common import ROOT

sys.path.insert(0, str(ROOT / "backend"))
from app.status import classify, predictive


def test_priors_have_every_indicator_with_positive_spreads():
    days = pd.DataFrame({"mission_id": ["m"] * 4, "astronaut_id": ["a", "a", "b", "b"], "mission_day": [1, 2, 1, 2],
                         **{ind: [1.0, 2.0, 5.0, 7.0] for ind in norm.sim.INDICATORS}})
    p = norm.fit_priors(days)
    assert set(p) == set(norm.sim.INDICATORS)
    assert all(v["tau0"] > 0 and v["sigma"] > 0 for v in p.values())


def test_a_steady_person_gets_a_narrow_band_and_a_variable_one_a_wide_band():
    steady = predictive("heart_rate", [50.0, 50.5, 49.5, 50.0, 50.2, 49.8, 50.1, 49.9])
    variable = predictive("heart_rate", [45.0, 55.0, 48.0, 58.0, 44.0, 56.0, 47.0, 57.0])
    assert steady["h95"] < variable["h95"]
    assert abs(steady["center"] - 50) < 1           # a week of data outweighs the population prior (about 60)


def test_no_norm_before_six_days_and_two_days_outside_95_is_yellow():
    assert predictive("heart_rate", [50.0] * 5) is None
    past = [50.0, 50.5, 49.5, 50.0, 50.2, 49.8, 50.1, 49.9]
    p = predictive("heart_rate", past)
    just_out = p["center"] + (p["h95"] + p["h99"]) / 2       # between the 95% and 99% band
    assert classify("heart_rate", just_out, past, population_band=False)["status"] == "green"
    two_days = past + [just_out]
    p2 = predictive("heart_rate", two_days)
    again = p2["center"] + (p2["h95"] + p2["h99"]) / 2
    assert classify("heart_rate", again, two_days, population_band=False)["status"] == "yellow"
