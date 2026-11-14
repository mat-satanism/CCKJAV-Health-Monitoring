# Sources

For every threshold or claim used in the app: link + one line on what we took from it.

## NASA Human Research Program
- 5 Hazards of Human Spaceflight: TODO link
- Risks of Human Spaceflight: TODO link
- Ongoing HRP Research in Space: TODO link

## CSA
- Monitoring Radiation for Astronaut Health: TODO link
- Why Do We Conduct Science Experiments in Space?: TODO link

## Explanations and advice in the app
Texts: `data/content/indicators.json`, `systems.json`; every item cites ids from `sources.json` (all opened and read on 2026-11-14; paraphrased). A test checks that each indicator and body system has at least one source.

- `nasa-hazards`: [5 Hazards of Human Spaceflight](https://www.nasa.gov/hrp/hazards/) (NASA Human Research Program)
- `ochmo-tb-019`: [NASA-STD-3001 Technical Brief: Orthostatic Intolerance (OCHMO-TB-019 Rev B)](https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-019-orthostatic-intolerance.pdf) (NASA Office of the Chief Health and Medical Officer, 2023)
- `ochmo-mtb-013`: [NASA-STD-3001 Medical Technical Brief: Bone Loss (OCHMO-MTB-013 Rev D)](https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-030-bone-loss.pdf) (NASA Office of the Chief Health and Medical Officer, 2023)
- `ochmo-tb-031`: [OCHMO-TB-031 Exercise Overview](https://www.nasa.gov/ochmo-tb-031-exercise-overview-2/) (NASA Office of the Chief Health and Medical Officer)
- `hrp-sleep-2016`: [Risk of Performance Decrements and Adverse Health Outcomes Resulting from Sleep Loss, Circadian Desynchronization, and Work Overload (Flynn-Evans, Gregory, Arsintescu, Whitmire)](https://ntrs.nasa.gov/citations/20160003864) (NASA Human Research Program, NTRS 20160003864, 2016)
- `hrp-immune-2009`: [Risk of Crew Adverse Health Event Due to Altered Immune Response, HRP-47060 (Crucian et al.)](https://humanresearchroadmap.nasa.gov/evidence/reports/immune.pdf) (NASA Human Research Program, 2009)
- `stahn-2017`: [Increased core body temperature in astronauts during long-duration space missions (Stahn et al.)](https://www.nature.com/articles/s41598-017-15560-w) (Scientific Reports 7, 16180, 2017)
- `energy-2024`: [Substrate metabolism in male astronauts onboard the International Space Station: the ENERGY study](https://www.nature.com/articles/s41526-024-00360-0) (npj Microgravity, 2024)
- `insulin-2023`: [Spaceflight induces changes in gene expression profiles linked to insulin and estrogen](https://www.nature.com/articles/s42003-023-05213-2) (Communications Biology, 2023)
- `hrp-48033`: [Exploration Medical Capability Clinical Decision Support System Concept of Operations, HRP-48033](https://ntrs.nasa.gov/citations/20220017856) (NASA Human Research Program, 2021)

## Datasets
Details and licenses: [data.md](data.md).
- NASA OSDR OSD-575 and OSD-569 (Inspiration4 blood tests): https://osdr.nasa.gov/bio/repo/data/studies/OSD-575 — lab reference ranges and before/after-flight values.
- NHANES 2021-2023, CDC: https://wwwn.cdc.gov/nchs/nhanes/ — population percentiles for blood pressure, pulse, fasting glucose (`data/processed/nhanes_reference.csv`).
- PMData (Simula): https://datasets.simula.no/pmdata — daily wearable + self-report data for models.
- LifeSnaps (Zenodo 7229547): https://zenodo.org/records/7229547 — daily wearable data for models, skin temperature.
- MMASH (PhysioNet): https://physionet.org/content/mmash/1.0.0/ — sleep and steps.

## Thresholds used
| Indicator | Range used | Source |
|---|---|---|
| heart_rate | TODO | TODO |
| glucose | yellow < 65 or > 114, red > 128 mg/dL (fasting) | High: NHANES 2021-2023 adults 20-60 without diabetes, 95th/99th percentile. Low: Inspiration4 lab reference minimum (OSD-575). See [data.md](data.md) |
