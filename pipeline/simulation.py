"""Crew mission simulator, calibrated on real data. Design: docs/simulation.md.

Normal days copy real people: each astronaut takes the mean, day-to-day spread and persistence of one
PMData participant for pulse, sleep and mood, and draws exercise from that person's real days. Blood
pressure and glucose levels come from NHANES percentiles. Temperature and every event effect are
ASSUMPTIONS (no open source yet): they live in ASSUMED and EVENTS below so they are easy to replace.
Heart rate variability (RMSSD) copies the median, spread and persistence of one LifeSnaps participant. Reaction
time (3-minute PVT, part of NASA's Cognition battery) is an ASSUMPTION. Both use their own random stream,
so adding them did not change the other simulated values.
Everything this module makes is synthetic and is labelled `source = synthetic`.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MISSION_DAYS = 30
EVENT_FREE_DAYS = 15        # days 1-15 never have events or early signs: they form the personal norm
HORIZON_DAYS = 2            # label = event starts within the next 48 hours
POOL_MIN_FULL_DAYS = 60     # PMData people with fewer complete days are not used for calibration
INDICATORS = ["heart_rate", "bp_sys", "bp_dia", "glucose", "temp", "sleep_hours", "mood", "exercise_min",
              "hrv_ms", "reaction_ms"]
HRV_MIN_DAYS = 21           # LifeSnaps people with fewer HRV days are not used for calibration
FROM_PMDATA = ["heart_rate", "sleep_hours", "mood", "exercise_min"]

# ASSUMPTIONS: no open daily data for these. sd = day-to-day spread, phi = persistence from day to day.
ASSUMED = {
    "bp_sys": {"sd": 5.0, "phi": 0.3},
    "bp_dia": {"sd": 4.0, "phi": 0.3},
    # Glucose day-to-day change is REAL since 2026-11-15: BIG IDEAs morning glucose, 16 people (pipeline/bigideas.py;
    # a test checks these numbers against data/processed/glucose_morning.csv). Was assumed sd 6.0, phi 0.2.
    "glucose": {"sd": 8.2, "phi": 0.0},
    "temp": {"mean": 36.6, "between_people_sd": 0.15, "sd": 0.15, "phi": 0.3},
    # mean of a 3-minute PVT, ms; slower after a short night (ms per hour of sleep below the person's usual)
    "reaction_ms": {"mean": 260.0, "between_people_sd": 20.0, "sd": 15.0, "phi": 0.3, "per_sleep_hour": -8.0},
}
HEALTHY_BAND = (0.05, 0.95)  # personal NHANES level is drawn between the 5th and 95th percentile

# ASSUMPTIONS: how each event moves the indicators. Additive deltas; exercise_factor multiplies exercise.
EVENTS = {
    "sleep_disruption": {
        "hazard": "isolation", "crew": False, "prodrome": 2, "episode": (5, 7), "rate": 0.5,
        "prodrome_effect": {"sleep_hours": -1.0, "mood": -0.3, "hrv_ms": -3.0, "reaction_ms": 10.0},
        "episode_effect": {"sleep_hours": -2.5, "mood": -1.0, "heart_rate": 3.0, "hrv_ms": -6.0, "reaction_ms": 30.0},
        "symptoms": ["trouble sleeping"],
    },
    "infection": {
        "hazard": "closed environment", "crew": False, "prodrome": 2, "episode": (3, 5), "rate": 0.3,
        "prodrome_effect": {"heart_rate": 4.0, "temp": 0.3, "sleep_hours": -0.5, "hrv_ms": -5.0},
        "episode_effect": {"temp": 1.8, "heart_rate": 12.0, "mood": -1.0, "sleep_hours": -1.0, "exercise_factor": 0.3,
                           "hrv_ms": -12.0, "reaction_ms": 20.0},
        "symptoms": ["fever", "fatigue"],
    },
    "deconditioning": {
        "hazard": "gravity", "crew": False, "prodrome": 4, "episode": (3, 4), "rate": 0.3,
        "prodrome_effect": {"exercise_factor": 0.1},
        "episode_effect": {"bp_sys": -8.0, "heart_rate": 6.0, "exercise_factor": 0.3, "hrv_ms": -4.0},
        "symptoms": ["dizziness when standing"],
    },
    "low_mood": {
        "hazard": "isolation", "crew": False, "prodrome": 4, "episode": (6, 8), "rate": 0.3,
        "prodrome_effect": {"mood": -0.5, "exercise_factor": 0.8},
        "episode_effect": {"mood": -1.5, "sleep_hours": -0.7, "exercise_factor": 0.6, "hrv_ms": -3.0, "reaction_ms": 10.0},
        "symptoms": ["low mood"],
    },
    "co2_buildup": {
        "hazard": "closed environment", "crew": True, "prodrome": 1, "episode": (2, 3), "rate": 0.4,
        "prodrome_effect": {"sleep_hours": -0.5, "mood": -0.3, "reaction_ms": 10.0},
        "episode_effect": {"mood": -1.0, "sleep_hours": -1.0, "heart_rate": 3.0, "hrv_ms": -3.0, "reaction_ms": 25.0},
        "symptoms": ["headache", "fatigue"],
    },
    "solar_flare": {   # sudden: handled by a rule (shelter, postpone EVA), not predicted
        "hazard": "radiation", "crew": True, "prodrome": 0, "episode": (1, 1), "rate": 0.3,
        "prodrome_effect": {}, "episode_effect": {}, "symptoms": [],
    },
}
PREDICTED = [e for e in EVENTS if e != "solar_flare"]

# Where the mission happens. Mars base is the original design (all factors 1), so its mission and every number
# measured on it stay as they were; the other places scale how often an event starts ("rate") and how strongly it
# moves the indicators ("effect"). ASSUMPTIONS with the reasoning and sources in docs/environments.md:
# - gravity: deconditioning is stronger the less gravity there is; 0 g (station, transit) 1.5x Mars, Moon 1.25x.
#   No human data exists for 0.16 g or 0.38 g, so the in-between values are an assumption.
# - radiation: a solar particle event that sends the crew to shelter; Earth's magnetic field shields low orbit
#   (0.2x), with no planet field or air on the Moon and in transit the exposure is about 2x the Mars surface
#   (measured daily doses: transit 1.84, Moon 1.37, Mars 0.64 mSv).
# - closed environment: a small pressurised rover reaches high CO2 sooner than a base (1.5x).
ENVIRONMENTS = {
    "mars_base": {"rate": {}, "effect": {}},
    "iss":       {"rate": {"deconditioning": 1.5, "solar_flare": 0.2}, "effect": {"deconditioning": 1.5}},
    "transit":   {"rate": {"deconditioning": 1.5, "solar_flare": 2.0}, "effect": {"deconditioning": 1.5}},
    "moon_base": {"rate": {"deconditioning": 1.25, "solar_flare": 2.0}, "effect": {"deconditioning": 1.25}},
    "rover":     {"rate": {"co2_buildup": 1.5}, "effect": {}},
}
# The demo story per place: John's infection on day 18 everywhere (the model's showcase), then what the place adds.
DEMO_EVENTS_BY_ENV = {
    "mars_base": None,   # DEMO_EVENTS below, unchanged
    "iss":       [("infection", "john", 18, 4), ("deconditioning", "stefan", 22, 4), ("co2_buildup", "crew", 25, 2)],
    "transit":   [("infection", "john", 18, 4), ("deconditioning", "maria", 21, 4), ("solar_flare", "crew", 24, 1),
                  ("low_mood", "kenji", 23, 6)],
    "moon_base": [("infection", "john", 18, 4), ("deconditioning", "stefan", 22, 4), ("sleep_disruption", "maria", 21, 6),
                  ("solar_flare", "crew", 26, 1)],
    "rover":     [("infection", "john", 18, 4), ("co2_buildup", "crew", 21, 3), ("sleep_disruption", "maria", 23, 5),
                  ("co2_buildup", "crew", 27, 2)],
}


def scaled_effect(effect: dict, k: float) -> dict:
    """An event's effect made k times stronger: deltas times k, the lost share of exercise times k."""
    if k == 1:
        return effect
    return {key: (max(0.0, 1 - (1 - v) * k) if key == "exercise_factor" else v * k) for key, v in effect.items()}

DEMO_SEED = 2026
DEMO_CREW = [
    {"astronaut_id": "kenji", "name": "Kenji", "role": "Commander", "skills": "command;eva;robotics", "calibrated_from": "pm_p07"},
    {"astronaut_id": "john", "name": "John", "role": "Flight engineer", "skills": "eva;maintenance", "calibrated_from": "pm_p01"},
    {"astronaut_id": "stefan", "name": "Stefan", "role": "Flight engineer", "skills": "eva;maintenance;robotics", "calibrated_from": "pm_p06"},
    {"astronaut_id": "amara", "name": "Amara", "role": "Crew medical officer", "skills": "medical;science", "calibrated_from": "pm_p14"},
    {"astronaut_id": "maria", "name": "Maria", "role": "Mission specialist", "skills": "science;medical", "calibrated_from": "pm_p11"},
]
# (event, who, onset day, episode length)
DEMO_EVENTS = [("infection", "john", 18, 4), ("sleep_disruption", "maria", 21, 6),
               ("co2_buildup", "crew", 25, 2), ("solar_flare", "crew", 27, 1)]


# Task kinds: (demand, skill needed). High-demand tasks need a fit astronaut.
TASK_KINDS = {
    "eva": ("high", "eva"), "robotics": ("high", "robotics"), "maintenance": ("normal", "maintenance"),
    "science": ("normal", "science"), "medical": ("normal", "medical"), "command": ("normal", "command"),
    "pmc": ("normal", "pmc"),       # private medical conference: personal, never reassigned
}
# On the space station each crew member has a weekly private medical conference with the flight surgeon,
# about 15 minutes (NASA podcast "Mission Control: Crew Health Consoles", 2025). One weekday per person here.
PMC_TITLE = "Private medical conference (flight surgeon, 15 min)"


def demo_tasks(days: int = MISSION_DAYS) -> pd.DataFrame:
    """The demo mission's task plan. John's EVA on day 19 falls on his fever; Stefan's EVA on day 27 on the flare.

    The experiment is done in pairs (Maria + a rotating partner), so who worked closely with whom is known:
    John works with Maria on day 17, the day before his fever starts.
    """
    plan = []
    for day in range(1, days + 1):
        plan += [(day, "Daily mission planning", "command", "kenji"),
                 (day, "Experiment run", "science", "maria", ["kenji", "amara", "john"][day % 3]),
                 (day, "Systems maintenance", "maintenance", "stefan" if day % 2 else "john")]
        if day % 3 == 0:
            plan.append((day, "Crew health check", "medical", "amara"))
        for i, member in enumerate(DEMO_CREW):
            if (day - 1) % 7 == i + 1:
                plan.append((day, PMC_TITLE, "pmc", member["astronaut_id"]))
    plan += [(12, "EVA: solar panel inspection", "eva", "john"),
             (19, "EVA: antenna repair", "eva", "john"),
             (19, "Robotic arm: cargo transfer", "robotics", "kenji"),
             (27, "EVA: sensor replacement", "eva", "stefan")]
    rows = []
    for i, (day, title, kind, who, *partner) in enumerate(sorted(plan, key=lambda p: (p[0], p[1]))):
        demand, skill = TASK_KINDS[kind]
        rows.append({"task_id": f"t{i:03d}", "mission_day": day, "title": title, "kind": kind,
                     "demand": demand, "skill": skill, "assignee": who, "partner": partner[0] if partner else ""})
    return pd.DataFrame(rows)


@dataclass
class Person:
    source: str
    mean: dict
    sd: dict
    phi: dict
    exercise: np.ndarray


@dataclass
class Calibration:
    pool: dict                       # person_id -> Person
    mood_per_sleep_hour: float       # within-person slope: next-day mood per hour of extra sleep
    hr_per_sleep_hour: float         # within-person slope: next-day resting pulse per hour of extra sleep
    nhanes: dict = field(default_factory=dict)   # indicator -> (percentiles, values)
    hrv_pool: list = field(default_factory=list)  # LifeSnaps people: (median, spread, persistence) of RMSSD


@dataclass
class Event:
    type: str
    who: str          # astronaut id or "crew"
    onset: int        # first day of the event (1-based)
    length: int

    @property
    def prodrome_start(self) -> int:
        return self.onset - EVENTS[self.type]["prodrome"]

    @property
    def end(self) -> int:
        return self.onset + self.length - 1

    def affects(self, astronaut: str) -> bool:
        return self.who in ("crew", astronaut)


def _daily_grids(daily: pd.DataFrame) -> dict[str, pd.DataFrame]:
    pm = daily[daily["source_dataset"] == "pmdata"].copy()
    pm["date"] = pd.to_datetime(pm["date"])
    return {pid: g.set_index("date").sort_index().asfreq("D") for pid, g in pm.groupby("person_id")}


def calibrate(daily: pd.DataFrame, nhanes_reference: pd.DataFrame) -> Calibration:
    grids = _daily_grids(daily)
    pool = {}
    for pid, g in grids.items():
        if g[FROM_PMDATA].notna().all(axis=1).sum() < POOL_MIN_FULL_DAYS:
            continue
        mean, sd, phi = {}, {}, {}
        for col in ["heart_rate", "sleep_hours", "mood"]:
            x = g[col].astype(float)
            mean[col], sd[col] = float(x.mean()), float(x.std())
            r = x.autocorr(1)
            phi[col] = float(np.clip(r, 0.0, 0.9)) if pd.notna(r) else 0.3
        pool[pid] = Person(pid, mean, sd, phi, g["exercise_min"].dropna().to_numpy(dtype=float))

    # within-person slopes: how last night's sleep (vs the person's mean) moves today's mood and pulse
    num_m = den_m = num_h = den_h = 0.0
    for g in grids.values():
        sleep_prev = (g["sleep_hours"] - g["sleep_hours"].mean()).shift(1)
        mood = g["mood"] - g["mood"].mean()
        hr = g["heart_rate"] - g["heart_rate"].mean()
        ok = sleep_prev.notna() & mood.notna()
        num_m += float((sleep_prev[ok] * mood[ok]).sum())
        den_m += float((sleep_prev[ok] ** 2).sum())
        ok = sleep_prev.notna() & hr.notna()
        num_h += float((sleep_prev[ok] * hr[ok]).sum())
        den_h += float((sleep_prev[ok] ** 2).sum())

    pcts = [0.01, 0.05, 0.50, 0.95, 0.99]
    nh = {r["indicator"]: (pcts, [r["p01"], r["p05"], r["p50"], r["p95"], r["p99"]])
          for _, r in nhanes_reference.iterrows()}
    hrv_pool = []
    ls = daily[(daily["source_dataset"] == "lifesnaps")].copy()
    if "hrv_ms" in ls.columns:
        ls["date"] = pd.to_datetime(ls["date"])
        for _, g in ls.groupby("person_id"):
            x = g.set_index("date").sort_index()["hrv_ms"].astype(float).asfreq("D")
            if x.notna().sum() >= HRV_MIN_DAYS:
                r = x.autocorr(1)
                hrv_pool.append((float(x.median()), float(x.std()), float(np.clip(r, 0.0, 0.9)) if pd.notna(r) else 0.3))
    return Calibration(pool, num_m / den_m, num_h / den_h, nh, hrv_pool)


def _ar1(rng: np.random.Generator, n: int, mu: float, sd: float, phi: float) -> np.ndarray:
    x = np.empty(n)
    x[0] = rng.normal(mu, sd)
    step = sd * np.sqrt(max(1 - phi ** 2, 1e-6))
    for t in range(1, n):
        x[t] = mu + phi * (x[t - 1] - mu) + rng.normal(0, step)
    return x


def _nhanes_level(cal: Calibration, indicator: str, u: float) -> float:
    pcts, values = cal.nhanes[indicator]
    return float(np.interp(u, pcts, values))


def _normal_days(rng, person: Person, cal: Calibration, n: int) -> dict[str, np.ndarray]:
    s = {}
    s["sleep_hours"] = _ar1(rng, n, person.mean["sleep_hours"], person.sd["sleep_hours"], person.phi["sleep_hours"])
    extra_sleep = np.r_[0.0, s["sleep_hours"][:-1] - person.mean["sleep_hours"]]   # last night vs usual
    s["heart_rate"] = (_ar1(rng, n, person.mean["heart_rate"], person.sd["heart_rate"], person.phi["heart_rate"])
                       + cal.hr_per_sleep_hour * extra_sleep)
    s["mood"] = (_ar1(rng, n, person.mean["mood"], person.sd["mood"], person.phi["mood"])
                 + cal.mood_per_sleep_hour * extra_sleep)
    s["exercise_min"] = rng.choice(person.exercise, size=n)
    u_bp, u_glu = rng.uniform(*HEALTHY_BAND, size=2)
    for ind, u in (("bp_sys", u_bp), ("bp_dia", u_bp), ("glucose", u_glu)):   # same rank for both pressures
        a = ASSUMED[ind]
        s[ind] = _ar1(rng, n, _nhanes_level(cal, ind, u), a["sd"], a["phi"])
    t = ASSUMED["temp"]
    s["temp"] = _ar1(rng, n, t["mean"] + rng.normal(0, t["between_people_sd"]), t["sd"], t["phi"])
    return s


def _newer_indicators(rng, cal: Calibration, s: dict[str, np.ndarray], usual_sleep: float) -> None:
    """HRV and reaction time, from their own random stream (rng) so the older indicators stay the same."""
    n = len(s["mood"])
    med, sd, phi = cal.hrv_pool[int(rng.integers(len(cal.hrv_pool)))] if cal.hrv_pool else (40.0, 8.0, 0.3)
    s["hrv_ms"] = _ar1(rng, n, med, sd, phi)
    r = ASSUMED["reaction_ms"]
    short_night = np.r_[0.0, s["sleep_hours"][:-1] - usual_sleep]
    s["reaction_ms"] = (_ar1(rng, n, r["mean"] + rng.normal(0, r["between_people_sd"]), r["sd"], r["phi"])
                        + r["per_sleep_hour"] * short_night)


def _apply(s: dict[str, np.ndarray], effect: dict, days: range) -> None:
    for day in days:
        i = day - 1
        if not 0 <= i < len(s["mood"]):
            continue
        for key, value in effect.items():
            if key == "exercise_factor":
                s["exercise_min"][i] *= value
            else:
                s[key][i] += value


def _finish(s: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {
        "heart_rate": np.round(s["heart_rate"], 1),
        "bp_sys": np.round(s["bp_sys"]), "bp_dia": np.round(s["bp_dia"]),
        "glucose": np.round(s["glucose"]), "temp": np.round(s["temp"], 1),
        "sleep_hours": np.round(np.clip(s["sleep_hours"], 1.0, 13.0), 1),
        "mood": np.clip(np.round(s["mood"]), 1, 5),
        "exercise_min": np.round(np.clip(s["exercise_min"], 0, None)),
        "hrv_ms": np.round(np.clip(s["hrv_ms"], 5.0, None), 1),
        "reaction_ms": np.round(np.clip(s["reaction_ms"], 150.0, None)),
    }


def simulate_mission(mission_id: str, seed: int, crew: list[dict], cal: Calibration,
                     events: list[Event], days: int = MISSION_DAYS, env: str = "mars_base") -> tuple[pd.DataFrame, pd.DataFrame]:
    strength = ENVIRONMENTS[env]["effect"]
    rng = np.random.default_rng(seed)
    rng_new = np.random.default_rng([seed, 1])      # own stream for HRV and reaction time
    rows = []
    for member in crew:
        aid = member["astronaut_id"]
        person = cal.pool[member["calibrated_from"]]
        s = _normal_days(rng, person, cal, days)
        _newer_indicators(rng_new, cal, s, person.mean["sleep_hours"])
        mine = [e for e in events if e.affects(aid)]
        for e in mine:
            spec, k = EVENTS[e.type], strength.get(e.type, 1)
            _apply(s, scaled_effect(spec["prodrome_effect"], k), range(e.prodrome_start, e.onset))
            _apply(s, scaled_effect(spec["episode_effect"], k), range(e.onset, e.end + 1))
        s = _finish(s)
        for day in range(1, days + 1):
            active = [e for e in mine if e.onset <= day <= e.end]
            early = [e for e in mine if e.prodrome_start <= day < e.onset]
            row = {"mission_id": mission_id, "astronaut_id": aid, "mission_day": day,
                   **{ind: float(s[ind][day - 1]) for ind in INDICATORS},
                   "symptoms": ";".join(sorted({x for e in active for x in EVENTS[e.type]["symptoms"]})),
                   "active_events": ";".join(sorted({e.type for e in active})),
                   "event_free": not active and not early,
                   "source": "synthetic"}
            for etype in PREDICTED:
                row[f"label_{etype}_48h"] = int(any(e.type == etype and day < e.onset <= day + HORIZON_DAYS
                                                    for e in mine))
            rows.append(row)
    ev = pd.DataFrame([{"mission_id": mission_id, "event_id": f"{mission_id}-{i}", "type": e.type,
                        "hazard": EVENTS[e.type]["hazard"], "who": e.who, "prodrome_start": e.prodrome_start,
                        "onset_day": e.onset, "end_day": e.end} for i, e in enumerate(events)])
    return pd.DataFrame(rows), ev


def random_events(rng: np.random.Generator, crew_ids: list[str], days: int = MISSION_DAYS,
                  env: str = "mars_base") -> list[Event]:
    out = []
    for etype, spec in EVENTS.items():
        rate = spec["rate"] * ENVIRONMENTS[env]["rate"].get(etype, 1)
        for who in (["crew"] if spec["crew"] else crew_ids):
            for _ in range(rng.poisson(rate)):
                first_onset = EVENT_FREE_DAYS + spec["prodrome"] + 1
                if first_onset > days - 1:
                    continue
                onset = int(rng.integers(first_onset, days))          # leaves at least one day after onset
                length = int(rng.integers(spec["episode"][0], spec["episode"][1] + 1))
                out.append(Event(etype, who, onset, length))
    return out


def demo_mission(cal: Calibration, env: str = "mars_base") -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    events = [Event(t, who, onset, length) for t, who, onset, length in (DEMO_EVENTS_BY_ENV[env] or DEMO_EVENTS)]
    days, ev = simulate_mission("demo", DEMO_SEED, DEMO_CREW, cal, events, env=env)
    return pd.DataFrame(DEMO_CREW), days, ev


def training_missions(cal: Calibration, n: int, seed: int, crew_size: int = 5,
                      env: str = "mars_base") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Many random missions for the model. Each mission draws its crew from the calibration pool."""
    rng = np.random.default_rng(seed)
    pool = sorted(cal.pool)
    all_days, all_events = [], []
    for m in range(n):
        crew = [{"astronaut_id": f"a{i}", "calibrated_from": str(rng.choice(pool))} for i in range(crew_size)]
        events = random_events(rng, [c["astronaut_id"] for c in crew], env=env)
        d, e = simulate_mission(f"m{m:04d}", int(rng.integers(2**31)), crew, cal, events, env=env)
        all_days.append(d)
        all_events.append(e)
    return pd.concat(all_days, ignore_index=True), pd.concat(all_events, ignore_index=True)


def compare_with_real(cal: Calibration, daily: pd.DataFrame, sim_days: pd.DataFrame) -> pd.DataFrame:
    """Median over people of mean, day-to-day spread and persistence: real PMData vs synthetic event-free days."""
    grids = _daily_grids(daily)

    def stats(series_by_person, col):
        means, sds, acs = [], [], []
        for x in series_by_person:
            x = x.astype(float)
            means.append(x.mean())
            sds.append(x.std())
            acs.append(x.autocorr(1))
        return np.nanmedian(means), np.nanmedian(sds), np.nanmedian(acs)

    calm = sim_days.copy()
    for ind in INDICATORS:
        calm.loc[~calm["event_free"], ind] = np.nan
    rows = []
    for col in FROM_PMDATA:
        real = stats([grids[p][col] for p in cal.pool], col)
        sim = stats([g.sort_values("mission_day")[col] for _, g in calm.groupby(["mission_id", "astronaut_id"])], col)
        rows.append({"indicator": col, "real_mean": real[0], "sim_mean": sim[0], "real_spread": real[1],
                     "sim_spread": sim[1], "real_persistence": real[2], "sim_persistence": sim[2]})
    return pd.DataFrame(rows).round(2)
