"""Copy what the app needs to the Hugging Face Space; the Space builds the Dockerfile and serves the site.

Run by .github/workflows/deploy-space.yml after every merge to main. Needs two settings in the GitHub repo:
- secret HF_TOKEN: a Hugging Face access token with write access;
- variable HF_SPACE: "<hf-user-or-org>/<space-name>", e.g. "my-team/crew-health-navigator".
The Space is created on the first run if it does not exist yet.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Only what the Dockerfile copies: no raw data, no pipeline, no pitch images.
PARTS = ["Dockerfile", ".dockerignore", "backend/requirements.txt", "backend/app", "frontend", "data/thresholds.json",
         "data/content", "data/synthetic", "data/processed", "models"]
SKIP = shutil.ignore_patterns("node_modules", "dist", ".vite", "__pycache__", "*.pyc", ".env*")

SPACE_CARD = """---
title: Crew Health Navigator
emoji: 🩺
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: Astronaut health monitoring with a personal norm (demo)
---

Crew Health Navigator, NASA Space Apps Challenge 2026. Simulated crew mission calibrated on real data, and
30 real days of one public-dataset participant. Not real astronauts, not medical advice.

Source code: https://github.com/{repo}
"""


def stage(folder: Path) -> None:
    """Put the files the Space needs, and its card, into `folder`."""
    for part in PARTS:
        src, dst = ROOT / part, folder / part
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, ignore=SKIP)
        else:
            shutil.copy2(src, dst)
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    (folder / "README.md").write_text(SPACE_CARD.format(repo=repo), encoding="utf-8")


def main() -> None:
    if "--dry-run" in sys.argv:   # show what would be uploaded, upload nothing
        with tempfile.TemporaryDirectory() as tmp:
            stage(Path(tmp))
            files = [f for f in Path(tmp).rglob("*") if f.is_file()]
            print(f"{len(files)} files, {sum(f.stat().st_size for f in files) / 1e6:.1f} MB")
        return
    from huggingface_hub import HfApi

    space, token = os.environ["HF_SPACE"], os.environ["HF_TOKEN"]
    api = HfApi(token=token)
    # private=False on purpose: the site must be open to everyone, and a private Space needs a paid plan (HTTP 402)
    api.create_repo(space, repo_type="space", space_sdk="docker", exist_ok=True, private=False)
    with tempfile.TemporaryDirectory() as tmp:
        stage(Path(tmp))
        api.upload_folder(folder_path=tmp, repo_id=space, repo_type="space", delete_patterns="*",
                          commit_message=f"Deploy {os.environ.get('GITHUB_SHA', 'local')[:7]}")
    print(f"Deployed to https://huggingface.co/spaces/{space}")


if __name__ == "__main__":
    main()
