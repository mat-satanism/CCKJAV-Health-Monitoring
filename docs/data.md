# Data

How the open datasets are downloaded, cleaned and stored. Code: `pipeline/`.

From the repository root, with the same virtual env as the backend (see README):

```bash
source backend/.venv/bin/activate
pip install -r pipeline/requirements.txt
python -m pipeline.get_data     # ~2.1 GB into data/raw/ (not in git); existing files are skipped
python -m pipeline.build        # writes data/processed/ (in git) incl. the simulated mission in sim/
python -m pipeline.model        # trains the risk model -> models/risk_model.json, sim/predictions.csv
pytest pipeline/tests
```

## Datasets

| Folder in `data/raw/` | What | People | License |
|---|---|---|---|
| `inspiration4/` | Blood tests of the Inspiration4 crew (NASA OSDR [OSD-575](https://osdr.nasa.gov/bio/repo/data/studies/OSD-575), [OSD-569](https://osdr.nasa.gov/bio/repo/data/studies/OSD-569)), 7 timepoints before and after a 3-day flight in 2021 | 4 | NASA open data, cite the studies |
| `pmdata/` | [PMData](https://datasets.simula.no/pmdata): Fitbit + daily self-report, Nov 2019 - Mar 2020 | 16 | CC BY-NC 4.0 (non-commercial, cite the paper) |
| `lifesnaps/` | [LifeSnaps](https://zenodo.org/records/7229547) v2: Fitbit Sense, 2021-2022. Only the CSV files are extracted | 71 | CC BY 4.0 |
| `mmash/` | [MMASH](https://physionet.org/content/mmash/1.0.0/): about 24 h of wearable data per person | 22 | ODbL |
| `nhanes/` | [NHANES 2021-2023](https://wwwn.cdc.gov/nchs/nhanes/): `DEMO_L`, `BPXO_L` (blood pressure, pulse), `GLU_L` (fasting glucose), `DIQ_L` (diabetes questionnaire), `GHB_L` (HbA1c) | ~12k | US public domain |

None of the daily datasets are astronauts. The model learns "deviation from a person's own norm" on people on Earth; Inspiration4 gives real spaceflight examples.

## `data/processed/daily.csv`

One row per person per day. Self-reports and device values are separate columns on purpose.

| Column | Meaning | Unit / scale | From |
|---|---|---|---|
| `person_id` | `pm_p01`, `ls_<id>`, `mm_user_1` | | all |
| `source_dataset` | `pmdata`, `lifesnaps`, `mmash` | | all |
| `date` | calendar date (empty for MMASH, which has only day numbers) | YYYY-MM-DD | PMData, LifeSnaps |
| `day` | 1 = the person's first day in the dataset | | all |
| `heart_rate` | resting heart rate | bpm, device | PMData, LifeSnaps |
| `sleep_hours` | sleep the person reported | hours, self-report | PMData |
| `sleep_hours_device` | main sleep measured by the watch | hours, device | all |
| `sleep_quality`, `mood`, `fatigue`, `stress`, `soreness` | morning questionnaire | 1-5, self-report | PMData |
| `readiness` | readiness to train | 0-10, self-report | PMData |
| `stress_score` | Fitbit stress score | 0-100, device | LifeSnaps |
| `exercise_min` | moderately + very active minutes | minutes, device | PMData, LifeSnaps |
| `steps` | steps per day | device | all |
| `temp_skin` | nightly **skin** temperature (not body temperature, about 34 deg C) | deg C, device | LifeSnaps |
| `emo_alert`, `emo_happy`, `emo_neutral`, `emo_relaxed`, `emo_sad`, `emo_tense`, `emo_tired` | short mood survey: 1 = the person ticked this feeling that day, 0 = did not. Filled on 2290 of 7410 LifeSnaps days, 63 people | 0 / 1, self-report | LifeSnaps |

Cleaning rules:

- PMData self-reports are UTC; the day is taken in Oslo time. If someone answered twice on one day, the last answer is kept (18 days).
- PMData resting heart rate of 0 means "no reading" and is dropped (145 of 1803). p12 and p13 have no resting heart rate file.
- PMData sleep counts only the main sleep of the night, not naps.
- Values outside `VALID_RANGES` in `pipeline/common.py` are set to empty, never clipped: 0 on a 1-5 scale, device sleep over 16 h, LifeSnaps nights with 0 minutes asleep.
- MMASH rows with day = -29 (two users) are dropped.

## `data/processed/inspiration4_blood.csv`

One row per crew member, timepoint and analyte. Panels: `cmp` (metabolic panel, 19 analytes) and `cbc` (blood count, 20 analytes). Cytokine panels are not processed because their `_percent` columns are not documented.

| Column | Meaning |
|---|---|
| `crew_id` | C001-C004 |
| `timepoint`, `days_from_flight`, `phase` | `L-92` = 92 days before launch (-92, pre-flight); `R+45` = 45 days after return (45, post-flight) |
| `analyte`, `unit` | from the column name, e.g. `glucose`, `milligram_per_deciliter` |
| `value`, `ref_min`, `ref_max` | result and the lab's reference range |
| `flag` | `low` / `normal` / `high` vs the lab range |

Fixes: hemoglobin is labelled "percent" in the source but is g/dL; ALT/AST max columns lack `range_`; eGFR max is text `N/A` (left empty). Cells that are empty in the source (some CBC timepoints) have no row.

`quality_note`: glucose (36-44 mg/dL) and potassium of C002, C003 and C004 at R+45 are marked "likely delayed sample processing". The same day potassium is above their own usual values for C003 (4.4 vs 3.0-3.8) and C004 (5.9, above the lab range, vs 3.7-4.2); C002's potassium (4.1) stays within its usual 3.5-4.4. C001's glucose (84) and potassium stay normal. Low glucose with raised potassium is the usual sign of blood that waited before processing: cells keep using glucose and leak potassium. OSD-575 says fresh serum was sent at room temperature to Quest Diagnostics. The values are kept; leave them out of charts and conclusions.

## `data/processed/nhanes_reference.csv`

Population percentiles for adults aged 20-60, using NHANES survey weights (`WTMEC2YR` for blood pressure and pulse, `WTSAF2YR` for fasting glucose). Blood pressure and pulse are each person's mean of three readings.

Glucose is computed for adults **without diabetes** (not told by a doctor they have diabetes, `DIQ010 != 1`, and HbA1c below 6.5%), because astronauts are selected healthy. With everyone included the 99th percentile is 310 mg/dL; without diabetes it is 128.

Agreed use: yellow band = 5th-95th percentile, red band = 1st-99th. These describe a population, not a diagnosis; the app's first signal is still the deviation from the person's own norm.

Glucose in `data/thresholds.json` (agreed 2026-11-14): yellow above 114, red above 128 (NHANES without diabetes); yellow below 65 (Inspiration4 lab minimum); no red on the low side until a source is found. The healthy 1st percentile (77 mg/dL) is not used as a low threshold: it is ordinary fasting glucose.

## `data/processed/demo_mission.csv`

30 days of one PMData participant in the backend's `Measurement` format. Heart rate, sleep, mood and exercise are real; blood pressure, glucose and temperature, which this person never measured, are synthetic (`source = synthetic`): the level is the NHANES median for adults 20-60 (a typical healthy person), day-to-day changes follow the assumptions in `pipeline/simulation.py`. Generated in `pipeline/demo.py` with seed 606. Columns: `astronaut_id, mission_day, ts, type, value, unit, source`; read by `demo_mission()` in `backend/app/demo.py`. Person and window: `pm_p06`, 2019-11-06 to 2019-12-05 (`pipeline/demo.py`).

Why this one: of the 16 PMData people, 10 have a 30-day window with 98-100% of resting heart rate, self-reported sleep, mood and exercise filled. pm_p06 is complete and has a clear story: days 1-14 are calm (the personal baseline), on days 18-24 sleep drops to 2-4 h and resting heart rate rises from about 49 to 51.8 bpm, then it recovers. `ts` keeps the real 2019 dates; the backend can shift them to the current mission.

## Feature tables for the model: `features_pmdata.csv`, `features_lifesnaps.csv`

Built by `pipeline/features.py` from `daily.csv`. One row = one person on one **calendar** day `t`. Days without any record stay as empty rows, so "tomorrow" is always `t + 1` and never "the next record" (LifeSnaps has 563 such gap days). MMASH is not included: it has no calendar dates and only 1-2 days per person. Run `python -m pipeline.baselines` for the scores a model has to beat.

| Group | Columns | Meaning |
|---|---|---|
| Who and when | `person_id`, `source_dataset`, `date`, `day`, `dow` | `dow` = day of week, 0 = Monday |
| Split | `fold`, `is_test` | people are dealt into 5 folds with seed 42; fold 4 is held out as the final test. No person is in two folds. PMData: 13 training / 3 test people. LifeSnaps: 57 / 14 |
| Today | the raw column, e.g. `heart_rate`, `sleep_hours_device`, `mood` | value on day t |
| Personal norm | `<col>_base` | median of the previous 14 days (t-14 .. t-1, today not included); empty if fewer than 7 of those days have a value |
| Deviation | `<col>_dev`, `<col>_dev3`, `<col>_z` | today minus norm, the mean of that over the last 3 days, and the deviation divided by the spread of the previous 14 days (with a minimum spread so a flat series does not give infinity) |
| Target | PMData `target_worse_mood`; LifeSnaps `target_neg_emotion` | see below |
| For the baseline | `worse_mood_today`, `neg_emotion_today` | the same yes/no for day t, used by the "same as today" reference |

PMData columns with norm and deviation: `heart_rate`, `sleep_hours_device`, `exercise_min`, `steps`, `sleep_hours`, `mood`, `fatigue`, `stress`. Today's value only: `sleep_quality`, `soreness`, `readiness`. LifeSnaps: `heart_rate`, `sleep_hours_device`, `exercise_min`, `steps`, `stress_score`, `temp_skin`.

**Targets (what the model predicts for tomorrow).**
- PMData `target_worse_mood` = 1 if tomorrow's mood is below this person's usual (median mood of the last 14 days, today included), else 0. Plain mood is not used: 64% of answers are "3".
- LifeSnaps `target_neg_emotion` = 1 if tomorrow the person ticked sad, tense/anxious or tired. Empty unless all three were answered.

**How many rows can be used** (rows where the target exists):

| | Rows with a target | People | Also with a norm for pulse, sleep and exercise today | People | Share of 1 in the target |
|---|---|---|---|---|---|
| PMData | 1517 | 16 | 979 | 14 | 15.7% (training), 11.3% (test) |
| LifeSnaps | 2282 | 63 | 1469 | 49 | 57.7% (training), 51.7% (test) |

**Reference scores** (`python -m pipeline.baselines`, held-out test people). Balanced accuracy is the mean of the hit rate on each class, 0.5 = guessing.

| Dataset | Method | Balanced accuracy | F1 of "worse tomorrow" |
|---|---|---|---|
| PMData | always the majority class | 0.500 | 0.000 |
| PMData | same as today | 0.654 | 0.384 |
| LifeSnaps | always the majority class | 0.500 | 0.682 |
| LifeSnaps | same as today | 0.639 | 0.656 |

A model is only interesting if it beats "same as today" on the test people. Test sets are small (3 PMData people), so differences of a few points are noise.

**Decisions that are provisional** (change them in `pipeline/features.py`): norm = 14 days with at least 7 values; minimum spread = 10th percentile of the training spreads; test fold = 1 of 5. The backend still uses its own norm (first 14 values), see the analysis of 7 / 14 / 21 days in the team document.

**Leakage rules, tested in `pipeline/tests/test_features.py`:** the norm uses only days before today; changing values after day t does not change any feature of day t; "tomorrow" is the next calendar day; each person is in exactly one fold; z-score floors come from training people only.
