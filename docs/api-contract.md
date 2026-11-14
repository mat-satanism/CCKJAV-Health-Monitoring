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
  "baseline": 65, "deviation": 1.4, "trend": "up|down|flat",   // baseline = personal norm, deviation = spreads from it
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
One rule for every view (`backend/app/status.py`), personal norm first:
1. Latest value outside the `red_*` limits in `data/thresholds.json` → red. A `null` red limit means that side never turns red (mood and exercise: one bad day shouldn't call the ground).
2. Personal norm = median of the previous 14 values (needs at least 7). If the value is 3 or more spreads from it → yellow. The spread has a per-indicator floor from `models/risk_model.json`.
3. Before a norm exists, the `yellow_*` band of `data/thresholds.json` decides yellow. In the crew mission the first 7 days show only red (a calibration week, no yellow from the population band). After the norm exists the population band is not used, so a person's usual value (e.g. an athlete's low resting pulse) is not flagged.
4. No data → grey. A system takes the worst status of its indicators.
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
| GET | /mission/astronaut/{id}?day=N | one crew member's card for day N (default: current day): indicators (with `entered`), body `systems`, risks, synthetic `anamnesis`, `medication_today`, `readiness` |
| GET | /mission/astronaut/{id}/history | every mission day per indicator: value, status, personal `norm`, `low`/`high` = norm ± 3 spreads, `entered` |
| POST | /mission/astronaut/{id}/entries?day=N | `{"values": {"temp": 39.2}, "symptoms": ["fever"]}` replaces that day's simulated values; statuses and tasks follow, risks stay the model's. Saved to `data/local/mission_entries.json`, removed by `/demo/reset` |
| POST | /mission/astronaut/{id}/readiness?day=N | `{"ready": true, "note": ""}` morning readiness check; returns a short `reply` |
| GET | /reference/blood?crew=C001 | BloodRow[]: NASA Inspiration4 blood tests, reference only, not daily status |
| POST | /demo/reset | reload the demo (real PMData days plus synthetic pressure, glucose and temperature; see demo.py) and delete the saved check-ins |

Storage: demo data ends yesterday, so a check-in from today is always the newest value. Values sent to `POST /measurements` are also written to `data/local/checkins.json` (not in git) and loaded again when the backend restarts.

Mission rules (backend/app/mission.py): statuses use the same rule as above. A red indicator or a fever / dizziness symptom takes someone off high-demand tasks; a high model risk only asks the CMO to confirm.

Todo: `/report` (summary for ground flight surgeon), persistent storage.
