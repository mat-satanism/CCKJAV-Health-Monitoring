# Wellbeing forecast on real people (2026-11-15)

The team's main ML task: from today's wearable data and morning check-in, predict that tomorrow will be a worse
day than usual. Unlike the risk model (`docs/model-comparison.md`), which learns on our simulated crew, this one
learns and is scored **only on real people**. Run: `python -m pipeline.wellbeing` (about 1 minute).

## Setup

- **Data.** PMData: 16 people, about 1300 days with an answer. LifeSnaps: 58 people, 2013 days.
- **Targets.** PMData: tomorrow's mood, fatigue or readiness is below the person's usual (median of the last 14
  days). All PMData scales go "higher = better" (fatigue 5 = fresh). LifeSnaps: tomorrow the person ticked sad,
  tense or tired.
- **Inputs.** For each signal: today's distance from the person's own norm (`_z`) and the 3-day average
  (`_dev3`). PMData signals: resting pulse, sleep (band and self-report), exercise, steps, mood, fatigue, stress,
  plus sleep quality, soreness and readiness. LifeSnaps: pulse, sleep, exercise, steps, stress score, skin
  temperature, today's feelings. Plus a weekend flag.
- **Honest check.** Each person is scored by a model trained on other people only (5 folds by person). The
  reference is "same as today": how far below their usual the person is today. Both 95% intervals come from
  resampling whole people (1000 times), not days.
- **Models.** Logistic regression and random forest (300 trees, leaves of 20+ days), the same family the app
  already uses. "Check-in only" is the forest without any wristband input.

## Results

AUC: 0.5 = guessing, 1 = perfect. "vs reference" is the 95% interval of the model's AUC minus the reference's.
An interval entirely above 0 means the model is better on people it has never seen.

| Target | Same as today | Logistic regression | Random forest | Forest, check-in only |
|---|---|---|---|---|
| Worse mood (PMData) | 0.611 | 0.548 (−0.109..−0.023) | 0.674 (**+0.023..+0.098**) | **0.696 (+0.051..+0.125)** |
| More tired (PMData) | 0.613 | 0.593 (−0.050..+0.012) | 0.638 (**+0.004..+0.054**) | 0.642 (−0.002..+0.068) |
| Less ready (PMData) | 0.621 | 0.611 (−0.068..+0.044) | 0.619 (−0.046..+0.034) | 0.602 (−0.062..+0.020) |
| Negative feeling (LifeSnaps) | 0.609 | 0.605 (−0.025..+0.016) | 0.586 (−0.048..+0.001) | 0.606 (−0.018..+0.016) |

What moves the forest most (mean |SHAP|): for mood, how far below usual mood is today and over 3 days, then stress
over 3 days; for fatigue, today's fatigue and readiness, then steps; for readiness, today's readiness and steps;
for LifeSnaps, today's feelings dominate.

## What this means

- **Mood tomorrow can be predicted better than "same as today"** on people the model never saw: AUC 0.67-0.70
  against 0.61. This is the first real-data result in the project that beats the simple reference, not just
  matches it. For fatigue the gain is small and borderline; readiness and LifeSnaps feelings are not predictable
  beyond "same as today".
- **The wristband adds nothing on top of the questionnaire** in these data: the forest without wearable inputs is
  as good or slightly better. The useful signal is the person's own recent answers, read against their own norm.
  For the app this argues for a short daily check-in, not only passive sensors.
- **Logistic regression is worse than the reference on mood.** The pattern is not linear: what matters is a
  drop against the person's norm combined with a few days' history, which trees pick up and a straight line
  does not.

## Limits

- 16 PMData people is few; the intervals are wide and the mood and fatigue gains come from one dataset.
- Eight comparisons were made (4 targets × 2 models); a single interval just above 0 (fatigue) can be luck.
- These are healthy people on Earth, not astronauts; the targets are self-reported feelings, not medical events.
- Not yet connected to the app: the next step is to show "tomorrow may be harder" in the real-data check-in demo
  with the SHAP reasons, marked as a forecast.
