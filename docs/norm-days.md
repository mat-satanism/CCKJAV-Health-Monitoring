# How many days does the personal norm need? (2026-11-15)

Task from the team doc: the code learns the norm from 14 days, the NASA decision-support concept (HRP-48033)
talks about a first week. Which is right? The Bayesian norm (`backend/app/status.py`) has two numbers:
`BAYES_MIN = 6` (days of the person's own data before the norm is used: the calibration week) and
`NORM_DAYS = 14` (the window it keeps learning from). Run: `python -m pipeline.norm_days` (5 s).

**Answer: both current numbers hold up. A first week is enough to start; a 14-day window is the best trade-off
afterwards. No code change.**

## 1. Calibration: how soon is the norm good enough?

264 real series (87 people, PMData + LifeSnaps). After k days, how far is the norm's centre from where the person
really sits over the next 30 days? In units of that month's spread; median over people. Lower is better.

| Days of own data | 3 | 5 | **6 (now)** | 7 | 8 | 10 | 14 |
|---|---|---|---|---|---|---|---|
| All indicators | 0.53 | 0.59 | **0.57** | 0.54 | 0.52 | 0.51 | 0.63 |
| Mood | 0.76 | 0.69 | 0.60 | 0.54 | 0.36 | 0.35 | 0.38 |
| Sleep | 0.27 | 0.21 | 0.24 | 0.27 | 0.33 | 0.23 | 0.29 |
| Resting pulse | 1.02 | 1.06 | 1.00 | 0.98 | 1.09 | 1.14 | 1.00 |

- After 6-7 days the norm is as good as after 14: waiting two weeks buys nothing. This matches NASA's first week.
- Mood is the exception: its norm keeps improving until about day 8. A mood yellow in the first days after
  calibration deserves a softer reading.
- Resting pulse is about one spread off whatever the start: pulse drifts over a month, which no start-up length
  fixes (the window below does the tracking).

## 2. Window: how many recent days should the norm learn from?

Real people, the same 15 959 days for every window: does the 95% band hold the next real value, how wide is it
(in the person's spreads), and on what share of days does the app's rule show yellow? Then 30 new simulated
missions, where events are labelled: calm days with any yellow (any of 10 indicators) and events flagged between
the first signs and the start.

| Window | 7 | 10 | **14 (now)** | 21 | 28 |
|---|---|---|---|---|---|
| Real: next value inside the 95% band | 94.5% | 93.4% | 93.2% | 93.2% | 93.3% |
| Real: band width (spreads) | 4.3 | 4.2 | 4.1 | 4.0 | 4.0 |
| Real: days with yellow (per indicator) | 1.7% | 2.5% | 2.7% | 2.9% | 2.8% |
| Simulation: calm days with any yellow | 15.0% | 17.5% | 17.9% | 18.8% | 18.9% |
| Simulation: **events flagged early** | 87.6% | 92.2% | **93.1%** | 92.2% | 91.7% |
| ... sleep disruption | 72.6% | 83.9% | 85.5% | 85.5% | 87.1% |
| ... low mood | 84.6% | 87.2% | 92.3% | 89.7% | 87.2% |
| ... deconditioning | 93.9% | 98.0% | 93.9% | 91.8% | 89.8% |

- A 7-day window gives fewer yellows (1.7% of days instead of 2.7%) because it follows the person closely, and
  that is the problem: it also follows the start of a problem and misses more events (88% vs 93%; sleep problems
  73% vs 86%). In space the slow changes are the ones to catch.
- Longer than 14 days gives nothing: slightly narrower bands, slightly fewer events caught.
- Resting pulse is the weak spot on real data: its 95% band holds 89% of next values with 14 days (93% with 7),
  because pulse drifts. A shorter window for pulse only is an option to test with real astronaut data, not a
  change we make on 30-day simulations.

## For the judges

"We checked how long the personal norm needs on 87 real people: a first week is enough to start, as NASA's
concept says, and a 14-day window catches the most problems early in the simulated mission. Shorter windows look
calmer but miss slow problems."

## Limits

- Real data has no labelled events, so the safety side (events caught) comes from the simulation, which has
  30-day missions: windows of 21 and 28 days cannot use their full length there.
- One value per day; healthy people on Earth.
