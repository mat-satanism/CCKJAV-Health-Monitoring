# Can the percentages be trusted? (2026-11-15)

When a model says "10%", the event should happen about 1 time in 10. The app shows risks as "× usual"
(probability / usual rate) and uses 3× (doctors see it) and 5× (CMO to confirm fitness) as lines, so a wrong
probability is a wrong multiple and a wrong alert. Run: `python -m pipeline.calibration` (about 1 minute).

Scores: **ECE** (expected calibration error: the average gap between what the model said and what happened,
weighted by how many days said it; 0 = perfect) and **Brier** (mean squared error of the probability; lower is
better).

## Risk model (simulation): fixed

Trained on 400 missions, scored on 100 new ones. Overall the forest is well calibrated (gap under 1 percentage
point), **but it understates high risks**, a known habit of random forests (they pull probabilities towards the
middle). For a health tool that is the wrong direction:

| Infection, the model said | Happened (raw forest) | Happened (recalibrated, shipped) |
|---|---|---|
| 1-5% | 0.7-2.1% | 1.8-3.1% |
| 30-50% (said 38%) | **65%** | 44% (said 39%) |
| 50-100% (said 55%) | **83%** | 72% (said 62%) |

Fix: a logistic fit on the forest's log-odds per event (Platt scaling), fitted on **100 separate simulated
missions** (seed 99, used for nothing else), stored as `platt: [a, b]` in `models/risk_model.json` and applied in
`pipeline/model.py` before the demo predictions are written. It never changes the order of risks (AUC, PR AUC,
caught/precision stay the same); it only makes the numbers honest.

| Event | ECE raw → shipped | Brier raw → shipped |
|---|---|---|
| Infection | 0.67 → **0.34** pp | 0.0144 → **0.0137** |
| Deconditioning | 0.74 → **0.39** pp | 0.0140 → **0.0134** |
| Low mood | 0.30 → 0.19 pp | 0.0170 → 0.0170 |
| Sleep disruption | 0.35 → 0.34 pp | 0.0277 → 0.0277 |
| CO2 build-up | 0.60 → 0.80 pp | 0.0222 → 0.0222 |

In the demo, John's infection risk on day 16 goes from 22× to 32× usual (still 2 days before the fever);
Maria's sleep risk on day 19 from 5.5× to 5.6×. The false alarms (Maria day 16, Kenji days 20-21, Stefan
days 26-27) stay, at similar multiples. SHAP signs are still computed on the forest itself: they rank and filter
the reasons, they do not add up to the recalibrated risk.

## Wellbeing forecast (real people): already fine, not changed

Each person scored by a model that never saw them.

| Tomorrow | Real rate | Mean predicted | ECE | Brier | Recalibrated (other people): ECE / Brier |
|---|---|---|---|---|---|
| Worse mood | 14.6% | 15.0% | 2.7 pp | 0.1157 | 1.2 pp / 0.1162 |
| Less energy | 25.4% | 25.2% | 3.2 pp | 0.1791 | 3.1 pp / 0.1791 |

Recalibrating would narrow the mood gap but makes the Brier score slightly worse, so it is not worth it: the card's
"× usual" stays as it is.

## Limits

- The risk model is calibrated on the simulation, which is calibrated on real people but is not real astronauts.
- Few days carry high risks (about 100 of 15 000 test days above 50%), so the top bins are noisy.
