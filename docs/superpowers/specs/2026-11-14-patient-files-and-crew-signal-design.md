# Patient files, sourced "why we track this", crew-wide signal (design, 2026-11-14)

## Why
Mentors and the team want the app to be useful to astronauts and clear for the jury: every crew member has
their own story and risks, every number says why it is tracked, and doctors do not spend hours scanning
dashboards. Nothing invented without a label; every risk rule has a source.

## Goals
1. **Patient file page** per crew member: a fictional biography (background, previous jobs, hobbies, previous
   flights) turned into an **exposure history**, and from it **hazard-specific monitoring**: what to watch and
   which tests, each with a source. This mirrors NASA's Lifetime Surveillance of Astronaut Health, which keeps
   an individual exposure history and builds monitoring protocols from it.
2. **"Why we track this"** for every indicator: why, what changes in space, which tests to do when it is off
   (follow-up), with sources.
3. **Crew-wide signal**: when several crew members move the same way on the same day, the cause is more likely
   the environment (air, CO2, schedule, radiation event) than each person. Transparent statistics, offline.
4. **Doctors' daily brief**: one short text, built from a template, that lists what matters today (people,
   crew-wide signal, trends, tasks moved) so the CMO reads one paragraph instead of tables.
5. **More realistic mission**: sourced facts about life on the station where they change the simulation or the
   app (sleep window, daily exercise, weekly private medical conference with the flight surgeon).

## Non-goals
- No language model (decided: offline rules and statistics; Mars has a 20-minute delay).
- No real people's data in biographies; biographies are fictional and labelled so.
- No medical claim without a source; where none is found the item is left out, not guessed.

## Approaches considered (crew-wide signal)
- **Chosen: per indicator, count crew members whose value is off their own norm in the same direction**
  (Bayesian z beyond a set level) and test how unlikely that is by chance (binomial). Plus the crew's average
  shift. Simple, explainable, matches the existing "same symptoms in 3 people → check CO2" rule.
- Mixed model with a shared day effect: closer to the mentor's statistics, but harder to explain in the UI and
  little gain with 5 people.
- Language model summary: rejected by the team (offline, explainable).

## Parts
- Data: `data/synthetic/biographies.json` (fictional, per crew member) + `data/content/exposures.json`
  (exposure → risk → monitoring/tests → sources) + `tests` field in `data/content/indicators.json`.
- Backend: `/mission/astronaut/{id}/file`, crew-signal in `mission.py`, `/mission/brief?day=`.
- Frontend: patient file page (from the card and the crew list), "Why we track this" panel with tests,
  crew-signal and brief at the top of Doctors.
- Simulation: only sourced realism changes; each change documented in `docs/simulation.md`.

## Left to the builder
Exact thresholds for the crew signal (documented and tested), wording of the brief template, which sourced
exposures fit each fictional biography.
