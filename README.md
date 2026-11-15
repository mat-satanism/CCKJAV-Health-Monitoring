# Crew Health Navigator

**Try it: https://crew-health-navigator.onrender.com** (no installation; the first visit after a quiet spell can take up to a minute to wake the site)

A health-monitoring tool for astronauts on long missions, built for the NASA Space Apps Challenge 2026. Each astronaut checks in once a day; the app compares every value with **that person's own norm**, says what looks unusual and why, and tells who should react: the astronaut, the crew medical officer on board, or the flight surgeon on Earth. It works without internet, because on Mars a message takes 20 minutes each way.

> Demo, not medical advice. The crew, their missions and their illnesses are simulated; the limits and advice are for demonstration and must be checked with medical sources before any real use.

## The problem
On missions to the Moon and Mars, radiation, isolation, changed gravity, distance from Earth and a closed environment affect the heart, bones, immune system, sleep and mood. Doctors are minutes away, and the onboard medical officer is busy. The app has to notice **early** that something is off for **this** person, say **why**, and never take someone off a task on a guess.

## A two-minute tour
1. Open the site, **Crew mission** tab. Press day **18** on the mission strip: John gets a fever, his tasks move to a fit crewmate with the reason, and his close contacts are asked to check their temperature.
2. Press **Doctors**: the onboard view starts with "Right now", one line per person and what to do; switch to the flight surgeon to see the 20-minute delay.
3. Open **Check-in**, pick **Real-data demo**: 30 real days of one participant of a public study, a body map, a trend per indicator with the personal norm, and tomorrow's mood and energy forecast.
4. Try **Light theme / Dark theme** in the header.

## What is real and what is simulated
There is no open daily health data of astronauts, so the app is honest about what it uses (details: [docs/limits-and-assumptions.md](docs/limits-and-assumptions.md)).

| Part | Real or simulated |
|---|---|
| Blood tests of the Inspiration4 crew (4 people, 7 time points) | real, NASA OSDR |
| Daily pulse, sleep, mood, exercise of ordinary people (PMData, 16 people); heart rate variability (LifeSnaps); typical blood pressure, pulse, glucose (NHANES, BIG IDEAs) | real, public datasets |
| The crew, their 30 days, their illnesses and biographies | **simulated**, calibrated on the real data above |
| How each event moves the numbers, reaction-time levels | **our assumptions**, written in `pipeline/simulation.py` |

Every simulated value is labelled "synthetic" in the app. On simulated missions the models work well; that shows the approach works if the early signs look like our simulation, and says nothing about real astronauts.

## How it works
- **Personal norm, not one limit for everyone.** Usual resting pulse differs by 32 bpm between ordinary people, so a fixed limit flags the wrong ones. Status is computed against the person's own norm, learned the Bayesian way: start from what is typical for people, update with the person's last 14 days. Yellow outside their 99% band, or outside the 95% band two days in a row; red only at safety limits ([docs/personal-norm.md](docs/personal-norm.md)).
- **Rules and small models, no chatbot.** Transparent rules and statistics that run offline and explain every alert (the signs and how many days). The risk model is a random forest per event with SHAP explanations ([docs/model-comparison.md](docs/model-comparison.md)); its percentages are recalibrated ([docs/calibration.md](docs/calibration.md)).
- **Forecasts that beat "same as today".** Tomorrow's mood and energy are forecast from real people only and scored on people the model never saw (mood 0.70 vs 0.61 for "same as today"; [docs/wellbeing-model.md](docs/wellbeing-model.md)).
- **Re-measure before calling Earth.** One red reading asks to re-measure; only a red confirmed by the next reading calls the flight surgeon, on a full screen with yes/no steps and the signal delay. An old value is grey ("no fresh value"), never red.
- **Crew-wide signal.** When 3 or more people move the worrying way on the same day, the app points to a shared cause (air, noise, schedule) instead of treating people one by one ([docs/crew-signal.md](docs/crew-signal.md)).

## What is in the app
- **Crew mission** (simulation): 5 astronauts over 30 days, mission clock, crew status, risks for the next 48 hours, tasks that move to a fit crewmate, isolation of close contacts, week trends, kind messages. The same crew can be moved to a Mars base, Moon base, space station, deep-space transit or Mars rover; each place has its own mission ([docs/environments.md](docs/environments.md)).
- **Doctors**: onboard medical officer or flight surgeon on Earth, an overnight report to save as PDF, a chart of the whole crew's distance from their own norm.
- **Check-in per person**: body map coloured by status, values and symptoms for a chosen day, morning readiness check, history with the usual range, a fictional patient file turned into an exposure history with sourced checks.
- **Real-data demo**: 30 real days of one PMData participant (blood pressure, glucose and temperature are synthetic and labelled), with tomorrow's outlook and its reasons.
- **Tasks** with points and "how do you feel after it?"; **sourced limits** (each limit in `data/thresholds.json` names its source and which numbers are our own choice); **two themes** (the light one meets WCAG 2.2 AA contrast and never shows status by colour alone).

Planned: streaks and badges; sleep quality on a sourced scale (no source found yet for the 1-7 scale).

## Run it yourself
Everything in one container:
```bash
docker build -t chn . && docker run -p 7860:7860 chn
```
Open http://localhost:7860.

Or backend and frontend separately:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload        # http://127.0.0.1:8000/docs, tests: pytest
```
```bash
cd frontend
npm install
npm run dev                          # http://localhost:5173
```
The backend starts with a synthetic demo mission; "Reset demo" in the app restores it.

## Repository
```
backend/app/
  main.py        API endpoints
  models.py      data models (mirror of docs/api-contract.md)
  config.py      indicators, body systems, environments, thresholds loader
  status.py      one status rule for every view (personal norm first, then safe limits)
  rules.py       status per indicator/system, advice, escalation level
  mission.py     simulated crew mission: crew, tasks, alerts, doctors' view
  analytics.py   trend arrow and the 7-day chart forecast (fitted: docs/forecast.md)
  demo.py        Check-in real-data demo: 30 real PMData days + synthetic BP, glucose, temp
backend/tests/   pytest
frontend/        React + Vite + TypeScript UI (see frontend/README.md)
pipeline/        data cleaning, simulation, models, charts (python -m pipeline.<module>)
models/          trained risk model and norm priors the app reads
data/            thresholds.json (limits), content/ (sourced texts), processed/ (cleaned data, simulated missions)
docs/            api contract, methods and results, sources, pitch charts
```


## Data and models
Everything is rebuilt by commands in `pipeline/`; the app reads the precomputed files.
- **Cleaned data:** `python -m pipeline.get_data` (downloads the public datasets into `data/raw/`, not in git), then `python -m pipeline.build` fills `data/processed/`. Columns, cleaning rules and licences: [docs/data.md](docs/data.md), [data/processed/README.md](data/processed/README.md). Which days have data, per person: [docs/data-completeness.md](docs/data-completeness.md).
- **Models:** `python -m pipeline.model` trains the risk model (`models/risk_model.json`) and writes the demo predictions; `python -m pipeline.wellbeing` trains the wellbeing forecast; `python -m pipeline.forecast_eval` fits the chart forecast ([docs/forecast.md](docs/forecast.md)).
- **Checks:** `python -m pipeline.calibration` (can the percentages be trusted), `python -m pipeline.norm_days` ([docs/norm-days.md](docs/norm-days.md)), `python -m pipeline.early_warning` ([docs/early-warning.md](docs/early-warning.md)), `python -m pipeline.environments` ([docs/environments.md](docs/environments.md)).
- **Design and results:** [docs/simulation.md](docs/simulation.md); one-page ML summary with the charts: [docs/pitch/](docs/pitch/README.md) (`python -m pipeline.pitch_charts`).
- **Thresholds:** edit `data/thresholds.json` and add the source to [docs/sources.md](docs/sources.md). API: [docs/api-contract.md](docs/api-contract.md).

## Public site
The site runs on Render's free plan from the `Dockerfile` (`render.yaml`) and redeploys after every merge to `main`. A free service sleeps after 15 minutes without visitors, so `.github/workflows/keep-awake.yml` opens it every 10 minutes (repo variable `SITE_URL`). GitHub can start scheduled jobs a few minutes late: open the site by hand before a presentation. The demo is shared: a check-in or "Reset demo" by one visitor is seen by everyone.

## Sources and licences
All sources: [docs/sources.md](docs/sources.md) (NASA Human Research Program and OSDR, CSA, CDC, AHA/ACC and the public datasets). The datasets keep their own licences, listed in [data/processed/README.md](data/processed/README.md); PMData is CC BY-NC 4.0, so non-commercial use only.
