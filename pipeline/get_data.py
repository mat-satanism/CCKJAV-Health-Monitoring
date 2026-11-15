"""Download every open dataset into data/raw/ (about 2.1 GB). Files already there are skipped.

    python -m pipeline.get_data            # everything
    python -m pipeline.get_data nhanes     # one dataset
"""
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

from .common import RAW

OSDR = "https://osdr.nasa.gov/geode-py/ws/studies/{}/download?source=datamanager&file={}"
NHANES = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/{}.xpt"
BIGIDEAS = "https://physionet-open.s3.amazonaws.com/big-ideas-glycemic-wearable/1.1.2"

DATASETS = {
    "inspiration4": {
        "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv": OSDR.format(
            "OSD-575", "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv"),
        "LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv": OSDR.format(
            "OSD-575", "LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv"),
        "LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv": OSDR.format(
            "OSD-575", "LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv"),
        "LSDS-8_Multiplex_serum.immune.AlamarPanel_TRANSFORMED.csv": OSDR.format(
            "OSD-575", "LSDS-8_Multiplex_serum.immune.AlamarPanel_TRANSFORMED.csv"),
        "LSDS-7_Complete_Blood_Count_CBC_TRANSFORMED.csv": OSDR.format(
            "OSD-569", "LSDS-7_Complete_Blood_Count_CBC_TRANSFORMED.csv"),
    },
    "nhanes": {f"{n}.xpt": NHANES.format(n) for n in ("DEMO_L", "BPXO_L", "GLU_L", "DIQ_L", "GHB_L")},
    "mmash": {"mmash-1.0.0.zip": "https://physionet-open.s3.amazonaws.com/mmash/mmash-1.0.0.zip"},
    "lifesnaps": {"rais_anonymized.zip": "https://zenodo.org/records/7229547/files/rais_anonymized.zip?download=1"},
    "pmdata": {"pmdata.zip": "https://datasets.simula.no/downloads/pmdata.zip"},
    # Only the glucose sensor files (2 MB), not the wristband recordings.
    "bigideas": {f"Dexcom_{i:03d}.csv": f"{BIGIDEAS}/{i:03d}/Dexcom_{i:03d}.csv" for i in range(1, 17)}
                | {"Demographics.csv": f"{BIGIDEAS}/Demographics.csv"},
}

# From the LifeSnaps archive only the small CSV files are needed (the rest is ~10 GB of MongoDB dumps).
LIFESNAPS_KEEP = ("rais_anonymized/csv_rais_anonymized/", "rais_anonymized/scored_surveys/")


def _extract_lifesnaps(archive: Path) -> None:
    target = archive.parent / "csv"
    target.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            if info.filename.startswith(LIFESNAPS_KEEP) and not info.is_dir():
                (target / Path(info.filename).name).write_bytes(z.read(info))


def download(name: str) -> None:
    folder = RAW / name
    folder.mkdir(parents=True, exist_ok=True)
    for fname, url in DATASETS[name].items():
        path = folder / fname
        if path.exists():
            print(f"skip  {name}/{fname} (already there)")
            continue
        print(f"get   {name}/{fname}")
        tmp = path.with_suffix(path.suffix + ".part")
        urlretrieve(url, tmp)
        tmp.rename(path)
    if name == "lifesnaps" and not (folder / "csv" / "daily_fitbit_sema_df_unprocessed.csv").exists():
        _extract_lifesnaps(folder / "rais_anonymized.zip")
        print("ok    lifesnaps/csv extracted")


def main(names: list[str]) -> None:
    for name in names or DATASETS:
        if name not in DATASETS:
            sys.exit(f"unknown dataset {name!r}; choose from {', '.join(DATASETS)}")
        download(name)


if __name__ == "__main__":
    main(sys.argv[1:])
