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
SOURCE = "NHANES 2021-2023, CDC (DEMO_L, BPXO_L, BPQ_L, GLU_L, DIQ_L, GHB_L)"


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


HBA1C_DIABETES = 6.5  # %, HbA1c at or above this counts as (undiagnosed) diabetes


def without_diabetes(glu: pd.DataFrame, diq: pd.DataFrame, ghb: pd.DataFrame) -> pd.DataFrame:
    """Drop people told by a doctor they have diabetes (DIQ010 == 1) or with HbA1c >= 6.5%.

    Astronauts are selected healthy, so their reference is the population without diabetes.
    Including diabetes pushes the 99th percentile of fasting glucose from 128 to 310 mg/dL.
    """
    g = glu.merge(diq[["SEQN", "DIQ010"]], on="SEQN", how="left").merge(ghb[["SEQN", "LBXGH"]], on="SEQN", how="left")
    healthy = (g["DIQ010"] != 1) & (g["LBXGH"] < HBA1C_DIABETES)
    return g.loc[healthy, glu.columns]


def without_hypertension(bp: pd.DataFrame, bpq: pd.DataFrame) -> pd.DataFrame:
    """Drop people a doctor has told they have high blood pressure (BPQ020 == 1); this includes everyone on
    blood-pressure medicine (BPQ150 is asked only of them).

    Same reason as for diabetes: astronauts are selected healthy. Measured high values are kept: undiagnosed people
    stay, so the upper percentiles are not cut by hand.
    """
    told = bpq.loc[bpq["BPQ020"] == 1, "SEQN"]
    return bp[~bp["SEQN"].isin(told)]


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
    for ind, unit, frame, wcol, population in [
        ("bp_sys", "mmHg", bp, "WTMEC2YR", "adults without diagnosed high blood pressure"),
        ("bp_dia", "mmHg", bp, "WTMEC2YR", "adults without diagnosed high blood pressure"),
        ("heart_rate", "bpm", bp, "WTMEC2YR", "adults without diagnosed high blood pressure"),
        ("glucose", "mg/dL", glu.rename(columns={"LBXGLU": "glucose"}), "WTSAF2YR", "adults without diabetes"),
    ]:
        data = frame[[ind, wcol]].dropna()
        data = data[data[wcol] > 0]
        p = weighted_percentiles(data[ind], data[wcol])
        rows.append({"indicator": ind, "unit": unit, "n": len(data),
                     **{f"p{q:02d}": round(x, 1) for q, x in zip(PERCENTILES, p)},
                     "age_range": f"{AGE_MIN}-{AGE_MAX}", "population": population,
                     "weight": wcol, "source": SOURCE})
    return pd.DataFrame(rows)


def load(directory: Path = DIR) -> pd.DataFrame:
    glu = without_diabetes(_read("GLU_L", directory), _read("DIQ_L", directory), _read("GHB_L", directory))
    bp = without_hypertension(_read("BPXO_L", directory), _read("BPQ_L", directory))
    return reference(_read("DEMO_L", directory), bp, glu)
