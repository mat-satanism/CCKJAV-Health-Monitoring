# Patient files, "why we track this", crew-wide signal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A sourced patient file per crew member, sourced "why we track this / which tests" per indicator, an offline crew-wide (environment) signal and a template daily brief for doctors, plus sourced realism in the mission.

**Architecture:** Content lives in JSON (`data/content/*.json` sourced, `data/synthetic/*.json` fictional); `backend/app/mission.py` computes the crew signal and the brief; new FastAPI endpoints; React pages read them.

**Tech Stack:** FastAPI + Pydantic, pytest; React 19 + Vite + TS; Python pipeline (pandas).

**Spec:** `docs/superpowers/specs/2026-11-14-patient-files-and-crew-signal-design.md`

## Global Constraints
- No language model; everything offline and explainable.
- Every exposure→risk→monitoring link and every "tests" item cites a source id in `data/content/sources.json` that was opened and read; no source → item left out.
- Biographies are fictional and labelled `synthetic` in API and UI.
- One status rule (`backend/app/status.py`) stays the only source of statuses.

## Review Focus
1. A crew member with no exposures in the biography → file page shows "none recorded", no crash.
2. Crew signal on days 1–6 (no personal norm, z is None) → no signal, no crash.
3. A day where every crew member is green → brief says so in one line.
4. An indicator without a `tests` list → panel hides the tests block.
5. Values entered by hand (entries) feed the crew signal and brief the same day.

---

### Task 1: Sourced content (exposures, tests) and fictional biographies
**Files:** Create `data/content/exposures.json`, `data/synthetic/biographies.json`; Modify `data/content/indicators.json` (add `tests: string[]`), `data/content/sources.json`, `backend/app/config.py` (load `exposures`), `docs/sources.md`.
**Interfaces:** Produces `CONTENT["exposures"][id] = {label, risk, monitoring: str[], sources: str[]}`; biography `{background, previous_jobs: str[], hobbies: str[], flights: int, exposures: [exposure id], notes}` per crew id.
- [ ] Test `test_exposures_and_tests_cite_known_sources` (backend/tests/test_api.py): every exposure and every indicator `tests` item has sources that exist in `sources`.
- [ ] Test `test_biographies_only_use_known_exposures`.
- [ ] Research and write content; run tests; commit.

### Task 2: Patient file endpoint
**Files:** Modify `backend/app/mission.py`, `backend/app/main.py`; Test `backend/tests/test_mission.py`.
**Interfaces:** `Mission.patient_file(aid: str, day: int) -> dict` = `{biography, exposures: [{id,label,risk,monitoring,sources}], monitoring_due: str[], anamnesis, history_summary}`; `GET /mission/astronaut/{id}/file?day=N`.
- [ ] Test `test_patient_file_turns_biography_into_monitoring` (John/Kenji have ≥1 exposure with monitoring; unknown id → 404).
- [ ] Implement; run; commit.

### Task 3: Crew-wide signal
**Files:** Modify `backend/app/mission.py`; Test `backend/tests/test_mission.py`.
**Interfaces:** `Mission.crew_signal(day: int) -> list[dict]`, each `{type, label, direction: "up"|"down", people: [names], n, p_chance: float, mean_shift: float, likely_causes: str[]}`. Rule: count crew with personal z ≥ +Z_SHIFT or ≤ −Z_SHIFT (Z_SHIFT = 1.5); signal when ≥ 3 of 5 in one direction and binomial chance < 0.05 under a 0.067 per-person rate (two-sided 1.5 z).
- [ ] Test `test_co2_days_show_a_crew_wide_signal` (days 25–26 have a signal on sleep or mood); `test_no_signal_in_the_calibration_week` (days 1–6 empty).
- [ ] Implement; commit.

### Task 4: Doctors' daily brief
**Files:** Modify `backend/app/mission.py`, `backend/app/main.py`; Test `backend/tests/test_mission.py`.
**Interfaces:** `Mission.brief(day: int) -> {"day", "lines": [str], "all_clear": bool}`; `GET /mission/brief?day=N`. Order: crew signal, alerts, people needing action (from `now`), worse trends, moved tasks, due weekly conference.
- [ ] Test `test_brief_names_john_first_on_day_19`, `test_brief_all_clear_line`.
- [ ] Implement; commit.

### Task 5: Sourced realism in the mission
**Files:** Modify `pipeline/simulation.py` (weekly private medical conference task per crew member), `docs/simulation.md`.
- [ ] Test (pipeline/tests/test_simulation.py) each crew member has one "Private medical conference" per 7 days.
- [ ] Implement, rebuild, retrain predictions; commit.

### Task 6: Frontend
**Files:** Create `frontend/src/components/PatientFile.tsx`, `frontend/src/components/WhyTrack.tsx`, `frontend/src/components/Brief.tsx`; Modify `App.tsx`, `PersonView.tsx`, `DoctorView.tsx`, `api.ts`, `types.ts`, `index.css`.
- [ ] Patient file opens from the card ("Open file") and shows biography, exposures → monitoring with sources, anamnesis.
- [ ] "Why we track this" in each indicator shows why / in space / tests / sources.
- [ ] Doctors: brief + crew signal on top.
- [ ] tsc, eslint, build; browser check; commit.

### Task 7: Docs, checks, wiki
- [ ] README, api-contract, limits doc; pr-check suite; wiki log.
