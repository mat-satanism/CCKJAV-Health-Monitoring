# CCKJAV Health Monitoring

NASA Space Apps Challenge 2026 — astronaut self-assessment health monitoring tool.

> Working name. Final name TBD by the team.

## The problem
On long-duration missions (Moon, Mars) astronauts must spot health changes in themselves: radiation, isolation, altered gravity, distance from Earth and a closed environment affect the heart, bones, immune system, sleep and mood. Our tool gathers health indicators, shows status at a glance and tells the astronaut what to do and when to escalate to flight surgeons.

## MVP features
- **Body Map**: clickable astronaut figure, each body system colored by status.
- **Daily Check-in**: 2-minute guided measurements (heart rate, blood pressure, glucose, temperature, sleep, mood) with how-to instructions.
- **Personal baseline**: status is computed against the astronaut's own norm plus absolute safety limits.
- **Trends**: dynamic charts with baseline band and 7-day forecast.
- **Assistant**: rule-based advice with escalation levels (self / crew / ground).
- **Gamification**: daily tasks, points, streaks, badges.
- **Mission context**: ISS, transit, rover, Moon base, Mars base (gravity, comms delay).
- **Mission replay**: synthetic 180-day mission with events for the demo.

> Not medical advice. Thresholds are for demonstration and must be verified with medical sources.

## Repo structure
```
backend/app/
  main.py        API endpoints
  models.py      data models (mirror of docs/api-contract.md)
  config.py      indicators, body systems, environments, thresholds loader
  rules.py       status per indicator/system, advice, escalation level
  analytics.py   baseline / deviation / trend / forecast  <- plug ML models in here
  demo.py        synthetic 30-day demo mission            <- replace with cleaned data
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
