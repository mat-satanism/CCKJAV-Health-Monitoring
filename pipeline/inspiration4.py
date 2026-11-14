"""Inspiration4 blood tests (NASA OSDR OSD-575 and OSD-569): 4 crew, 7 timepoints.

Output is long: one row per crew member, timepoint and analyte, with the lab's
reference range next to the value.
"""
import re
from pathlib import Path

import pandas as pd

from .common import RAW

DIR = RAW / "inspiration4"
PANELS = {
    "cmp": "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv",
    "cbc": "LSDS-7_Complete_Blood_Count_CBC_TRANSFORMED.csv",
}
# Cytokine panels (Eve, Alamar) are not processed: the meaning of their
# `_percent` columns is not documented.

# value / range_min / range_max columns; ALT and AST spell their max as `_max_`.
COLUMN = re.compile(r"^(?P<analyte>.+?)_(?P<kind>value|range_min|range_max|max)(?:_(?P<unit>.+))?$")
# The CBC file labels hemoglobin as "percent", but the values (about 12-17) are g/dL.
UNIT_FIX = {("hemoglobin", "percent"): "gram_per_deciliter"}


def parse_sample(name: str) -> dict:
    """'C001_serum_L-3' -> crew C001, timepoint L-3, -3 days, pre-flight."""
    parts = name.split("_")
    crew, timepoint = parts[0], parts[2]
    pre = timepoint.startswith("L")
    return {
        "crew_id": crew,
        "timepoint": timepoint,
        # L-n = n days before launch; R+n = n days after return.
        "days_from_flight": int(timepoint[1:]),
        "phase": "pre-flight" if pre else "post-flight",
    }


def tidy(raw: pd.DataFrame, panel: str) -> pd.DataFrame:
    long = raw.melt(id_vars="Sample Name", var_name="column", value_name="number")
    parts = long["column"].str.extract(COLUMN)
    if parts["analyte"].isna().any():
        bad = long.loc[parts["analyte"].isna(), "column"].unique().tolist()
        raise ValueError(f"unexpected columns in {panel}: {bad}")
    long = pd.concat([long, parts], axis=1)
    long["kind"] = long["kind"].replace({"max": "range_max"})
    long["number"] = pd.to_numeric(long["number"], errors="coerce")  # "N/A" -> empty

    wide = long.pivot_table(index=["Sample Name", "analyte"], columns="kind", values="number", aggfunc="first")
    wide = wide.reindex(columns=["value", "range_min", "range_max"]).reset_index()
    units = long[long["kind"] == "value"].drop_duplicates("analyte").set_index("analyte")["unit"]
    wide["unit"] = wide["analyte"].map(units)
    wide["unit"] = [UNIT_FIX.get((a, u), u) for a, u in zip(wide["analyte"], wide["unit"])]

    meta = pd.DataFrame([parse_sample(s) for s in wide["Sample Name"]])
    out = pd.concat([meta, wide.drop(columns="Sample Name")], axis=1)
    out.insert(0, "panel", panel)
    out = out.rename(columns={"range_min": "ref_min", "range_max": "ref_max"})
    out["flag"] = "normal"
    out.loc[out["value"] < out["ref_min"], "flag"] = "low"
    out.loc[out["value"] > out["ref_max"], "flag"] = "high"
    out.loc[out["value"].isna(), "flag"] = pd.NA
    return out


def load(directory: Path = DIR) -> pd.DataFrame:
    frames = [tidy(pd.read_csv(directory / f, encoding="utf-8-sig"), p) for p, f in PANELS.items()]
    df = pd.concat(frames, ignore_index=True)
    return df.sort_values(["panel", "analyte", "crew_id", "days_from_flight", "phase"]).reset_index(drop=True)
