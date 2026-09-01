"""Filesystem roots shared by the relocated CassiFI runtime and tools."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = ROOT.parent
QWEN_ROOT = WORKSPACE_ROOT / "CassiQwen"
QWEN_MODEL_PATH = QWEN_ROOT / "Qwen3.8-27B-Q4_K_M.gguf"
QWEN_DLL_DIR = QWEN_ROOT
LEGACY_ROOT = ROOT / "legacy" / "flow"
CONFIG_DIR = ROOT / "configs"
DESIGN_DIR = ROOT / "designs"
ARTIFACT_DIR = ROOT / "artifacts"
SCHEMA_DIR = ROOT / "schemas"
