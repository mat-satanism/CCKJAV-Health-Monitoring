# Data

How the open datasets are downloaded, cleaned and stored. Code: `pipeline/`.

From the repository root, with the same virtual env as the backend (see README):

```bash
source backend/.venv/bin/activate
pip install -r pipeline/requirements.txt
python -m pipeline.get_data     # ~2.1 GB into data/raw/ (not in git); existing files are skipped
python -m pipeline.build        # writes data/processed/ (in git, ~1 MB)
pytest pipeline/tests
```

## Datasets

| Folder in `data/raw/` | What | People | License |
|---|---|---|---|
| `inspiration4/` | Blood tests of the Inspiration4 crew (NASA OSDR [OSD-575](https://osdr.nasa.gov/bio/repo/data/studies/OSD-575), [OSD-569](https://osdr.nasa.gov/bio/repo/data/studies/OSD-569)), 7 timepoints before and after a 3-day flight in 2021 | 4 | NASA open data, cite the studies |
| `pmdata/` | [PMData](https://datasets.simula.no/pmdata): Fitbit + daily self-report, Nov 2019 - Mar 2020 | 16 | CC BY-NC 4.0 (non-commercial, cite the paper) |
| `lifesnaps/` | [LifeSnaps](https://zenodo.org/records/7229547) v2: Fitbit Sense, 2021-2022. Only the CSV files are extracted | 71 | CC BY 4.0 |
| `mmash/` | [MMASH](https://physionet.org/content/mmash/1.0.0/): about 24 h of wearable data per person | 22 | ODbL |
| `nhanes/` | [NHANES 2021-2023](https://wwwn.cdc.gov/nchs/nhanes/): `DEMO_L`, `BPXO_L` (blood pressure, pulse), `GLU_L` (fasting glucose) | ~12k | US public domain |

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

Known oddity, not explained yet: glucose at R+45 is 36-44 mg/dL for three of four crew.

## `data/processed/nhanes_reference.csv`

Population percentiles for adults aged 20-60, using NHANES survey weights (`WTMEC2YR` for blood pressure and pulse, `WTSAF2YR` for fasting glucose). Blood pressure and pulse are each person's mean of three readings.

Agreed use: yellow band = 5th-95th percentile, red band = 1st-99th. These describe a population, not a diagnosis; the app's first signal is still the deviation from the person's own norm.
