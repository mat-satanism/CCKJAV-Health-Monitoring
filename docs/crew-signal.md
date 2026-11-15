# Crew-wide signal (2026-11-14)

When several crew members move the worrying way on the same day, a shared cause (station air, CO2, noise,
temperature, light, work hours) is more likely than five separate problems. The app says so, and the CMO checks
the station before treating people one by one. Code: `Mission.crew_signal` in `backend/app/mission.py`.

**Rule.** For each indicator: count the crew members whose value is 2 or more prediction scales off their own
Bayesian norm in the worrying direction (`WORSE_WHEN`). A signal needs at least 3 people and less than a 5% chance
of that many by accident (binomial, 2.3% per person, the one-sided tail of a normal at 2). No signal in the first
6 days: nobody has a norm yet.

**Tuning on 40 simulated missions** (seed 1234; both directions counted):

| Threshold | CO2 days caught | Calm days with a signal |
|---|---|---|
| 1.5 scales, 3 people | 78% | 10.3% |
| **2.0 scales, 3 people (chosen)** | 59% | 0.8% |
| 1.5 scales, 4 people | 57% | 0% |
| 2.0 scales, 4 people | 35% | 0% |

**Checked on fresh missions** (seed 555, never used for tuning; 2026-11-15): CO2 days caught 76%, calm days with
a signal 0.7%. The thresholds were tuned on seed 1234 (above), so this is the honest number; it holds.

We chose 2.0 / 3 people: a busy CMO should not learn to ignore it. The assumption "people are independent on a
calm day" is ours; days in a row are not independent, so the "chance" is a guide, not an exact probability.

**Demo mission:** signals on day 20 (sleep down in Kenji, John, Maria) and on the CO2 days 25-26 (mood down in
4 of 5, heart rate up in 3 of 5).
