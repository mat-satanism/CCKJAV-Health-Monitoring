# ML on one page (for the pitch)

Charts in this folder are made by `python -m pipeline.pitch_charts`; every number comes from the data, the same
numbers are in `facts.json`. Not medical advice.

## The problem we solve with ML

On Mars the doctor is 20 minutes away and the crew medical officer is busy. The app has to notice **early**
that something is off for **this** astronaut, say **why**, and never take someone off a task on a guess.

## Three findings, three charts

**1. Everyone has their own normal** (`2-everyone-has-their-own-normal.png`).
Usual resting pulse differs by 32 bpm between 79 ordinary people (PMData, LifeSnaps). A fixed "too low" limit of
55 bpm would flag 9 of them on an ordinary day. So every status in the app is computed against the person's own
norm, learned the Bayesian way (`docs/personal-norm.md`).

**2. Tomorrow's mood and energy can be forecast on real people** (`1-forecast-beats-same-as-today.png`).
Trained and scored on real people only, each person scored by a model that never saw them:

| Tomorrow | "Same as today" | Our forest | Gain, 95% interval |
|---|---|---|---|
| Lower mood | 0.61 | **0.68** | +0.04 .. +0.12 |
| Less energy | 0.59 | **0.64** | +0.01 .. +0.12 |
| Readiness, LifeSnaps feelings | | no better | we show this too |

AUC within a person (is tomorrow a bad day *for me?*), 0.5 = guessing. Even after paying for every variant we
tried (nested check) the gain holds: mood 0.67, energy 0.64. In the app: "Tomorrow's outlook" in the real-data
demo, for a person the model never saw, with the reasons (`docs/wellbeing-model.md`).

**3. Early warning before symptoms** (`3-early-warning-before-fever.png`, simulated mission).
The risk model flags John's infection on day 16, at 20× the usual risk, 2 days before the fever, while his pulse
and temperature are still inside the safe limits. It also gives false alarms (Maria day 16, Kenji day 17, Stefan
days 26-27), which is why a prediction only asks the CMO to confirm and never moves a task by itself
(`docs/simulation.md`).

## Why the judges can trust the numbers

- **People never in both training and testing.** Folds are split by person, the demo person is never in training.
- **Always against a simple reference** ("same as today"), never against nothing. Accuracy is not used: bad days
  are rare, so "never alert" would look accurate.
- **Score that matches the question.** We found that the usual pooled AUC can be raised from 0.69 to 0.73 just by
  learning which people are moody; for one person that changes nothing. We report AUC within a person.
- **We say what failed.** Readiness and LifeSnaps feelings: no gain. Sleep debt, training load, interactions and
  a wellbeing index: no gain. Logistic regression: worse than the reference.
- **Every alert explains itself** (SHAP: which signs pushed the risk up), as NASA-STD-3001 Vol. 2 asks of
  decision support.
- **Runs offline** on a laptop: small forests, precomputed files, no cloud.

## Honest limits (say them before the judges ask)

- No open daily data of astronauts exists. Real-data models learn on people on Earth (16 + 58); the crew mission
  is synthetic, calibrated on real people and labelled as such everywhere.
- The infection warning is shown on the simulation, so it proves the approach, not clinical skill.
- Self-reported mood and energy are feelings, not diagnoses. The app says "forecast, not a diagnosis".

## Likely questions

- *Why not astronaut data?* It is not public (NASA LSDA, access by request). The pipeline retrains on it without
  changing the app.
- *Is 0.68 good?* It is modest, and it is honest: measured on people the model never saw, against the strongest
  simple rule. Models that report 0.9 on 16 people usually leak.
- *Why random forest?* Same accuracy as boosting on simulation, more stable on real people, exact SHAP
  explanations (`docs/model-comparison.md`).
