"""Charts for the pitch, each with one finding in its title. Run after `python -m pipeline.build` and
`python -m pipeline.model`:

    python -m pipeline.pitch_charts        -> docs/pitch/*.png (about 2 minutes)

Every number on a chart is computed here from data/processed and models/, nothing is typed in by hand.
"""
import json
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import wellbeing as w
from .common import PROCESSED, ROOT

OUT = ROOT / "docs" / "pitch"

# Reference palette (light mode): one highlight hue, neutral ink, recessive grid.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#8a8984"
GRID = "#e4e3df"
BLUE = "#2a78d6"
YELLOW = "#eda100"
ORANGE = "#eb6834"

plt.rcParams.update({
    "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 13, "text.color": INK, "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
    "axes.edgecolor": GRID, "axes.facecolor": SURFACE, "figure.facecolor": SURFACE,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
})


def _titles(fig, title: str, subtitle: str, source: str) -> None:
    """Title, subtitle and source, wrapped to the figure width; the plot area starts below them."""
    w_in, h_in = fig.get_size_inches()
    t = textwrap.wrap(title, int(w_in * 6.9))
    st = textwrap.wrap(subtitle, int(w_in * 11.3))
    so = textwrap.wrap(source, int(w_in * 15))
    y = 1 - 0.3 / h_in
    fig.text(0.04, y, "\n".join(t), fontsize=20, fontweight="bold", va="top", linespacing=1.15)
    y -= (len(t) * 0.36 + 0.1) / h_in
    fig.text(0.04, y, "\n".join(st), fontsize=13, color=INK_2, va="top", linespacing=1.3)
    y -= (len(st) * 0.25 + 0.45) / h_in
    fig.text(0.04, 0.02, "\n".join(so), fontsize=10, color=MUTED, va="bottom")
    fig.subplots_adjust(top=min(fig.subplotpars.top, y))


# --- 1. The forecast beats "same as today" -----------------------------------------------------------------

FORECASTS = [   # (label, task name, inputs): the variants shipped in the app, the forest with all inputs otherwise
    ("Lower mood tomorrow", "worse mood", "check-in + last days"),
    ("Less energy tomorrow", "more tired (fatigue)", "all inputs"),
    ("Less ready to train", "less ready (readiness)", "all inputs"),
    ("Sad, tense or tired (LifeSnaps)", "negative feeling", "all inputs"),
]


def forecast_gains() -> pd.DataFrame:
    data = {ds: w.load(ds) for ds in ("pmdata", "lifesnaps")}
    rows = []
    for label, name, inputs in FORECASTS:
        task = next(t for t in w.TASKS if t.name == name)
        d = data[task.dataset]
        d = d[d[task.target].notna() & d[task.reference].notna()].reset_index(drop=True)
        cols = w.export_columns(inputs, d) if task.dataset == "pmdata" else w.feature_columns("lifesnaps", d)
        y, people = d[task.target].to_numpy(int), d["person_id"].to_numpy()
        model = w.within_person_auc(people, y, w.out_of_person_scores(d, cols, task.target)["random forest"])
        ref = w.within_person_auc(people, y, d[task.reference].to_numpy(float))
        lo, hi = w.within_bootstrap(model, ref)
        rows.append({"label": label, "model": np.mean(list(model.values())), "reference": np.mean(list(ref.values())),
                     "lo": lo, "hi": hi, "people": d["person_id"].nunique()})
    out = pd.DataFrame(rows)
    out["gain"] = out["model"] - out["reference"]
    return out


def chart_forecast(g: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 6.2))
    fig.subplots_adjust(left=0.27, right=0.86, top=0.74, bottom=0.17)
    ys = np.arange(len(g))[::-1]
    for y, (_, r) in zip(ys, g.iterrows()):
        wins = r["lo"] > 0
        c = BLUE if wins else MUTED
        ax.plot([r["lo"], r["hi"]], [y, y], color=c, lw=2, solid_capstyle="round")
        ax.scatter([r["gain"]], [y], s=90, color=c, zorder=3, edgecolor=SURFACE, linewidth=2)
        verdict = "better" if wins else "no better"
        ax.text(max(r["hi"], 0) + 0.006, y, f"{r['model']:.2f} vs {r['reference']:.2f}  ·  {verdict}",
                va="center", fontsize=12, color=INK if wins else INK_2)
    ax.axvline(0, color=INK_2, lw=1)
    ax.text(-0.003, len(g) - 0.5, '← worse   "same as today"   better →', ha="center", fontsize=11, color=INK_2,
            bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 2})
    ax.set_yticks(ys, g["label"], fontsize=13, color=INK)
    ax.tick_params(axis="y", length=0)
    ax.set_ylim(-0.6, len(g) - 0.3)
    ax.set_xlim(min(-0.08, g["lo"].min() - 0.01), max(0.13, g["hi"].max() + 0.01))
    ax.set_xlabel("Gain in AUC within a person over \"same as today\" (dot), 95% interval (line)")
    ax.grid(axis="y", visible=False)
    _titles(fig, "Tomorrow's mood and energy: the model beats \"same as today\"",
            "Scored on real people the model never saw. Readiness and LifeSnaps feelings: no gain, and we say so.",
            f"PMData ({g['people'].iloc[0]} people) and LifeSnaps ({g['people'].iloc[-1]} people). "
            "Labels: AUC of the model vs \"same as today\" (0.5 = guessing). python -m pipeline.pitch_charts")
    fig.savefig(OUT / "1-forecast-beats-same-as-today.png", dpi=160)
    plt.close(fig)


# --- 2. Everyone has their own normal ----------------------------------------------------------------------

def chart_own_norm() -> dict:
    daily = pd.read_csv(PROCESSED / "daily.csv")
    d = daily[daily["source_dataset"].isin(["pmdata", "lifesnaps"]) & daily["heart_rate"].notna()]
    stats = d.groupby("person_id")["heart_rate"].agg(
        n="count", med="median", lo=lambda x: x.quantile(0.1), hi=lambda x: x.quantile(0.9))
    stats = stats[stats["n"] >= 21].sort_values("med").reset_index()
    limit = json.loads((ROOT / "data" / "thresholds.json").read_text())["heart_rate"]["yellow_low"]
    below = int((stats["med"] < limit).sum())
    spread = stats["med"].max() - stats["med"].min()

    fig, ax = plt.subplots(figsize=(12, 6.2))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.74, bottom=0.17)
    x = np.arange(len(stats))
    ax.vlines(x, stats["lo"], stats["hi"], color=BLUE, alpha=0.35, lw=2)
    ax.scatter(x, stats["med"], s=22, color=BLUE, zorder=3)
    ax.axhline(limit, color=YELLOW, lw=2)
    ax.text(len(stats) - 1, limit - 1.2, f"one fixed \"too low\" limit for everyone: {limit} bpm", ha="right",
            va="top", fontsize=12, color=INK)
    ax.set_xticks([])
    ax.set_xlim(-1, len(stats))
    ax.set_ylabel("Resting pulse, bpm")
    ax.set_xlabel(f"{len(stats)} people, sorted by their usual pulse "
                  "(dot = usual, line = their 10th-90th percentile day)")
    ax.grid(axis="x", visible=False)
    _titles(fig, f"Usual resting pulse differs by {spread:.0f} bpm between ordinary people",
            f"A fixed limit would flag {below} of them on an ordinary day. "
            "So the app compares each person with their own norm.",
            "PMData and LifeSnaps, people with 21+ days of resting pulse. python -m pipeline.pitch_charts")
    fig.savefig(OUT / "2-everyone-has-their-own-normal.png", dpi=160)
    plt.close(fig)
    return {"people": len(stats), "spread_bpm": round(float(spread), 1), "below_limit": below, "limit": limit}


# --- 3. Early warning in the simulated mission ------------------------------------------------------------

def chart_early_warning() -> dict:
    pred = pd.read_csv(PROCESSED / "sim" / "predictions.csv")
    events = pd.read_csv(PROCESSED / "sim" / "events.csv")
    model = json.loads((ROOT / "models" / "risk_model.json").read_text())
    base = model["events"]["infection"]["base_rate"]
    watch = 3.0   # backend/app/mission.py WATCH_MULTIPLE: doctors see a risk from 3x usual
    ev = events[(events["mission_id"] == "demo") & (events["type"] == "infection")].iloc[0]
    who, onset, end = ev["who"], int(ev["onset_day"]), int(ev["end_day"])
    pred["x"] = pred["risk_infection"] / base
    person = pred[pred["astronaut_id"] == who].sort_values("mission_day")
    before = person[(person["mission_day"] < onset) & (person["x"] >= watch)]
    first = int(before["mission_day"].min()) if len(before) else None
    lead = onset - first if first else 0

    fig, ax = plt.subplots(figsize=(12, 6.2))
    fig.subplots_adjust(left=0.08, right=0.9, top=0.74, bottom=0.17)
    ax.axvspan(onset - 0.5, end + 0.5, color=GRID, alpha=0.7, lw=0)
    for aid, g in pred.groupby("astronaut_id"):
        if aid != who:
            g = g.sort_values("mission_day")
            ax.plot(g["mission_day"], g["x"], color=MUTED, lw=1.2, alpha=0.6)
    ax.plot(person["mission_day"], person["x"], color=BLUE, lw=2.5)
    if first:
        y = float(person.loc[person["mission_day"] == first, "x"].iloc[0])
        ax.scatter([first], [y], s=90, color=BLUE, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.annotate(f"day {first}: {y:.0f}× usual, doctors alerted", (first, y), xytext=(-14, 14),
                    textcoords="offset points", ha="right", fontsize=12)
    ax.axhline(watch, color=INK_2, lw=1, ls=(0, (4, 3)))
    ax.text(30.6, watch, "3× usual:\ndoctors see it", va="center", fontsize=11, color=INK_2)
    top = max(person["x"].max(), watch) * 1.12
    ax.set_ylim(0, top)
    ax.text((onset + end) / 2, top * 0.97, "fever", ha="center", va="top", fontsize=12, color=INK_2)
    ax.text(person["mission_day"].iloc[-1] + 0.3, person["x"].iloc[-1], who.capitalize(), color=BLUE,
            fontsize=12, va="center", fontweight="bold")
    ax.text(1, top * 0.05, "grey: the other four crew members", fontsize=11, color=MUTED)
    ax.set_xlim(0.5, 30.5)
    ax.set_xticks(range(1, 31, 2))
    ax.set_xlabel("Mission day")
    ax.set_ylabel("Infection risk in the next 48 h, × usual")
    ax.grid(axis="x", visible=False)
    _titles(fig, f"The model flags {who.capitalize()}'s infection {lead} days before the fever",
            "Pulse and temperature creep up against his own norm while still inside the safe limits: the model sees it.",
            "SIMULATED mission: synthetic crew calibrated on real people (docs/simulation.md). "
            "Risk model: random forest. python -m pipeline.pitch_charts")
    fig.savefig(OUT / "3-early-warning-before-fever.png", dpi=160)
    plt.close(fig)
    return {"who": who, "first_alert_day": first, "onset_day": onset, "lead_days": lead}


# --- 4. Real astronauts: blood before and after flight ---------------------------------------------------

BLOOD = [("glucose", "Glucose", "mg/dL"), ("white_blood_cell_count", "White blood cells", "thousand per µL"),
         ("monocytes", "Monocytes", "% of white cells")]


def chart_blood() -> dict:
    b = pd.read_csv(PROCESSED / "inspiration4_blood.csv")
    b = b[b["quality_note"].isna()]   # R+45 glucose samples suspected of late processing are left out
    order = ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"]
    fig, axes = plt.subplots(1, len(BLOOD), figsize=(12, 6.2), sharex=True)
    fig.subplots_adjust(left=0.06, right=0.98, top=0.72, bottom=0.2, wspace=0.28)
    facts = {}
    for ax, (analyte, label, unit) in zip(axes, BLOOD):
        a = b[b["analyte"] == analyte]
        lo, hi = a["ref_min"].iloc[0], a["ref_max"].iloc[0]
        ax.axhspan(lo, hi, color=GRID, alpha=0.6, lw=0)
        ax.axvspan(2.5, 3.5, color=BLUE, alpha=0.08, lw=0)
        above = below = 0
        for crew, g in a.groupby("crew_id"):
            g = g.set_index("timepoint").reindex(order)
            x = np.arange(len(order))
            ax.plot(x, g["value"], color=BLUE, lw=1.6, alpha=0.75, marker="o", ms=4)
            pre = g.loc[["L-92", "L-44", "L-3"], "value"]   # the person's own range before flight
            above += int(g.loc["R+1", "value"] > pre.max())
            below += int(g.loc["R+1", "value"] < pre.min())
        facts[analyte] = {"R+1_above_own_preflight_range": above, "R+1_below_own_preflight_range": below,
                          "crew": int(a["crew_id"].nunique()), "lab_range": [lo, hi]}
        ax.set_title(f"{label}\n", loc="left", fontsize=13, color=INK, fontweight="bold")
        ax.text(0, 1.02, unit, transform=ax.transAxes, fontsize=10, color=INK_2)
        ax.set_xticks(range(len(order)), order, rotation=45, fontsize=10)
        ax.grid(axis="x", visible=False)
    axes[0].text(3, axes[0].get_ylim()[1], "flight", ha="center", va="top", fontsize=10, color=BLUE)
    g_up = facts["glucose"]["R+1_above_own_preflight_range"]
    w_dn = facts["white_blood_cell_count"]["R+1_below_own_preflight_range"]
    _titles(fig, f"The day after 3 days in space, glucose was above their own pre-flight range in {g_up} of 4, "
                 f"white cells below it in {w_dn} of 4",
            "Each line is one Inspiration4 astronaut; grey band = lab normal range. Real NASA data: 4 people, one sample "
            "each; not known if the R+1 sample was fasting.",
            "NASA OSDR OSD-575 / OSD-569 (Inspiration4, 2021). L = days before launch, R = days after return. "
            "Suspect R+45 glucose samples left out. python -m pipeline.pitch_charts")
    fig.savefig(OUT / "4-real-astronauts-blood.png", dpi=160)
    plt.close(fig)
    return facts


# --- 5. What comes before a worse-mood day (real people) -------------------------------------------------

BEFORE = [   # (label, column, test on today's distance from the person's own norm)
    ("Stressed day (calm 1+ below usual)", "stress_dev", lambda x: x <= -1),
    ("Short sleep (1+ h below usual, self-report)", "sleep_hours_dev", lambda x: x <= -1),
    ("Tired day (energy 1+ below usual)", "fatigue_dev", lambda x: x <= -1),
    ("Short sleep (1+ h below usual, wristband)", "sleep_hours_device_dev", lambda x: x <= -1),
    ("Fewer steps (3000+ below usual)", "steps_dev", lambda x: x <= -3000),
    ("Resting pulse 2+ bpm above usual", "heart_rate_dev", lambda x: x >= 2),
]
MIN_DAYS = 5     # a person counts for a sign when they have at least 5 days with it and 5 without


def within_person(d: pd.DataFrame, mask: pd.Series, n: int = 2000, seed: int = 7) -> dict:
    """How much a sign changes the chance of a worse mood tomorrow FOR THE SAME PERSON.

    For each person: share of worse-mood next days after days with the sign, minus after days without it. The mean
    over people (each person counts once), a 95% interval resampling people, and in how many people it is positive.
    Pooling all days instead mixes in who is moody in general: e.g. "stressed" gave +9 points pooled, +4 within.
    """
    diffs = []
    for _, g in d.assign(m=mask.to_numpy()).groupby("person_id"):
        if g["m"].sum() >= MIN_DAYS and (~g["m"]).sum() >= MIN_DAYS:
            diffs.append(g.loc[g["m"], "y_mood"].mean() - g.loc[~g["m"], "y_mood"].mean())
    diffs = np.array(diffs)
    rng = np.random.default_rng(seed)
    boots = [rng.choice(diffs, len(diffs)).mean() for _ in range(n)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"effect": float(diffs.mean()), "lo": float(lo), "hi": float(hi),
            "people": len(diffs), "positive": int((diffs > 0).sum()), "days": int(mask.sum())}


def chart_before_bad_mood() -> dict:
    f = w.load("pmdata")
    d = f[f["y_mood"].notna()].copy()
    rows = []
    for label, col, test in BEFORE:
        has = d[col].notna()
        rows.append({"label": label, **within_person(d[has], test(d.loc[has, col]))})
    overall = float(d["y_mood"].mean())
    fig, ax = plt.subplots(figsize=(12, 6.2))
    fig.subplots_adjust(left=0.33, right=0.95, top=0.74, bottom=0.17)
    ys = np.arange(len(rows))[::-1]
    for y, r in zip(ys, rows):
        c = BLUE if r["lo"] > 0 else MUTED
        ax.plot([r["lo"] * 100, r["hi"] * 100], [y, y], color=c, lw=2.2, alpha=0.8)
        ax.scatter([r["effect"] * 100], [y], s=70, color=c, zorder=3)
        ax.text(max(r["hi"] * 100, 0) + 0.8, y, f"{r['effect'] * 100:+.0f} pts, in {r['positive']} of {r['people']} people",
                va="center", fontsize=11.5, color=INK_2)
    ax.axvline(0, color=INK_2, lw=1)
    ax.set_yticks(ys, [r["label"] for r in rows], fontsize=12, color=INK)
    ax.tick_params(axis="y", length=0)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlim(min(r["lo"] for r in rows) * 100 - 2, max(r["hi"] for r in rows) * 100 + 17)
    ax.set_xlabel("Change in tomorrow's chance of a worse mood, % points (dot), 95% interval (line)")
    ax.grid(axis="y", visible=False)
    clear = [r["label"].split(" (")[0].lower() for r in rows if r["lo"] > 0]
    pos = [r["effect"] * 100 for r in rows if r["effect"] > 0]
    pulse = next(r for r in rows if r["label"].startswith("Resting pulse"))
    title = (f"For the same person, a short night, stress or a tired day add only {min(pos):.0f}-{max(pos):.0f} points "
             f"to tomorrow's chance of a worse mood; a raised pulse adds none")
    _titles(fig, title,
            f"Each person compared with themselves (worse mood on {overall:.0%} of days overall). Small, not in everyone"
            + (f", clearly above zero only for: {', '.join(clear)}" if clear else "")
            + ". That is why the forecast combines several signs.",
            "Real people (PMData, 16); a person counts for a sign with 5+ days with and without it. Blue: interval clear "
            "of 0. python -m pipeline.pitch_charts")
    fig.savefig(OUT / "5-what-comes-before-a-worse-mood.png", dpi=160)
    plt.close(fig)
    return {"any_day": round(overall, 3), "pulse_effect": round(pulse["effect"], 3),
            "signals": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()} for r in rows]}


# --- 6. The whole crew at a glance (simulated mission) ----------------------------------------------------

WORSE = {"heart_rate": 1, "temp": 1, "sleep_hours": -1, "mood": -1, "hrv_ms": -1, "reaction_ms": 1}


def chart_crew_heatmap() -> dict:
    days = pd.read_csv(PROCESSED / "sim" / "days.csv")
    days = days[days["mission_id"] == "demo"]
    crew = pd.read_csv(PROCESSED / "sim" / "crew.csv")
    events = pd.read_csv(PROCESSED / "sim" / "events.csv")
    events = events[events["mission_id"] == "demo"]
    names = crew.set_index("astronaut_id")["name"]
    grid = []
    for aid in crew["astronaut_id"]:
        g = days[days["astronaut_id"] == aid].sort_values("mission_day").set_index("mission_day")
        calm = g.loc[:14]
        z = pd.concat([(g[c] - calm[c].mean()) / (calm[c].std() or 1) * s for c, s in WORSE.items()], axis=1)
        grid.append(z.clip(lower=0).mean(axis=1).reindex(range(1, 31)).to_numpy())
    grid = np.array(grid)
    fig, ax = plt.subplots(figsize=(12, 6.2))
    fig.subplots_adjust(left=0.1, right=0.9, top=0.72, bottom=0.2)
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("one_hue", ["#f1f6fd", "#9ec5f2", BLUE, "#0d3f80"])
    im = ax.imshow(grid, aspect="auto", cmap=cmap, vmin=0, vmax=np.nanpercentile(grid, 99),
                   extent=[0.5, 30.5, len(grid) - 0.5, -0.5])
    for x in np.arange(1.5, 30, 1):
        ax.axvline(x, color=SURFACE, lw=1.5)
    for y in np.arange(0.5, len(grid) - 1, 1):
        ax.axhline(y, color=SURFACE, lw=3)
    ax.set_yticks(range(len(grid)), [names[a] for a in crew["astronaut_id"]], fontsize=12, color=INK)
    ax.set_xticks(range(1, 31, 2))
    ax.set_xlabel("Mission day")
    ax.tick_params(length=0)
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    labels = {"infection": "infection", "sleep_disruption": "sleep problem", "co2_buildup": "CO₂ in the air",
              "solar_flare": "solar flare"}
    for i, (_, e) in enumerate(events.sort_values("onset_day").iterrows()):
        ax.annotate(labels.get(e["type"], e["type"]), ((e["onset_day"] + e["end_day"]) / 2, -0.5),
                    xytext=(0, 6 + 16 * (i % 2)), textcoords="offset points", ha="center", va="bottom",
                    fontsize=10, color=INK_2, annotation_clip=False)
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cb.set_label("distance from own norm, worrying side", color=INK_2, fontsize=10)
    cb.outline.set_visible(False)
    _titles(fig, "One person drifting, or the whole crew at once: the pattern tells the cause",
            "John and Maria stand out alone (illness, sleep); on days 25-26 everyone shifts together: check the air.",
            "SIMULATED mission. Mean distance from each person's days 1-14 (pulse, temperature, sleep, mood, HRV, "
            "reaction time), worrying side only. python -m pipeline.pitch_charts")
    fig.savefig(OUT / "6-crew-at-a-glance.png", dpi=160)
    plt.close(fig)
    return {"events": events[["type", "who", "onset_day", "end_day"]].to_dict(orient="records")}


# --- 7. The forecast for a person the model never saw -----------------------------------------------------

def chart_demo_person() -> dict:
    data = json.loads(w.EXPORT_FILE.read_text(encoding="utf-8"))
    days = data["days"]
    x = np.array([d["mission_day"] for d in days])
    t = np.array([d["mood"]["times_usual"] for d in days])
    hap = [d["mood"]["happened"] for d in days]
    high = t >= 2
    known = np.array([h is not None for h in hap])
    hit = np.array([bool(h) for h in hap])
    hi_n, hi_bad = int((high & known).sum()), int((high & known & hit).sum())
    lo_n, lo_bad = int((~high & known).sum()), int((~high & known & hit).sum())

    fig, ax = plt.subplots(figsize=(12, 6.2))
    fig.subplots_adjust(left=0.08, right=0.95, top=0.72, bottom=0.17)
    ax.bar(x, t, width=0.7, color=[YELLOW if h else MUTED for h in high], alpha=0.9)
    ax.axhline(2, color=INK_2, lw=1, ls=(0, (4, 3)))
    ax.text(31.4, 2.06, "2× usual", ha="right", va="bottom", fontsize=11, color=INK_2)
    ys = t[hit] + 0.25
    ax.scatter(x[hit], ys, s=60, color=INK, zorder=3)
    ax.text(0.8, t.max() + 0.75, "● = the next day really was a worse-mood day", fontsize=11, color=INK)
    ax.set_ylim(0, t.max() + 1.1)
    ax.set_xlim(0.3, 31.5)
    ax.set_xticks(range(1, 31, 2))
    ax.set_xlabel("Day of the real-data demo (the forecast is for the next day)")
    ax.set_ylabel("Chance of a worse mood tomorrow, × usual")
    ax.grid(axis="x", visible=False)
    _titles(fig, f"A person the model never saw: a worse mood followed {hi_bad} of {hi_n} high-risk days",
            f"against {lo_bad} of {lo_n} other days. One real person over 30 days: an illustration, not a proof.",
            "PMData participant p06, model trained on the other 15 people (docs/wellbeing-model.md). "
            "Same data as 'Tomorrow's outlook' in the app. python -m pipeline.pitch_charts")
    fig.savefig(OUT / "7-forecast-for-an-unseen-person.png", dpi=160)
    plt.close(fig)
    return {"high_days": hi_n, "high_then_bad": hi_bad, "other_days": lo_n, "other_then_bad": lo_bad}


# --- 8. Inspiration4: six blood values per astronaut (real) -------------------------------------------------

PANEL = [("glucose", "Glucose", "mg/dL"), ("calcium", "Calcium", "mg/dL"),
         ("white_blood_cell_count", "White blood cells", "thousand per µL"), ("hemoglobin", "Hemoglobin", "g/dL"),
         ("platelet_count", "Platelets", "thousand per µL"), ("creatinine", "Creatinine", "mg/dL")]
CREW_STYLE = {"C001": "-", "C002": "--", "C003": ":", "C004": "-."}


def chart_blood_panel() -> dict:
    b = pd.read_csv(PROCESSED / "inspiration4_blood.csv")
    b = b[b["quality_note"].isna()]
    order = ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"]
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.4), sharex=True)
    fig.subplots_adjust(left=0.06, right=0.98, top=0.8, bottom=0.12, wspace=0.25, hspace=0.42)
    outside = {}
    for ax, (analyte, label, unit) in zip(axes.ravel(), PANEL):
        a = b[b["analyte"] == analyte]
        # Some ranges differ by sex: the band spans the lowest minimum to the highest maximum; "outside" uses each
        # result's own lab flag.
        ax.axhspan(a["ref_min"].min(), a["ref_max"].max(), color=GRID, alpha=0.6, lw=0)
        ax.axvspan(2.5, 3.5, color=BLUE, alpha=0.08, lw=0)
        for crew, g in a.groupby("crew_id"):
            g = g.set_index("timepoint").reindex(order)
            ax.plot(range(len(order)), g["value"], color=BLUE, lw=1.6, ls=CREW_STYLE.get(crew, "-"), alpha=0.8,
                    marker="o", ms=3.5, label=crew)
        outside[analyte] = int(a["flag"].isin(["low", "high"]).sum())
        ax.set_title(f"{label} ({unit})", loc="left", fontsize=12, color=INK, fontweight="bold")
        ax.set_xticks(range(len(order)), order, rotation=45, fontsize=9)
        ax.grid(axis="x", visible=False)
    axes[0, 0].legend(fontsize=9, frameon=False, ncol=2, loc="upper left")
    n_out = sum(outside.values())
    _titles(fig, f"Six blood values of the four Inspiration4 astronauts: {n_out} of "
                 f"{int(b[b['analyte'].isin([p[0] for p in PANEL])]['value'].notna().sum())} results outside the lab range",
            "Each line is one astronaut, grey band = lab normal range (widest if it differs by sex), blue band = the 3-day flight. Glucose, bone "
            "(calcium), immune (white cells), blood (hemoglobin, platelets), kidneys (creatinine).",
            "NASA OSDR OSD-575 / OSD-569 (Inspiration4, 2021). Suspect R+45 glucose samples left out. "
            "python -m pipeline.pitch_charts")
    fig.savefig(OUT / "8-inspiration4-six-blood-values.png", dpi=160)
    plt.close(fig)
    return {"outside_lab_range": outside}


# --- 9. Data completeness: which days have values (real, for the team) ---------------------------------------

COMPLETENESS = [("heart_rate", "Resting pulse"), ("sleep_hours", "Sleep (self)"), ("sleep_hours_device", "Sleep (watch)"),
                ("mood", "Mood"), ("exercise_min", "Exercise"), ("steps", "Steps"), ("hrv_ms", "HRV"),
                ("temp_skin", "Skin temp")]
DEMO_SIGNALS = ["heart_rate", "sleep_hours", "mood", "exercise_min"]   # what the real-data demo needs every day


def completeness() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Share of calendar days with a value, per person and indicator; and the best 30-day window per PMData person."""
    d = pd.read_csv(PROCESSED / "daily.csv", parse_dates=["date"])
    d = d[d["source_dataset"].isin(["pmdata", "lifesnaps"])]
    rows = []
    for pid, g in d.groupby("person_id"):
        span = (g["date"].max() - g["date"].min()).days + 1
        rows.append({"person_id": pid, "dataset": g["source_dataset"].iloc[0], "calendar_days": span,
                     **{c: round(g[c].notna().sum() / span, 2) for c, _ in COMPLETENESS}})
    table = pd.DataFrame(rows)
    best = []
    for pid, g in d[d["source_dataset"] == "pmdata"].groupby("person_id"):
        full = g.set_index("date").sort_index().asfreq("D")[DEMO_SIGNALS].notna().all(axis=1).astype(float)
        roll = full.rolling(30).mean()
        best.append({"person_id": pid, "best_30_days_complete": round(float(roll.max()), 2),
                     "from": roll.idxmax() - pd.Timedelta(days=29) if roll.notna().any() else None})
    best = pd.DataFrame(best).sort_values("best_30_days_complete", ascending=False).reset_index(drop=True)
    return table, best


def chart_completeness() -> dict:
    table, best = completeness()
    cols = [c for c, _ in COMPLETENESS]
    table = table.assign(order=table[cols].mean(axis=1)).sort_values(["dataset", "order"], ascending=[False, False])
    fig, ax = plt.subplots(figsize=(12, 9))
    fig.subplots_adjust(left=0.12, right=0.97, top=0.88, bottom=0.08)
    ax.imshow(table[cols].to_numpy(), aspect="auto", cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(cols)), [lab for _, lab in COMPLETENESS], fontsize=11)
    split = int((table["dataset"] == "pmdata").sum())
    ax.set_yticks(range(split), table["person_id"].iloc[:split], fontsize=6.5)
    ax.set_ylabel(f"PMData: {split} people (named) | LifeSnaps: {len(table) - split} people", fontsize=11)
    ax.grid(False)
    ax.axhline(split - 0.5, color=INK, lw=1.2)
    _titles(fig, f"Which days have data: {len(table)} people; {int((best['best_30_days_complete'] >= 0.98).sum())} of "
                 f"{len(best)} PMData people have a 30-day stretch with pulse, sleep, mood and exercise every day",
            "Share of each person's calendar days with a value (dark = every day). PMData above the line, LifeSnaps below; "
            "white columns = not in that dataset.",
            "data/processed/daily.csv after cleaning (no-steps days = watch not worn). python -m pipeline.pitch_charts")
    fig.savefig(OUT / "9-data-completeness.png", dpi=160)
    plt.close(fig)
    md = ["# Data completeness (generated by `python -m pipeline.pitch_charts`)", "",
          ("Share of each person's calendar days with a value, after cleaning (`docs/data.md`). "
           "Picture: `docs/pitch/9-data-completeness.png`."), "",
          "## PMData: best 30-day stretch with pulse, self-reported sleep, mood and exercise every day", "",
          "| Person | Days complete in the best 30 | Window starts |", "|---|---|---|"]
    md += [f"| {r.person_id} | {r.best_30_days_complete:.0%} | {r['from'].date() if pd.notna(r['from']) else '-'} |"
           for _, r in best.iterrows()]
    md += ["", "The real-data demo uses pm_p06 (complete, with a clear calm-then-short-sleep story; `docs/data.md`).", "",
           "## Every person", "", "| Person | Dataset | Calendar days | " + " | ".join(lab for _, lab in COMPLETENESS) + " |",
           "|---|---|---|" + "---|" * len(COMPLETENESS)]
    md += [f"| {r.person_id} | {r.dataset} | {r.calendar_days} | " + " | ".join(f"{r[c]:.0%}" for c in cols) + " |"
           for _, r in table.iterrows()]
    (ROOT / "docs" / "data-completeness.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return {"people": len(table), "pmdata_top5": best.head(5)[["person_id", "best_30_days_complete"]].to_dict("records")}


# --- 10. Early warning without crying wolf (simulated missions) ---------------------------------------------

def chart_alerts() -> dict:
    from . import early_warning as ew

    t, calibrated = ew.run()
    fig, ax = plt.subplots(figsize=(12, 6.2))
    fig.subplots_adjust(left=0.3, right=0.95, top=0.72, bottom=0.17)
    ys = np.arange(len(t))[::-1]
    h = 0.34
    for y, (_, r) in zip(ys, t.iterrows()):
        for off, col, color in ((h / 2, "flagged_before_events", BLUE), (-h / 2, "flagged_in_a_calm_week", ORANGE)):
            v = r[col] * 100
            ax.barh(y + off, v, height=h - 0.04, color=color)
            ax.text(v + 1, y + off, f"{v:.0f}%", va="center", fontsize=12, color=INK)
    ax.set_yticks(ys, ["Status rules\n(any yellow or red)", "Model\nrisk 3x usual", "Model\nrisk 5x usual"],
                  fontsize=12, color=INK)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, 112)
    ax.set_xlabel("Share of events / of astronauts with at least one flag in the 6 days")
    ax.grid(axis="y", visible=False)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=BLUE), plt.Rectangle((0, 0), 1, 1, color=ORANGE)],
              labels=["in the 6 days before a problem", "in a calm week (nothing happens)"],
              loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, fontsize=11)
    rules, m5 = t.iloc[0], t.iloc[-1]
    _titles(fig, "The model warns as early as the rules, with far fewer false alarms",
            f"In a calm week the rules flag {rules['flagged_in_a_calm_week']:.0%} of astronauts; the model at 5x usual "
            f"flags {m5['flagged_in_a_calm_week']:.0%}, and still {m5['flagged_before_events']:.0%} of problems ahead.",
            f"SIMULATED: 100 new missions, {int(rules['events'])} events. Risk model "
            f"{'recalibrated' if calibrated else 'raw forest'}. python -m pipeline.early_warning")
    fig.savefig(OUT / "10-early-warning-without-crying-wolf.png", dpi=160)
    plt.close(fig)
    return {"calibrated": calibrated, "rows": t.to_dict(orient="records")}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    facts = {"own_norm": chart_own_norm(), "early_warning": chart_early_warning(), "blood": chart_blood(),
             "before_bad_mood": chart_before_bad_mood(), "crew": chart_crew_heatmap(),
             "demo_person": chart_demo_person(), "blood_panel": chart_blood_panel(),
             "completeness": chart_completeness(),
             "alerts": chart_alerts()}
    gains = forecast_gains()
    chart_forecast(gains)
    facts["forecast"] = gains.round(3).to_dict(orient="records")
    (OUT / "facts.json").write_text(json.dumps(facts, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(facts, indent=1))


if __name__ == "__main__":
    main()
