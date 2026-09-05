"""Filesystem roots shared by the relocated CassiFI runtime and tools."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_DIR = ROOT / "configs"
DESIGN_DIR = ROOT / "designs"
ARTIFACT_DIR = ROOT / "artifacts"
SCHEMA_DIR = ROOT / "schemas"
