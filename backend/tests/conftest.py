"""Tests never touch the real saved check-ins: point the backend at a temporary file before it is imported."""
import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp())
os.environ["CHN_SAVED_PATH"] = str(_tmp / "checkins.json")
os.environ["CHN_MISSION_SAVED_PATH"] = str(_tmp / "mission_entries.json")
