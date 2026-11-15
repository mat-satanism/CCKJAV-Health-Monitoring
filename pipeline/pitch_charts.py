"""Charts for the pitch, each with one finding in its title. Run after `python -m pipeline.build` and
`python -m pipeline.model`:

    python -m pipeline.pitch_charts        -> docs/pitch/*.png (about 2 minutes)

Every number on a chart is computed here from data/processed and models/, nothing is typed in by hand.
"""
import json

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

plt.rcParams.update({
    "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 13, "text.color": INK, "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
    "axes.edgecolor": GRID, "axes.facecolor": SURFACE, "figure.facecolor": SURFACE,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
})


def _titles(fig, title: str, subtitle: str, source: str) -> None:
    fig.text(0.04, 0.95, title, fontsize=20, fontweight="bold", va="top")
    fig.text(0.04, 0.885, subtitle, fontsize=13, color=INK_2, va="top")
    fig.text(0.04, 0.03, source, fontsize=10, color=MUTED, va="bottom")


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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    facts = {"own_norm": chart_own_norm(), "early_warning": chart_early_warning()}
    gains = forecast_gains()
    chart_forecast(gains)
    facts["forecast"] = gains.round(3).to_dict(orient="records")
    (OUT / "facts.json").write_text(json.dumps(facts, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(facts, indent=1))


if __name__ == "__main__":
    main()
