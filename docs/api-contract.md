# API contract

Single source of truth for frontend and backend. Change it in the same PR as the code.

## Types
```jsonc
// Measurement
{ "id": "uuid", "astronaut_id": "a1", "ts": "2026-11-14T08:00:00Z",
  "type": "heart_rate", "value": 72, "unit": "bpm", "source": "manual" }

// IndicatorStatus
{ "type": "heart_rate", "latest": 72, "status": "green|yellow|red|grey",
  "baseline": 65, "deviation": 1.4, "trend": "up|down|flat",
  "message": "Slightly above your normal", "actions": ["..."] }

// BodySystemStatus
{ "system": "cardiovascular", "status": "yellow", "indicators": ["heart_rate","bp_sys","bp_dia"] }

// Task
{ "id": "t1", "title": "Measure blood pressure", "points": 10, "done": false }

// MissionContext
{ "environment": "iss|transit|rover|moon_base|mars_base", "mission_day": 94,
  "gravity_g": 0.38, "comm_delay_s": 1200 }
```

Indicator types: `heart_rate` (bpm), `bp_sys`/`bp_dia` (mmHg), `glucose` (mg/dL), `temp` (°C), `sleep_hours` (h), `mood` (1-5). Stretch: `spo2`, `weight`, `exercise_min`, `radiation_dose`.

Body systems: `cardiovascular`, `musculoskeletal`, `behavioral`, `immune`, `metabolic`, `sleep`.

## Endpoints
| Method | Path | Returns | Status |
|---|---|---|---|
| GET | /health | `{ok}` | done |
| GET/PUT | /context | MissionContext | done (stub) |
| POST | /measurements | Measurement[] | done (in-memory) |
| GET | /measurements?type=&from=&to= | Measurement[] | partial |
| GET | /status | `{indicators: IndicatorStatus[], systems: BodySystemStatus[]}` | stub |
| GET | /insights | `{level: "self|crew|ground", items: [...]}` | todo |
| GET | /tasks, POST /tasks/{id}/complete | Task[] / Task | stub |
| POST | /simulate | generates synthetic mission | todo |
| GET | /report | summary for ground flight surgeon | todo |

Mock responses for frontend: `data/sample/status.json`.
