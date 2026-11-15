# Same crew, another place

The header's place switch (Mars base, Moon base, space station, deep-space transit, Mars surface rover) loads a
separate simulated mission for that place: the same five people, the same 30 days, simulated with that place's
hazards and scored by the same risk model. Everything is synthetic, like the original mission
([simulation.md](simulation.md)).

```
python -m pipeline.environments    # writes data/processed/sim/<place>/ and docs/environments.json
```

## What the place changes

The **Mars base** is the original mission and is not changed: all its factors are 1, and a test checks that its
days are identical to `data/processed/sim/days.csv`. So every number in the pitch and in the other docs
(John 31× on day 16, the calibration, the early-warning comparison) still holds.

Each of the other places multiplies how often an event starts (rate) and how strongly it moves the indicators
(effect). These factors are **assumptions**; the reasons are below.

| Place | Gravity | Signal delay | Deconditioning | Solar flare (shelter) | CO2 build-up | Demo story after day 15 |
|---|---|---|---|---|---|---|
| Mars base | 0.38 g | 20 min | 1× | 1× | 1× | John's infection, Maria's sleep, CO2, flare |
| Space station (LEO) | 0 g | live | 1.5× rate and effect | 0.2× | 1× | John's infection, Stefan deconditions, CO2 |
| Deep-space transit | 0 g | up to 10 min | 1.5× rate and effect | 2× | 1× | John's infection, Maria deconditions, flare, Kenji's low mood |
| Moon base | 0.16 g | 1.3 s | 1.25× rate and effect | 2× | 1× | John's infection, Stefan deconditions, Maria's sleep, flare |
| Mars surface rover | 0.38 g | 20 min | 1× | 1× | 1.5× | John's infection, CO2 twice, Maria's sleep |

**Why these factors:**
- **Gravity → deconditioning.**
  - Fluid shifts and orthostatic intolerance come from weightlessness (OCHMO-TB-019 in `data/content/sources.json`).
  - We assume the effect grows as gravity falls: 0 g is 1.5× the Mars base, and the Moon sits in between.
  - There is no human data at 0.16 g or 0.38 g, so the in-between values are a guess with the right direction, not a measurement.
- **Radiation → solar flare shelter.** The measured daily doses are:
  - in transit to Mars, 1.84 mSv a day (Zeitlin et al., *Science* 2013, MSL RAD);
  - on the Mars surface, 0.64 mSv a day (Hassler et al., *Science* 2014);
  - on the lunar surface, 1.37 mSv a day (Zhang et al., *Science Advances* 2020, Chang'e 4).

  Transit and the Moon therefore get about twice the Mars-surface exposure (2×). Low Earth orbit sits inside Earth's
  magnetic field, which turns most solar particles away (0.2×, an assumption).
- **Closed environment → CO2.** A small pressurised rover has far less air per person than a base, so CO2 builds up sooner (1.5×, an assumption).
- **Signal delay** comes from the app's config. It changes the flight surgeon's view: on the station the data is
  live and the guidance says so, while in transit and on Mars it arrives late.

**Days 1-15.** These are the same everywhere: they are the calm weeks the personal norm learns from, and events
start only after them, as in the original design. The place shows from day 16.

## Does the model still work elsewhere?

The model was trained on Mars-base missions only. For each place it was scored on 100 new random missions
simulated with that place's hazards (test seed, never used in training).

**AUC (0.5 = guessing):**

| Event | Mars base | Station | Transit | Moon | Rover |
|---|---|---|---|---|---|
| Infection | 0.944 | 0.948 | 0.948 | 0.947 | 0.951 |
| Deconditioning | 0.960 | 0.955 | 0.948 | 0.962 | 0.949 |
| Low mood | 0.856 | 0.845 | 0.856 | 0.845 | 0.848 |
| Sleep disruption | 0.828 | 0.823 | 0.822 | 0.829 | 0.823 |
| CO2 build-up | 0.802 | **0.744** | 0.779 | 0.802 | 0.775 |

**Mean risk the model said vs share of days with the event in the next 48 h:**

| Event | Station | Transit | Moon | Rover |
|---|---|---|---|---|
| Deconditioning | 2.7% vs 2.8% | 2.8% vs 2.7% | 2.5% vs 2.4% | 2.0% vs 1.9% |
| CO2 build-up | 3.0% vs 2.6% | 2.9% vs 2.4% | 2.9% vs 2.0% | **3.0% vs 3.5%** |

**What this means:**
- The model carries over. Ranking (AUC) stays within about 0.02 of the Mars base for every event except CO2.
- The average risk follows the place: more deconditioning on the station and in transit, and the model says more.
- **Two honest weak spots:**
  - On the station, CO2 is harder to tell apart (0.744). Stronger deconditioning also raises pulse and lowers HRV, which look like early CO2 signs.
  - In the rover, CO2 comes more often than the model learned on Mars, so it says 3.0% where 3.5% happen. It understates that risk a little.
- A real mission would retrain on its own place. The pipeline already takes the place as a parameter (`training_missions(..., env=...)`).

Numbers: `docs/environments.json`. Not medical advice.
