"""The app's chart forecast: settings in the code are the ones fitted on real people, and it beats 'same as today'."""
from pipeline import forecast_eval as fe
from pipeline.features import TEST_FOLD, assign_folds


def _origins():
    data = fe.series()
    folds = assign_folds(sorted({p for _, p, _ in data}))
    o = fe.origins(data)
    return o, o["person"].map(folds).eq(TEST_FOLD)


def test_code_settings_match_the_fit_on_training_people():
    o, is_test = _origins()
    assert fe.fit(o[~is_test]) == fe.analytics.FORECAST


def test_new_forecast_beats_same_as_today_and_the_old_line_on_new_people():
    o, is_test = _origins()
    rel, cover = fe.score(o[is_test].reset_index(drop=True))
    row = rel.loc["ALL (mean of indicators)"]
    assert row["back to own norm (new)"] < 0.9
    assert row["current (straight line)"] > 1.0          # the old line was worse than repeating today
    assert (rel["back to own norm (new)"].drop("ALL (mean of indicators)") < 1).all()
    assert cover.between(0.7, 0.9).all()           # an 80% band holds about 80% of real values
