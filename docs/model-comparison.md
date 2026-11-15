# Which risk model and why (2026-11-14)

Mentors suggested replacing logistic regression with tree models (LightGBM or random forest) and explaining
each decision with SHAP. We compared all three on the same data: `python -m pipeline.compare_models`.

**Setup.** Train: 400 simulated missions (seed 7). Test: 100 new simulated missions (seed 1234), never seen in
training. Same 33 features for every model. An alert = the 5% riskiest astronaut-days.

- ROC AUC: how well the model puts risky days above calm ones (0.5 = guessing, 1 = perfect).
- PR AUC: the same, focused on the rare event days (better than accuracy when events are 2-3% of days).
- Precision: share of alerts that were real. Recall: share of real events that got an alert. F1: balance of both.

## On new simulated missions (mean over 5 events)

| Model | ROC AUC | PR AUC | Precision | Recall | F1 | Training time |
|---|---|---|---|---|---|---|
| Logistic regression | 0.857 | 0.152 | 0.158 | 0.369 | 0.220 | under 1 s |
| Random forest | 0.874 | 0.219 | 0.168 | 0.396 | 0.235 | 16 s |
| LightGBM | 0.875 | 0.229 | 0.176 | 0.418 | 0.247 | 6 s |

Trees win mostly on infection (ROC AUC 0.89 logistic, 0.95 forest, 0.96 LightGBM) and deconditioning. On
sleep disruption, low mood and CO2 all three are about the same; logistic regression is slightly best on CO2.

## On real people (PMData, 16 people, 1517 days)

Target: "tomorrow's mood is worse than usual". Reference "same as today": AUC 0.644.
The 95% interval comes from resampling people (300 times).

| Model (low_mood risk) | AUC | 95% interval |
|---|---|---|
| Logistic regression | 0.530 | 0.419-0.642 |
| Random forest | 0.660 | 0.625-0.689 |
| LightGBM | 0.567 | 0.471-0.666 |

## Decision: random forest

On the simulation the forest and LightGBM are practically tied (F1 0.235 vs 0.247). On real people only the
forest stays at the level of the simple reference, and its result is the most stable across people; LightGBM
varies a lot. For a health tool we prefer the model that is more robust, not the one that is 1 point better on
our own simulated data. The forest is also explained exactly by SHAP (TreeExplainer).

Honest limits: no model here beats "same as today" on real mood; the forest only matches it. All event labels
come from our simulator, so the numbers show the approach, not real medical skill.

Update (same day): after adding heart rate variability and reaction time (8 more features) the forest scores
0.632 on real mood (PMData has neither, so they count as 0); the comparison above was run before that.

Update 2026-11-15, inputs against the Bayesian norm (same as the app's statuses): mean over events, ROC AUC /
PR AUC / F1: logistic 0.873 / 0.186 / 0.244, forest 0.878 / 0.253 / 0.261, LightGBM 0.887 / 0.273 / 0.278.
LightGBM is still slightly ahead on the simulation. On real mood all three are at or below guessing (forest 0.565,
LightGBM 0.500, logistic 0.479): the earlier 0.632-0.660 was mostly a shared median definition of target and
inputs, see `docs/personal-norm.md`. The forest stays: exact SHAP, and nothing here is judged on real mood any more
(that is the wellbeing model's job, trained on real people).

Not tried yet: Cox time-to-event models (postponed). Bayesian personal norms: done, see above.
