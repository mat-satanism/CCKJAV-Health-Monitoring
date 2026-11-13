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
backend/    FastAPI app (API, rule engine, analytics)
frontend/   React + Vite + TypeScript UI
data/       thresholds, content texts, sample/synthetic data
docs/       api contract, sources, decisions
```

## Quick start
Backend:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs

Frontend (once scaffolded, see `frontend/README.md`):
```bash
cd frontend
npm install
npm run dev
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for workflow.

## Sources
See [docs/sources.md](docs/sources.md). Based on NASA Human Research Program and CSA public resources.
