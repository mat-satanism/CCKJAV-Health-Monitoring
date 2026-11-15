# The 7-day forecast on the charts (2026-11-15)

Every indicator chart in the app ends with a dashed 7-day forecast (`GET /forecast/{indicator}`,
`forecast()` in `backend/app/analytics.py`). It used to be a straight line through the last 7 points. Two days of
rising pulse and the line kept rising for a week. We replaced it with a forecast that goes **back to the person's
own norm**, with an **80% band**, and checked both on real people. Run: `python -m pipeline.forecast_eval` (2 s).

## How it works

- Norm = median of the person's last 14 values (the same window as the rest of the app).
- Tomorrow keeps a share `persistence` of today's distance from the norm; the day after, `persistence²`, and so on.
  0 = back to usual at once (mood, sleep), 0.9 = changes last (resting pulse drifts slowly).
- Band: grows from one day's spread to the person's full spread, scaled by `band` so that 80% of real values fall
  inside. Wider the further ahead.
- Settings per indicator (`FORECAST` in `analytics.py`), fitted on 70 people, scored on 17 others:

| Indicator | Persistence | Band (× spread) | Data |
|---|---|---|---|
| Resting pulse | 0.9 | 2.52 | PMData + LifeSnaps |
| Sleep | 0.0 | 1.51 | PMData (self-report) + LifeSnaps (wristband) |
| Mood | 0.0 | 1.3 | PMData |
| Exercise | 0.0 | 1.32 | PMData + LifeSnaps |
| HRV | 0.5 | 1.59 | LifeSnaps |
| Pressure, glucose, temperature, reaction time | 0.5 | 1.5 | **assumption**: no open daily data |

## Results on people the settings never saw (16 people; re-run 2026-11-15 after the data cleaning)

Error = mean |forecast − real| over the 7 days, divided by the person's spread; relative to "same as today"
(last value repeated). Below 1 is better.

| Indicator | Old straight line | Same as today | Usual level (median) | **Back to own norm (new)** | Real values inside the 80% band |
|---|---|---|---|---|---|
| Resting pulse | 1.36 | 1.00 | 1.16 | **0.97** | 81% |
| Sleep | 1.48 | 1.00 | 0.75 | **0.75** | 82% |
| Mood | 1.66 | 1.00 | 0.78 | **0.78** | 81% |
| Exercise | 1.47 | 1.00 | 0.78 | **0.78** | 73% |
| HRV | 1.36 | 1.00 | 0.89 | **0.88** | 78% |
| **All** | **1.44** | 1.00 | 0.89 | **0.84** | |

- **The old straight line was 44% worse than simply repeating today.** The new forecast is 16% better than that.
- One rule does not fit all: "usual level" is right for mood and sleep and wrong for pulse (1.15), because a pulse
  change lasts. Per-indicator persistence handles both.
- The band is honest: 76-83% of real values fall inside an 80% band on new people.

## Limits

- Only five indicators have open daily data; the other four use an assumed middle setting.
- One value per day; the band says nothing about events (an infection is a jump no forecast of this kind predicts:
  that is the risk model's job, `docs/simulation.md`).
- `trend()` (the arrow next to the value) is unchanged.
- Tried on the simulated crew for a per-astronaut "tomorrow" view: the point forecast is 7% better than "same as
  today" there, but the 80% band holds only 53-78% of crew values (events move them more than real days), so it
  was not shipped (`python -m pipeline.forecast_eval sim`; `docs/wellbeing-model.md`, "Tried for the crew").
