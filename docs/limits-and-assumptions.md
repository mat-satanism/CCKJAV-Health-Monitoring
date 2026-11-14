# How we worked with limited data, and what we assumed

There is no open daily health data of astronauts. Everything below follows from that.

## What is real, what is synthetic

| Part | Real or synthetic | Where |
|---|---|---|
| Inspiration4 blood tests (4 crew, 7 time points) | real, NASA OSDR | reference table in the app |
| Everyday life of a person: pulse, sleep, mood, exercise | real people (PMData, 16 people) | real-data demo; calibration of the simulator |
| Heart rate variability | real people (LifeSnaps, 39 people with 21+ days) | calibration of the simulator |
| Typical blood pressure, pulse, glucose of healthy adults | real survey (NHANES 2021-2023) | thresholds, simulator levels |
| The crew, their 30 days, their events and medical histories | **synthetic** | crew mission, check-in, doctors |
| Reaction time levels, temperature spread, every event effect | **assumptions** | `pipeline/simulation.py` (ASSUMED, EVENTS) |

Every synthetic value is labelled "synthetic" in the API and in the app.

## Assumptions we made (and where to change them)

- How each event moves the numbers (e.g. infection: pulse +12, temperature +1.8 °C, HRV -12 ms): `EVENTS`.
- Day-to-day spread of pressure, glucose, temperature, reaction time: `ASSUMED`.
- The safety limits for pulse, pressure, temperature, sleep: demo values, marked TODO in `data/thresholds.json`
  until a source is found; glucose and reaction time have sources.
- Advice for mission events (`EVENT_ACTIONS`) is a placeholder, not from a clinical source. So are the isolation
  protocol (fever: isolate; close contact = a shared task in the last 2 days: check temperature twice a day for 3
  days), the support messages and the food tips (`backend/app/mission.py`). The app labels them as placeholders.
- Biographies (`data/synthetic/biographies.json`) are fictional. The exposure -> risk -> monitoring links
  (`data/content/exposures.json`) are sourced; steps marked "our plan" follow from the risk but are not stated
  in a source (e.g. a skin check after years in the sun).
- Crew-wide signal thresholds (2 prediction scales, 3 of 5 people, chance under 5%) were tuned by us on 40
  simulated missions (docs/crew-signal.md).
- How infectious an infection is, is not simulated: contacts are flagged, they do not get ill by themselves.
- Week trends: 7 days that clearly go one way (correlation 0.7 or more) and change by at least 2 of the person's
  usual day-to-day spreads. Thresholds chosen by us, not from a source.

## How we checked ourselves

- People never appear in both training and testing (missions with other seeds; people-level folds for real data).
- Every model is compared with a simple rule, and on real people with "same as today" (see
  `docs/model-comparison.md`).
- Metrics: ROC AUC, PR AUC, precision, recall, F1. Accuracy is not used: events are 2-3% of days, so
  "never alert" would be 97% accurate and useless.

## What the numbers do and do not mean

- On simulated missions the model is good (infection ROC AUC 0.95). That shows the approach works **if** the
  early signs look like our simulation. It does not prove anything about real astronauts.
- On real people the forest only matches the simple "same as today" reference for mood (AUC 0.63-0.66 vs 0.644).
- No model can predict what it has never seen; a new kind of problem will show as "unusual for this person"
  (the personal norm), not as a named risk.

## Why the design still helps

The goals are transparency (every alert says why, with SHAP and the personal band), robustness (only measured
facts take someone off a task; a prediction only asks the CMO to confirm) and fewer human errors (everything is
checked every day, nothing depends on someone remembering). With real data the same pipeline can be retrained
without changing the app.
