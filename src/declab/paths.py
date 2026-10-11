from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"
DATA = ROOT / "data"
RAW = DATA / "raw"
BANK = DATA / "bank"
SESSIONS = DATA / "sessions"
RESULTS = ROOT / "results"
DOCS = ROOT / "docs"
MODELS = ROOT / "models"
VAR = ROOT / "var"
WEB_DIST = ROOT / "web" / "dist"
