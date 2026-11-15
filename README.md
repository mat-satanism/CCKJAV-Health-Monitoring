# Crew Health Navigator

NASA Space Apps Challenge 2026 — astronaut self-assessment health monitoring tool.

Repository: CCKJAV Health Monitoring.

## The problem
On long-duration missions (Moon, Mars) astronauts must spot health changes in themselves: radiation, isolation, altered gravity, distance from Earth and a closed environment affect the heart, bones, immune system, sleep and mood. Our tool gathers health indicators, shows status at a glance and tells the astronaut what to do and when to escalate to flight surgeons.

## Features
Working now:
- **Body Map**: clickable astronaut figure, each body system colored by status.
- **Daily Check-in**: heart rate, blood pressure, glucose, temperature, sleep, exercise, mood, heart rate variability, reaction time (3-minute PVT). Each indicator says how often and how to measure it; weekly and occasional measures (body mass, bone, blood, urine, saliva) are listed with sources.
- **Personal baseline**: status is computed against the astronaut's own norm, learned the Bayesian way (start from what is typical for people, update with the person's last 14 days; yellow outside their 99% band or outside 95% two days in a row) plus absolute safe limits, the same rule in every tab. See `docs/personal-norm.md` and `docs/limits-and-assumptions.md`.
- **Trends**: charts with the personal baseline line and a 7-day forecast.
- **Assistant**: rule-based advice with escalation levels (self / crew / ground) and a comms-delay note.
- **Daily tasks** with points.
- **Mission context**: one Mars-base mission (0.38 g, 20 min signal delay).
- **Check-in per crew member**: pick an astronaut, tap the body, pick a day on the mission strip or any chart, see the history with their usual range, enter values and symptoms for that day, answer the morning readiness check, see their (synthetic) medical history and medicine for the day.
- **Demo data (Check-in, real-data demo)**: 30 real days of one PMData participant for heart rate, sleep, mood and exercise; blood pressure, glucose and temperature are synthetic (typical NHANES level + simulated daily changes) and labelled as such.
- **Crew mission (simulation)**: 5 astronauts over 30 days, synthetic data calibrated on real people. Mission clock, crew status, risks for the next 48 h, and tasks that move to a fit crew member with the reason (e.g. John's EVA goes to Stefan because of fever).
- **Doctors' tab**: crew medical officer onboard (live) or flight surgeon on Earth (20 min delay). The CMO is busy, so the onboard view starts with "Right now": one line per person and what to do; the full tables (anomalies, risks with their signs, symptoms) and the alarm log are one click away. A chart shows the whole crew's distance from their own norm over the mission. The ground gets a daily or weekly report made overnight, saved as PDF from the browser's print dialog.
- **Isolation of close contacts**: a fever isolates the person (their tasks move to someone else), and whoever shared a task with them in the last 2 days is asked to check temperature twice a day (John's fever on day 18: Maria worked with him on day 17).
- **Week trends and support**: each card shows what has been going one way for a week (e.g. Maria's sleep going down before her sleep problem), a kind message (take it easier / you're doing well) and demo food tips.
- **Patient file**: a fictional biography turned into an exposure history (e.g. years as a jet pilot, outdoor work, previous long flights) and from it sourced risks and checks, as NASA's lifetime surveillance of astronaut health does.
- **Crew-wide signal and daily brief**: when 3+ crew members move the worrying way on the same day, the app points to a shared cause (air, noise, schedule) instead of treating people one by one; the CMO gets one short brief written by fixed rules from the data.
- **Tomorrow's outlook (real-data demo)**: the chance that tomorrow's mood or energy is below the person's usual, with the reasons (SHAP) and a 30-day strip of forecast vs what really happened. Learned from other real people only (PMData), and shown only because it beats "same as today" on people it never saw (mood 0.68 vs 0.61). See `docs/wellbeing-model.md`.
- **Risk model**: one random forest per event, trained on simulated missions, with SHAP explanations (which signs pushed the risk up). Chosen over logistic regression and LightGBM, see `docs/model-comparison.md`.

Planned:
- How-to-measure instructions in the check-in and body system descriptions.
- Streaks and badges.
- Printable report for the ground flight surgeon.

> Not medical advice. Thresholds are for demonstration and must be verified with medical sources.

## Repo structure
```
backend/app/
  main.py        API endpoints
  models.py      data models (mirror of docs/api-contract.md)
  config.py      indicators, body systems, environments, thresholds loader
  status.py      one status rule for every view (personal norm first, then safe limits)
  rules.py       status per indicator/system, advice, escalation level
  mission.py     simulated crew mission: crew, tasks, alerts, doctors' view
  analytics.py   baseline / deviation / trend / forecast  <- plug ML models in here
  demo.py        Check-in real-data demo: 30 real PMData days + synthetic BP, glucose, temp
backend/tests/   pytest
frontend/        React + Vite + TypeScript UI (see frontend/README.md)
data/            thresholds.json (demo values)
docs/            api contract, sources
```

## For the data / ML team
- **Models:** implement the functions in `backend/app/analytics.py`. Keep the signatures; each gets a time-ordered list of floats for one indicator.
- **Data:** to show real/cleaned data in the app, make `demo_mission()` in `backend/app/demo.py` return your records as `Measurement` objects.
- **Thresholds:** edit `data/thresholds.json` and add the source to `docs/sources.md`.
- Notebooks go to `notebooks/`, raw data to `data/raw/` (keep large files out of git).
- **Cleaned data:** `python -m pipeline.get_data` then `python -m pipeline.build` fills `data/processed/` (daily wearable table, Inspiration4 blood tests, NHANES reference ranges). Columns and cleaning rules: [docs/data.md](docs/data.md).
- **Simulation and model:** `python -m pipeline.build` also writes the simulated crew mission to `data/processed/sim/`; `python -m pipeline.model` trains the risk model (`models/risk_model.json`) and writes the demo predictions. Design, assumptions and results: [docs/simulation.md](docs/simulation.md).
- **Wellbeing forecast on real people:** `python -m pipeline.wellbeing` predicts a worse mood, fatigue or readiness tomorrow on PMData and LifeSnaps, scored within each person on people the model never saw against "same as today". `python -m pipeline.wellbeing export` writes the app's forecasts to `data/processed/wellbeing_demo.json`. Results: [docs/wellbeing-model.md](docs/wellbeing-model.md).

## Quick start
Backend:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs. Tests: `pytest` inside `backend/`.

Frontend (second terminal):
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173. The backend starts with a synthetic demo mission; "Reset demo" in the UI restores it.

See [CONTRIBUTING.md](CONTRIBUTING.md) for workflow.

## Sources
See [docs/sources.md](docs/sources.md). Based on NASA Human Research Program and CSA public resources.
