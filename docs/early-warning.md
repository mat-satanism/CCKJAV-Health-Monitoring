# Early warning without crying wolf (2026-11-15)

A warning is only useful if it is rare when nothing is wrong. We compared the app's two ways of raising a flag on
100 new simulated missions (717 events, seed never used in training). Run: `python -m pipeline.early_warning`
(about 1 minute); chart: `docs/pitch/8-early-warning-without-crying-wolf.png`.

- **Rules:** any indicator yellow or red that day (Bayesian personal norm and safety limits).
- **Model:** any event risk at 3× the usual level or more (doctors see it), or 5× (the CMO is asked to confirm
  fitness).

| | Flag in the 6 days before a problem | Median days ahead | Flag in a calm week | Flags per calm astronaut-week |
|---|---|---|---|---|
| Rules (any yellow or red) | 96% | 4 | **73%** of astronauts | 1.44 |
| Model, risk ≥ 3× usual | 99% | 4 | **41%** | 0.99 |
| Model, risk ≥ 5× usual | 88% | 3 | **17%** | 0.32 |

Calm week = mission days 10-15, which the simulator keeps free of events and early signs; same 6-day length as the
"before" window, so the two columns compare directly. Numbers above: the raw forest (current `main`). With the
recalibration of `docs/calibration.md` rerun the command; the script uses it automatically.

**What it means.** Both catch nearly every problem ahead of time. The rules also flag almost three astronauts in
four during a week when nothing happens, so their flags carry little information; that is why the app keeps a
yellow as "re-measure, look closer". The model flags a calm week two to four times less often and still warns
3-4 days ahead. **For the judges:** "The model warns as early as simple rules, with far fewer false alarms."

**Why the first look was misleading.** Counting only "days ahead", the rules looked as good or better (4 days).
But with a yellow on about one calm day in five, some yellow falls in almost any 6-day window by chance; the calm
week column is what separates a warning from noise.

## Limits

- Simulated missions only: real data has no labelled events.
- "Days ahead" counts the first flag in the window, which can be a chance flag; read it together with the calm
  week column.
