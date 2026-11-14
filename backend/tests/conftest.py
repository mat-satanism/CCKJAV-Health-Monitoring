"""Tests never touch the real saved check-ins: point the backend at a temporary file before it is imported."""
import os
import tempfile
from pathlib import Path

os.environ["CHN_SAVED_PATH"] = str(Path(tempfile.mkdtemp()) / "checkins.json")
