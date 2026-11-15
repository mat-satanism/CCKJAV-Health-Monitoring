"""The place changes the hazards; Mars base stays exactly the original mission."""
import pandas as pd
import pytest

from pipeline import simulation as sim
from pipeline.common import PROCESSED


def test_mars_base_has_no_factors_and_scaling_by_one_is_identity():
    assert sim.ENVIRONMENTS["mars_base"] == {"rate": {}, "effect": {}}
    effect = sim.EVENTS["infection"]["episode_effect"]
    assert sim.scaled_effect(effect, 1) is effect


def test_stronger_effect_scales_deltas_and_the_lost_exercise():
    e = sim.scaled_effect({"bp_sys": -8.0, "exercise_factor": 0.6}, 1.5)
    assert e["bp_sys"] == -12.0
    assert e["exercise_factor"] == pytest.approx(0.4)          # loses 40% x 1.5 = 60% of the exercise
    assert sim.scaled_effect({"exercise_factor": 0.1}, 2.0)["exercise_factor"] == 0.0   # never below zero


def test_every_place_has_a_demo_story_with_johns_infection():
    assert set(sim.DEMO_EVENTS_BY_ENV) == set(sim.ENVIRONMENTS)
    for env, events in sim.DEMO_EVENTS_BY_ENV.items():
        story = events or sim.DEMO_EVENTS
        assert ("infection", "john", 18, 4) in story, env
        for etype, _, onset, _ in story:
            assert onset - sim.EVENTS[etype]["prodrome"] > sim.EVENT_FREE_DAYS, (env, etype)


@pytest.mark.skipif(not (PROCESSED / "sim" / "days.csv").exists(), reason="run python -m pipeline.build first")
def test_mars_demo_is_unchanged_by_the_places(tmp_path):
    cal = sim.calibrate(pd.read_csv(PROCESSED / "daily.csv"), pd.read_csv(PROCESSED / "nhanes_reference.csv"))
    _, days, _ = sim.demo_mission(cal, "mars_base")
    days.to_csv(tmp_path / "days.csv", index=False)          # compare as written, like pipeline.build does
    pd.testing.assert_frame_equal(pd.read_csv(tmp_path / "days.csv"), pd.read_csv(PROCESSED / "sim" / "days.csv"))
