# Wellbeing forecast on real people (2026-11-15)

The team's main ML task: from today's wearable data and morning check-in, predict that tomorrow will be a worse
day than usual. Unlike the risk model (`docs/model-comparison.md`), which learns on our simulated crew, this one
learns and is scored **only on real people**. Run: `python -m pipeline.wellbeing` (about 2 minutes).

## Setup

- **Data.** PMData: 16 people, about 1300 days with an answer. LifeSnaps: 58 people, 2013 days.
- **Targets.** PMData: tomorrow's mood, fatigue or readiness is below the person's usual (median of the last 14
  days). All PMData scales go "higher = better" (fatigue 5 = fresh). LifeSnaps: tomorrow the person ticked sad,
  tense or tired.
- **Inputs.** For each signal: today's distance from the person's own norm (`_z`) and the 3-day average
  (`_dev3`). PMData signals: resting pulse, sleep (band and self-report), exercise, steps, mood, fatigue, stress,
  plus sleep quality, soreness and readiness. LifeSnaps: pulse, sleep, exercise, steps, stress score, skin
  temperature, today's feelings. Plus a weekend flag.
  "Last days" adds, for each check-in answer: yesterday's value, the change since yesterday and the worst of the
  last 3 days.
- **Honest check.** Each person is scored by a model trained on other people only (5 folds by person). The
  reference is "same as today": how far below their usual the person is today. Intervals come from resampling
  whole people (1000 times), not days.
- **Models.** Logistic regression and random forest (300 trees, leaves of 20+ days), the same family the app
  already uses. "Check-in only" is the forest without any wristband input.

## Two ways to score, and why the second one matters

- **Pooled AUC**: all days of all people in one ranking. It rewards a model that only learns *who* has many bad
  days (a moody person versus a calm one).
- **Within-person AUC**: the AUC inside each person, averaged. It answers the question an astronaut has: *is
  tomorrow a bad day for me?* This is the main score below.

## Results

AUC: 0.5 = guessing, 1 = perfect. In brackets: 95% interval of the model minus the reference, within person.
An interval entirely above 0 means the model beats "same as today" on people it has never seen.

| Target | Same as today | Random forest (all inputs) | Forest, check-in only | Forest, check-in + last days |
|---|---|---|---|---|
| Worse mood (PMData) | 0.608 | 0.658 (+0.016..+0.087) | 0.647 (−0.001..+0.093) | **0.681 (+0.038..+0.115)** |
| More tired (PMData) | 0.590 | **0.644 (+0.008..+0.118)** | 0.615 (−0.008..+0.064) | 0.617 (−0.020..+0.083) |
| Less ready (PMData) | 0.627 | 0.645 (−0.019..+0.051) | 0.632 (−0.039..+0.050) | 0.610 (−0.056..+0.017) |
| Negative feeling (LifeSnaps) | 0.530 | 0.531 (−0.039..+0.040) | 0.543 (−0.007..+0.036) | not built |

Logistic regression is never better than the reference (mood 0.580, fatigue 0.608, readiness 0.609).
Pooled AUC for the best mood model is 0.705 against 0.611; full table: `python -m pipeline.wellbeing`.

What moves the forest most (mean |SHAP|): for mood, how far below usual mood is today and over 3 days, then stress
over 3 days; for fatigue, today's fatigue and readiness, then steps; for readiness, today's readiness and steps;
for LifeSnaps, today's feelings dominate.

## What we tried and left out

Scored on three different splits of people (seeds 42, 1, 2) before choosing:

| Idea | Pooled AUC, mood | Within-person AUC, mood | Kept? |
|---|---|---|---|
| How jumpy the person usually is (14-day spread of each answer) | 0.69 → 0.73 | no gain | no: it tells people apart, not days |
| Share of the person's bad days so far | 0.69 → 0.71 | no gain | no, same reason |
| 7-day slope of each answer | no gain | — | no |
| Gradient boosting (HistGradientBoosting) instead of the forest | 0.02-0.04 lower | — | no |
| Forest with leaves of 10 or 40, class weights, extra trees | within ±0.01, extra trees worse | — | no, keep leaves of 20 |
| Last days (yesterday, change since yesterday, worst of 3 days) | +0.01 | +0.03 | **yes, for mood** |

The first two ideas are the lesson: they lift the headline number by 0.04 and change nothing for one person.

## What this means

- **A worse mood tomorrow can be predicted better than "same as today" for the same person**: within-person AUC
  0.68 against 0.61, interval entirely above 0, on people the model never saw. It is the first real-data result
  in the project that beats the simple reference instead of matching it.
- **Fatigue**: the forest with all inputs beats the reference within person (0.64 vs 0.59); steps are among its
  top signals, so here the wristband helps.
- **Readiness and LifeSnaps feelings**: nothing beats "same as today".
- **Linear models fail**: what matters is a drop against the person's own norm combined with the last days, which
  trees pick up and a straight line does not.

## Limits

- 16 PMData people is few; intervals are wide. Many variants were compared (4 targets, several models and inputs),
  so an interval just above 0 can be luck; the mood result is the one with clear room above 0.
- These are healthy people on Earth, not astronauts; the targets are self-reported feelings, not medical events.
- Not yet connected to the app: the next step is to show "tomorrow may be harder" in the real-data check-in demo
  with the SHAP reasons, marked as a forecast.
