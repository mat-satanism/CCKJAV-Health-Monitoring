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
  "source": "manual|sensor|synthetic",
  "message": "Within normal range", "actions": ["..."] }

// BloodRow (reference only, from GET /reference/blood)
{ "panel": "cmp", "analyte": "glucose", "unit": "milligram_per_deciliter", "timepoint": "R+45",
  "days_from_flight": 45, "value": 36.0, "ref_min": 65.0, "ref_max": 99.0,
  "flag": "low", "quality_note": "likely delayed sample processing (...)" }

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

## Validation
`POST /measurements` rejects (422) unknown indicator types and values outside the plausible range in `BOUNDS` (`backend/app/config.py`), e.g. heart rate 20-250 bpm, mood 1-5.

## Status logic
1. Latest value outside `red_*` limits in `data/thresholds.json` → red; outside `yellow_*` → yellow. A `null` red limit means that side only goes yellow (used for mood and exercise: one bad day shouldn't call the ground).
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
| GET | /mission | simulated crew mission: `{day, days_total, crew[], source: "synthetic", note}` |
| PUT | /mission/day?day=N | move the mission clock (1..days_total) |
| GET | /mission/timeline | per day: `{day, status, high_risks, alerts[], changed_tasks}` for the mission strip |
| GET | /mission/crew | per astronaut: indicators vs personal norm, symptoms, risks for 48 h with signs, `fit_for_high_demand`, `unfit_reasons`, `cautions` |
| GET | /mission/tasks | today's tasks: `status` planned / reassigned / postponed / needs decision, `reassigned_to`, `reason`, `warning` |
| GET | /mission/alerts | crew-wide alerts (solar flare, same symptoms in 3+ people) |
| GET | /mission/doctor?role=cmo\|ground | anomalies, risks above 3x usual, symptoms, alerts; `ground` adds the 20 min data delay |
| GET | /reference/blood?crew=C001 | BloodRow[]: NASA Inspiration4 blood tests, reference only, not daily status |
| POST | /demo/reset | reload the demo mission (real PMData days where they exist, grey elsewhere; see demo.py) |

Mission rules (backend/app/mission.py): red = outside safe limits; yellow = 3+ spreads from the person's own 14-day norm. A red indicator or a fever / dizziness symptom takes someone off high-demand tasks; a high model risk only asks the CMO to confirm.

Todo: `/report` (summary for ground flight surgeon), persistent storage.
