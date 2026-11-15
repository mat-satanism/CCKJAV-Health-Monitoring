"""Analytics used on the pitch charts."""
import pandas as pd

from pipeline import pitch_charts as pc


def test_within_person_effect_ignores_who_is_moody_in_general():
    # A is often in a bad mood and often stressed; B rarely either. Within each person the sign changes nothing.
    a = pd.DataFrame({"person_id": "a", "sign": [True] * 8 + [False] * 8, "y_mood": [1, 1, 1, 1, 0, 0, 0, 0] * 2})
    b = pd.DataFrame({"person_id": "b", "sign": [True] * 6 + [False] * 18, "y_mood": [1, 0, 0, 0, 0, 0] * 4})
    d = pd.concat([a, b], ignore_index=True)
    pooled = d.loc[d["sign"], "y_mood"].mean() - d.loc[~d["sign"], "y_mood"].mean()
    r = pc.within_person(d, d["sign"])
    assert pooled > 0.05                      # pooling makes the sign look meaningful (+9 points here)
    assert abs(r["effect"]) < 1e-9 and r["people"] == 2


def test_completeness_table_has_every_person_and_shares_between_0_and_1():
    table, best = pc.completeness()
    cols = [c for c, _ in pc.COMPLETENESS]
    assert table[cols].min().min() >= 0 and table[cols].max().max() <= 1
    assert "pm_p06" in best["person_id"].head(3).tolist()
