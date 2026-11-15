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

### Round 2: composite features (`python -m pipeline.wellbeing_search mood|fatigue`)

Within-person AUC, mean of 3 splits of people (min-max in brackets). Start: the best forest above for each target.

| Variant | Mood | Fatigue |
|---|---|---|
| Same as today | 0.608 | 0.590 |
| Start (current best) | 0.675 (0.670-0.680) | 0.640 (0.637-0.644) |
| + wellbeing index (mean of today's answers against norm, its 3-day mean and change) | 0.670 | 0.635 |
| + sleep debt (shortfall against own norm over 3 days) | 0.679 | 0.632 |
| + training load (acute 7 days / chronic 28 days, ACWR) | 0.667 | 0.636 |
| + interactions (pulse up × short sleep, stress × fatigue) | 0.676 | 0.636 |
| + days since the last bad day | 0.678 | 0.645 |
| + all composites | 0.674 | 0.640 |
| Regression on "tomorrow minus usual" instead of yes/no | 0.665 | 0.606 |
| Score centred on the person's own past scores | 0.684 | 0.646 |

Every variant lands within ±0.01 of the start, inside the spread between splits. With 16 people the data seem to
hold about this much signal: **0.67-0.68 for mood and 0.64 for fatigue**, and more feature work does not move it.

### The honest number: nested check

Comparing many variants and keeping the best one flatters the result. So we also ran the whole search inside a
nested check: for each fold of people, the best variant is chosen on the other people only (inner folds), then
scored on the held-out ones. This number includes the cost of our own searching.

| Target | Same as today | Search, scored nested | Difference, 95% interval | Variants picked in the 5 folds |
|---|---|---|---|---|
| Worse mood | 0.608 | **0.666** | **+0.023..+0.094** | all composites, days since ×3, centred |
| More tired | 0.590 | **0.644** | **+0.006..+0.119** | centred ×3, days since ×2 |

Both stay above "same as today" even after paying for the search. The model in `pipeline/wellbeing.py` keeps the
simple start version: the variants are equivalent, and the simpler one is easier to explain.

## What this means

- **A worse mood tomorrow can be predicted better than "same as today" for the same person**: within-person AUC
  0.68 against 0.61 (0.67 after paying for our search in the nested check), interval entirely above 0, on people
  the model never saw. It is the first real-data result
  in the project that beats the simple reference instead of matching it.
- **Fatigue**: the forest with all inputs beats the reference within person (0.64 vs 0.59, also in the nested
  check); steps are among its top signals, so here the wristband helps.
- **More features do not help further**: sleep debt, training load, interactions and a wellbeing index all land
  within ±0.01. The ceiling is the data (16 people), not the model.
- **Readiness and LifeSnaps feelings**: nothing beats "same as today".
- **Linear models fail**: what matters is a drop against the person's own norm combined with the last days, which
  trees pick up and a straight line does not.

## Limits

- 16 PMData people is few; intervals are wide. Many variants were compared (4 targets, several models and inputs),
  so an interval just above 0 can be luck; the mood result is the one with clear room above 0.
- These are healthy people on Earth, not astronauts; the targets are self-reported feelings, not medical events.

## In the app

`python -m pipeline.wellbeing export` trains the mood model (check-in + last days) and the fatigue model (all
inputs) on every PMData person **except the demo person** (`pm_p06`), then forecasts that person's 30 demo days:
probability, times the usual rate, up to 3 signs that raised the risk by at least 1 percentage point (SHAP), and
what really happened the next day. Output: `data/processed/wellbeing_demo.json`, served by `GET /wellbeing` and
shown as "Tomorrow's outlook" in Check-in → Real-data demo. The card names reasons only from 1.5× usual, turns
yellow from 2×, and always shows the score against "same as today".
