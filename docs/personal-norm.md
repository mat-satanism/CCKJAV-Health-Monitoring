# Personal norm: Bayesian, not a fixed median (2026-11-14)

A mentor suggested a Bayesian mixed-effects model: start from what is typical for people (a prior), learn
each astronaut's own baseline in the first days of the mission, and alert when a value falls outside the
person's own prediction band. We built the simple core of that idea; the code is `backend/app/status.py`
(one rule for the whole app) and `pipeline/norm.py` (priors and comparison).

## How it works, in plain words

1. **Prior: what is typical for people.** For each indicator: the average level, how much people differ from
   each other, and how much one person's days usually vary. Taken from the calm days of 400 simulated missions,
   which are calibrated on real people (PMData, LifeSnaps, NHANES). File: `models/norm_priors.json`.
2. **Calibration: the first 6 days.** With fewer than 6 days of the person's own data there is no personal norm:
   the crew mission shows "Learning this person's norm", and only safety limits (red) can fire.
3. **Daily update.** From then on, each day the model combines the prior with the person's last 14 values.
   Both the person's level and their own day-to-day spread are learned (Normal-Inverse-Gamma model), so a steady
   person gets a narrow band and a variable person a wide one. The prediction for today is a band where 95%
   (and 99%) of the person's values should fall if nothing has changed.
4. **Alerts.**
   - yellow: outside the 99% band, or outside the 95% band two days in a row;
   - green with "check again tomorrow": just outside 95% once;
   - red: only safety limits (`data/thresholds.json`). The mentor's concept also makes "outside 99%" red; we
     keep it yellow, because in this app red takes someone off heavy tasks and should be a measured fact.

## Comparison with the old rule

Old rule: median of the last 14 days, yellow at 3 or more spreads (with a minimum spread per indicator).
Test: 30 new simulated missions (seed 1234), 218 events, statuses exactly as the crew mission shows them.

| Rule | Calm days with any yellow | Events with a yellow from the early signs to the first day |
|---|---|---|
| Median, 3 spreads (old) | 13.8% | 87.6% |
| Bayesian norm (new) | 17.2% | 93.1% |

Per indicator the Bayesian rule flags 1-3% of calm days, which is what a 99% band plus "two days outside
95%" should give; with 10 indicators that adds up to about 1 calm day in 6 for a person. **Trade-off:** it
catches more events early and says how sure it is (the band), at the cost of a few more yellows on calm days.
Yellow only asks to re-measure or look closer, so we accept that. Run: `python -m pipeline.norm`.

## Not done from the mentor's concept

- Age, sex and measurement context (time of test, exercise, meals, medication) as model inputs: the
  simulation has no such variation yet, so they would add nothing to learn from.
- A gradual mission-time trend f(t) and exposure effects (gravity, radiation): one crew in one environment
  cannot separate them from other changes (the concept itself says so).
- Separate norms at rest and during exercise: needs several readings a day; we have one daily value.

## The models read the same norm (2026-11-15)

Until now only the statuses used the Bayesian norm; both models measured "unusual" against the old 14-day
median. Now the risk model (`pipeline/model.py`, `NORM = "bayes"`) and the wellbeing forecast
(`pipeline/wellbeing.py`) take each signal as its distance from the Bayesian norm, in the person's predictive
scale (`pipeline/bayes_features.py`, same formulas as `status.predictive`, tested). Priors: the app's own for its
indicators; for check-in answers the app does not have (fatigue, stress) and LifeSnaps signals, fitted on training
people only.

**Wellbeing forecast, real people**, AUC within a person (mean of 3 splits of people; the comparison keeps every
other input the same):

| Tomorrow | Same as today | Median-norm inputs | Bayesian-norm inputs |
|---|---|---|---|
| Worse mood | 0.608 | 0.679 | **0.686** |
| Less energy | 0.590 | 0.640 | **0.649** |
| Less ready | 0.627 | 0.644 | 0.642 |
| Negative feeling (LifeSnaps) | 0.530 | 0.531 | **0.550** |

Not worse anywhere, slightly better on three of four (within the noise).

**Risk model, 100 new simulated missions** (mean over 5 events): ROC AUC 0.875 → 0.878, PR AUC 0.221 → 0.253,
events caught in the top 5% riskiest days 40.7% → 44.3%, precision 17.3% → 18.6%. The gain is mostly
deconditioning (caught 54% → 71%). The demo story holds: John's infection risk is 22× usual on day 16, two days
before the fever; Maria's sleep risk rises on days 19-20 before day 21.

**Risk model on real mood: an honest correction.** The sim-trained forest scored 0.632 on real PMData mood, close
to "same as today" (0.644). With Bayesian inputs it scores 0.565. The reason is the target: "worse than usual"
was defined against the same 14-day median as the old inputs, which flatters median inputs. Defined the way the
app sees "usual" (the Bayesian centre), the old forest scores **0.438** and the new one **0.504**, against 0.653 for
"same as today". So the simulation-trained model does not carry over to real mood under either norm; the earlier
"on par with the reference" was mostly the shared definition. Real-data forecasting is the wellbeing model's job
(`docs/wellbeing-model.md`), which is trained on real people.

## Still open from the mentor's concept

- Personal priors per astronaut from pre-flight data (we use one population prior per indicator).
