# Crew mission simulation: design

Status: agreed 2026-11-14, built in stages. Mentor's suggestion: show a living mission instead of one person.

## Why

Judges should see a story, not a dashboard of numbers: a crew on a 30-day mission, a health problem the system
spots early, a task that moves from one astronaut to another with the reason, and a separate view for doctors.
Open daily data of real astronauts does not exist, so the mission is synthetic, but calibrated on real data and
labelled as a simulation everywhere.

## Goals

- A crew of 5 with names, roles and skills; one of them is the onboard crew medical officer (CMO).
- 30 mission days of the 8 app indicators per astronaut, generated so they look like real people.
- Health events with early signs a few days before they start, tied to the 5 spaceflight hazards.
- A model that predicts, for each astronaut and day, the chance of each event in the next 48 hours, with the signs behind it.
- Tasks with assignees; when someone is not fit, the task moves to a fit crew member with the needed skill, with the reason.
- A doctors' tab with a role switch: CMO onboard (live data) and flight surgeon on Earth (data 20 minutes late).

## Non-goals

- Clinical accuracy. Event effects are assumptions, not medicine. The app says so.
- Real spacecraft telemetry. Station events (CO2, solar flare) are simulated.

## Anti-goals (would make this a failure even if it works)

- Synthetic values shown as if they were measured on a real person.
- A model whose quality is only shown on the same generator it learned from, with no check on real data.

## Approaches considered

| How events happen | Trade-off | Decision |
|---|---|---|
| A. Scripted scenario | same every time, easy to demo, but a play | no |
| B. Random generator | lively, but a demo may show no event | no |
| **C. Seeded generator with guaranteed events** | rules and model react on their own, the story is guaranteed | **chosen** |

| What the model learns from | Trade-off | Decision |
|---|---|---|
| Real data only | honest, but only predicts mood / feelings | no |
| **Simulation calibrated on real data** | predicts every event; risk of learning our own generator | **chosen**, with checks below |
| Model on real data + rules for events | most honest, less impressive | no |

Who the doctors' tab is for: **both** the onboard CMO and the flight surgeon on Earth, one tab with a role switch.

## How the simulation stays close to real data

| Indicator | Normal days | Source |
|---|---|---|
| `heart_rate`, `sleep_hours`, `mood` | each astronaut copies the mean, day-to-day spread and day-to-day persistence (lag-1 autocorrelation) of one real PMData participant | PMData |
| `exercise_min` | drawn from that participant's real daily values | PMData |
| sleep → next-day mood and pulse | one slope each, estimated within person on PMData | PMData |
| `bp_sys`, `bp_dia`, `glucose` | personal level drawn from NHANES adult percentiles (5th-95th band); day-to-day spread is an **assumption** | NHANES + assumption |
| `temp` | 36.6 °C plus a personal offset and daily noise: **assumption**, no open daily data | assumption |

The first 15 days are always event-free: they are the personal norm.

Checks: synthetic event-free days are compared with real people (mean, spread, persistence per indicator); the
model is tested on missions with seeds it never saw; and it is also scored on real PMData people for the one
target real data has (worse mood than usual).

## Events (effects are assumptions, documented in `pipeline/simulation.py`)

| Event | Hazard | Early signs (before onset) | During the event |
|---|---|---|---|
| Sleep disruption | isolation | 2 days: sleep down, mood slightly down | 5-7 days: short sleep, lower mood, pulse up |
| Infection | closed environment | 2 days: pulse and temperature creeping up | 3-5 days: fever, high pulse, low mood, little exercise |
| Deconditioning | gravity | 4 days of almost no exercise | 3-4 days: lower systolic pressure, higher pulse, dizziness on standing |
| Low mood | isolation | 4 days: mood sliding, less exercise | 6-8 days: low mood, less sleep and exercise |
| CO2 build-up (whole crew) | closed environment | 1 day: everyone sleeps a bit worse | 2-3 days: headache and fatigue in several people at once |
| Solar flare (whole crew) | radiation | none: sudden | 1 day: shelter, EVA postponed. Rule, not prediction |

Label: `label_<event>_48h` = 1 if that event starts on day t+1 or t+2 for this astronaut.

## Demo mission (seed 2026)

Crew: Kenji (commander), John and Stefan (flight engineers, EVA), Amara (CMO), Maria (mission specialist).
Each is calibrated on one real PMData participant (`calibrated_from`). Guaranteed events: John's infection
starts on day 18 (an EVA is planned for him on day 19, so it should go to Stefan), Maria's sleep disruption on
day 21, CO2 build-up on day 25, solar flare on day 27.

## Stages

1. Simulator and demo mission (`pipeline/simulation.py`, `data/processed/sim/`).
2. Model trained on many simulated missions, predictions for the demo mission.
3. API (crew, mission clock, tasks with reassignment, doctors' overview) and frontend (crew, tasks, doctors' tab).

Left to the builder: exact UI layout, task catalogue details, how the mission clock is played in the demo.

## Calibration check (stage 1, 2026-11-14)

`python -m pipeline.build` prints this table: median over people of the mean, the day-to-day spread (standard
deviation) and the persistence (correlation of today with yesterday). Real = 11 PMData people with at least 60
complete days. Synthetic = event-free days of 200 simulated missions.

| Indicator | Mean real / sim | Spread real / sim | Persistence real / sim |
|---|---|---|---|
| Resting pulse, bpm | 61.25 / 60.78 | 2.09 / 1.60 | 0.86 / 0.70 |
| Sleep, h (self-report) | 6.88 / 7.00 | 1.14 / 1.03 | 0.01 / 0.02 |
| Mood, 1-5 | 3.17 / 3.17 | 0.56 / 0.59 | 0.16 / 0.04 |
| Exercise, min | 70.66 / 69.54 | 49.33 / 45.16 | 0.05 / -0.05 |

What this says: levels and spreads match. Real resting pulse is more persistent and spread out because it drifts
over the months of PMData; a 30-day synthetic mission does not drift. In PMData, last night's sleep barely moves
the next day's mood (+0.01 per extra hour) or pulse (-0.05 bpm per extra hour), so the simulator carries almost no
link between them on normal days; the events add that link on purpose.

## Files (stage 1)

`data/processed/sim/` (all synthetic): `crew.csv` (name, role, skills, which real person each is calibrated on),
`days.csv` (one row per astronaut per mission day: the 8 indicators, symptoms, active events, `event_free`,
`label_<event>_48h`), `events.csv` (type, hazard, who, early-sign start, onset, end).
Code: `pipeline/simulation.py`; tests: `pipeline/tests/test_simulation.py`.

## Stage 2: risk model (2026-11-14, switched to random forest the same day)

`python -m pipeline.model` (needs `scikit-learn` and `shap`, training only). One **random forest** per event
(300 trees, at least 20 days per leaf) on 41 features: for each of the 10 indicators the z-score vs the
personal norm and the 3-day mean deviation, the whole-crew deviation of sleep, mood and pulse, and whether a
norm exists yet. Trained on 400 simulated missions (seed 7). Each demo prediction is explained with **SHAP**:
how many percentage points each sign added to the risk; signs adding at least 1 point are shown. The app
reads the precomputed `data/processed/sim/predictions.csv` and the settings in `models/risk_model.json`
(floors, usual risk per event), so it does not need scikit-learn.

Why a random forest: see [model-comparison.md](model-comparison.md). Logistic regression, random forest and
LightGBM were trained on the same data. On new simulated missions the forest and LightGBM tie and both beat
logistic regression; on real people only the forest holds up.

**Test on 100 new simulated missions** (seed 1234, never used in training). AUC: 0.5 = guessing, 1 = perfect.
The rule is "the biggest |z| of any indicator today". "Top 5%" = alerts on the 5% riskiest astronaut-days.

| Event | Share of days | AUC model | AUC rule | Caught with top-5% alerts | Precision of those alerts |
|---|---|---|---|---|---|
| Sleep disruption | 3.0% | 0.830 | 0.675 | 24.7% | 14.9% |
| Infection | 2.0% | 0.945 | 0.798 | 69.3% | 27.3% |
| Deconditioning | 1.9% | 0.960 | 0.648 | 75.5% | 29.2% |
| Low mood | 1.8% | 0.857 | 0.675 | 31.5% | 11.5% |
| CO2 build-up | 2.4% | 0.805 | 0.644 | 28.7% | 13.6% |

**Update 2026-11-15:** the risk model now reads the Bayesian norm, like the statuses; numbers and the real-mood
correction are in `docs/personal-norm.md` ("The models read the same norm"). The paragraphs below are the
median-norm version.

**Real people (PMData, 16 people, 1517 days), target "tomorrow's mood is worse than usual":** the sim-trained
`low_mood` risk scores AUC 0.632 and `sleep_disruption` 0.609 (before HRV and reaction time were added: 0.660,
95% interval over people 0.625-0.689, and 0.595), while
"same as today" scores 0.644. So the forest is on par with the simple reference on real mood, not better: the
interval includes 0.644. The earlier logistic regression scored 0.530 here. Real early-warning skill still
needs real labelled data, and we say so in the pitch.

**Demo mission:** John's infection risk is 42% on day 16 (two days before the fever; his days 1-15 are at
most 0.8%), with the sign "Resting pulse +6.2 bpm vs usual today". Maria's sleep-disruption risk is 22% on day
19 and 16% on day 20, before it starts on day 21. The CO2 day is still caught late: at most 8% the day before,
10% on the day itself. The forest also gives false alarms the CMO has to check, e.g. Stefan's infection risk of
21% on day 26.

Risks are calibrated probabilities, so they look small (events happen on 2-3% of days). The UI should show them
next to the usual level ("10 times the usual risk") rather than as a bare percentage.

## Stage 3: API and frontend (2026-11-14)

Backend: `backend/app/mission.py` reads `data/processed/sim/` and `models/risk_model.json`; endpoints `/mission*`
in `docs/api-contract.md`. Frontend: tabs **Crew mission** (mission clock, crew cards, tasks with reassignment)
and **Doctors** (role switch CMO / flight surgeon), plus the earlier single-astronaut view as **My check-in**.

Rules, chosen with the data:
- (Replaced later the same day by the Bayesian personal norm, see `docs/personal-norm.md`.) Yellow = 3 or more spreads from the person's own norm. With 8 indicators a 2-spread rule marks someone yellow
  on 54% of calm simulated astronaut-days, 2.5 spreads on 30%, 3 spreads on 13% (1-3% per indicator).
- Only measured facts take someone off a high-demand task (a red indicator, fever, dizziness when standing). A high
  model risk (5x the usual level or more) only shows "CMO to confirm fitness": on day 26 the model raises a false
  alarm for Stefan (infection 10.8x usual; with the median norm it was Kenji on day 19, 5.6x), and an automatic
  swap would be wrong.
- Doctors see risks from 3x the usual level.

Demo walk-through: day 16 John's infection risk is 10.8x usual (pulse +6.2 bpm vs his norm); day 18 fever 38.3 °C,
not fit; day 19 his EVA goes to Stefan ("John is not fit: Symptom: fever"); day 25 same symptoms in all 5 → check the
air (CO2); day 27 solar flare → EVA postponed. Tested in `backend/tests/test_mission.py`.


## Stage 4: heart rate variability and reaction time (2026-11-14)

Two new daily indicators, chosen from what NASA measures on the space station (docs/sources.md):
- `hrv_ms`, heart rate variability during sleep (RMSSD, wearable). Calibrated on real people: each astronaut
  copies the median, spread and persistence of one LifeSnaps participant with at least 21 HRV days (39 people,
  medians 19-100 ms). No population limits: only the personal norm decides.
- `reaction_ms`, mean reaction time of the 3-minute PVT (part of NASA's Cognition battery). ASSUMPTION: per-person
  mean 260 ms (between people ±20), daily spread 15 ms, 8 ms slower per hour of sleep below the person's usual.
  Before a personal norm exists, slower than 355 ms is yellow (the PVT-B lapse threshold, Basner & Rubinstein 2011).

Event effects on both are ASSUMPTIONS (in `EVENTS`): e.g. infection lowers HRV by 12 ms, sleep disruption makes
reaction 30 ms slower. They use their own random stream, so all earlier simulated values stayed the same.
Weekly or occasional measures (body mass, bone scans, blood, urine, saliva, the full cognition battery) are not
simulated; the app lists them with sources in "Also measured, not daily" (`data/content/measurement_plan.json`).

## Data cleaning (2026-11-15)

Rebuilt after cleaning the daily table (`docs/data.md`, "Cleaning update"). Two changes reach the simulation:
- **Exercise**: each astronaut copies the exercise days of a real person, and days the watch was not worn used
  to count as 0 minutes. Now they are left out: share of no-exercise days for Maria's real person 28% → 9%,
  Amara's 14% → 10%. The risk model catches deconditioning (little exercise) much better: 54% → 76% of events.
- **Glucose**: the day-to-day change is now real (BIG IDEAs morning glucose, 16 people): spread 8.2 mg/dL,
  no carry-over from day to day. It was assumed: 6.0 mg/dL with persistence 0.2.

The risk-model table above is the re-run. Demo story: John's infection risk is 23× usual on day 16 (0.3× or less
on days 1-15); false alarms: Maria day 16, Stefan days 26-27.
