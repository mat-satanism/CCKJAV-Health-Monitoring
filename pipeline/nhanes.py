"""NHANES 2021-2023 (CDC): population reference ranges for adults aged 20-60.

Percentiles use the NHANES survey weights, so they describe the US adult
population rather than just the people who were sampled.
yellow band = 5th..95th percentile, red band = 1st..99th percentile.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from .common import RAW

DIR = RAW / "nhanes"
AGE_MIN, AGE_MAX = 20, 60
PERCENTILES = [1, 5, 50, 95, 99]
SOURCE = "NHANES 2021-2023, CDC (DEMO_L, BPXO_L, GLU_L)"


def weighted_percentiles(values, weights, percentiles=PERCENTILES) -> list[float]:
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    keep = ~np.isnan(v) & ~np.isnan(w) & (w > 0)
    v, w = v[keep], w[keep]
    order = np.argsort(v)
    v, w = v[order], w[order]
    cum = (np.cumsum(w) - 0.5 * w) / w.sum()  # midpoint of each value's weight
    return [float(np.interp(p / 100, cum, v)) for p in percentiles]


def _read(name: str, directory: Path) -> pd.DataFrame:
    return pd.read_sas(directory / f"{name}.xpt", format="xport")


def reference(demo: pd.DataFrame, bp: pd.DataFrame, glu: pd.DataFrame) -> pd.DataFrame:
    adults = demo.loc[demo["RIDAGEYR"].between(AGE_MIN, AGE_MAX), ["SEQN", "WTMEC2YR"]]

    # Three readings in a row; use each person's mean.
    bp = bp.assign(
        bp_sys=bp[["BPXOSY1", "BPXOSY2", "BPXOSY3"]].mean(axis=1),
        bp_dia=bp[["BPXODI1", "BPXODI2", "BPXODI3"]].mean(axis=1),
        heart_rate=bp[["BPXOPLS1", "BPXOPLS2", "BPXOPLS3"]].mean(axis=1),
    ).merge(adults, on="SEQN")
    # Fasting glucose has its own subsample weight.
    glu = glu.merge(adults[["SEQN"]], on="SEQN")

    rows = []
    for ind, unit, frame, wcol in [
        ("bp_sys", "mmHg", bp, "WTMEC2YR"),
        ("bp_dia", "mmHg", bp, "WTMEC2YR"),
        ("heart_rate", "bpm", bp, "WTMEC2YR"),
        ("glucose", "mg/dL", glu.rename(columns={"LBXGLU": "glucose"}), "WTSAF2YR"),
    ]:
        data = frame[[ind, wcol]].dropna()
        data = data[data[wcol] > 0]
        p = weighted_percentiles(data[ind], data[wcol])
        rows.append({"indicator": ind, "unit": unit, "n": len(data),
                     **{f"p{q:02d}": round(x, 1) for q, x in zip(PERCENTILES, p)},
                     "age_range": f"{AGE_MIN}-{AGE_MAX}", "weight": wcol, "source": SOURCE})
    return pd.DataFrame(rows)


def load(directory: Path = DIR) -> pd.DataFrame:
    return reference(_read("DEMO_L", directory), _read("BPXO_L", directory), _read("GLU_L", directory))
