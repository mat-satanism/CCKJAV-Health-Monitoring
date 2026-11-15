# Who enters what (2026-11-15)

Mentors asked us to stop making the astronaut type numbers. On the space station most values arrive by themselves,
the crew medical officer keeps the clinical record, and the astronaut only reports what no device can measure.
The app now follows that split (`collected_by` on every indicator in `backend/app/config.py`, shown in `/meta`).

| Value | Who provides it | In the app |
|---|---|---|
| Heart rate, heart rate variability, blood pressure, sleep hours, exercise minutes | the wearable, automatically | arrives by itself; not in the astronaut's check-in |
| Reaction time | the 3-minute test | the test records it |
| Blood glucose, body temperature | the crew medical officer, at a check-up or when someone is unwell | medic tab |
| Mood, symptoms, "ready for the day" | the astronaut | the check-in |
| Medicines (drug, dose, why, given by medic or taken by themselves, side effects) | the medic | medic tab, medication log |
| Clinical notes | the medic, in SOAP form (subjective, objective, assessment, plan) | medic tab |

A medic can still type a wearable or test value by hand, for example when the wearable was charging, but only
with a reason; the value is then marked "typed by medic" and keeps the reason. The API enforces the same rules
(`docs/api-contract.md`).

## How it is done in practice
- **Wearable.** The CSA Bio-Monitor shirt on the ISS measures pulse and ECG, blood pressure, breathing, skin
  temperature, blood oxygen and activity; the astronaut docks the battery on a base unit, which sends the data to
  Earth. ([CSA](https://www.asc-csa.gc.ca/eng/sciences/astroskin.asp))
- **Medical record.** NASA's Medical Data Architecture prototype stores biosensor data in an electronic medical
  record for the crew medical officer, with SOAP notes and the Dose Tracker medication app.
  ([NASA NTRS 20170000744](https://ntrs.nasa.gov/citations/20170000744))
- **Medicines are under-reported without a log.** When Dose Tracker asked crew to log each dose, the average was
  453 uses per crewmember, far above what recall-based records showed.
  ([npj Microgravity 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6565689))
- **Self-report.** NASA's Reaction Self Test asks about sleep timing and quality and 0-10 ratings of stress,
  fatigue and sleepiness; the reaction time itself is measured by the test.
  ([Sleep 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC8919197))

## Limits
In the demo the "wearable" is a replay: 30 real days of a PMData participant, or the simulated crew mission. There
is no device connection yet. The medic's forms have no login: anyone using the demo can open them.
