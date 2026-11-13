# API contract

Single source of truth for frontend and backend. Change it in the same PR as the code.
Live docs: http://127.0.0.1:8000/docs

## Types
```jsonc
// Measurement
{ "id": "uuid", "astronaut_id": "a1", "ts": "2026-11-14T08:00:00Z",
  "type": "heart_rate", "value": 72, "unit": "bpm", "source": "manual|sensor|synthetic" }

// IndicatorStatus
{ "type": "heart_rate", "latest": 72, "status": "green|yellow|red|grey",
  "baseline": 65, "deviation": 1.4, "trend": "up|down|flat",
  "message": "Within normal range", "actions": ["..."] }

// BodySystemStatus
{ "system": "cardiovascular", "status": "yellow", "indicators": ["heart_rate","bp_sys","bp_dia"] }

// Task
{ "id": "bp", "title": "Measure blood pressure", "points": 10, "done": false }

// MissionContext
{ "environment": "iss|transit|rover|moon_base|mars_base", "mission_day": 94,
  "gravity_g": 0.38, "comm_delay_s": 1200 }
```

Indicators: `heart_rate` (bpm), `bp_sys`/`bp_dia` (mmHg), `glucose` (mg/dL), `temp` (°C), `sleep_hours` (h), `mood` (1-5), `exercise_min` (min).

Body systems: `cardiovascular`, `musculoskeletal`, `behavioral`, `immune`, `metabolic`, `sleep`.

## Status logic
1. Latest value outside `red_*` limits in `data/thresholds.json` → red; outside `yellow_*` → yellow.
2. Otherwise, |deviation from personal baseline| ≥ 2 → yellow.
3. No data → grey. A system takes the worst status of its indicators.
4. Escalation: any red → `ground`; 2+ yellow → `crew`; else `self`.

## Endpoints
| Method | Path | Returns |
|---|---|---|
| GET | /health | `{ok}` |
| GET | /meta | labels/units for indicators, systems, environments |
| GET / PUT | /context | MissionContext (PUT fills gravity and delay from environment) |
| POST | /measurements | Measurement[] |
| GET | /measurements?type=&start=&end= | Measurement[] sorted by time |
| GET | /status | `{indicators: IndicatorStatus[], systems: BodySystemStatus[]}` |
| GET | /insights | `{level: "self|crew|ground", items: [...], comm_note}` |
| GET | /forecast/{indicator}?days=7 | `{type, values: number[]}` |
| GET | /tasks | Task[] |
| POST | /tasks/{id}/complete | Task |
| POST | /demo/reset | reload synthetic demo mission |

Todo: `/report` (summary for ground flight surgeon), persistent storage.
