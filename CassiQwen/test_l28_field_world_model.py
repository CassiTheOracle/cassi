"""Focused tests for L28 evidence-integrity rejection paths."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from verify_l28_field_world_model import verify


ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "_diag" / "l28-field-world-model"


def _temporary_board() -> tuple[tempfile.TemporaryDirectory[str], Path, dict]:
    temporary = tempfile.TemporaryDirectory(dir=ROOT)
    directory = Path(temporary.name)
    for name in ("l28-manifest.json", "l28-field.pt"):
        shutil.copy2(SOURCE_DIR / name, directory / name)
    board = json.loads((SOURCE_DIR / "l28-board.json").read_text(encoding="utf-8"))
    board_path = directory / "l28-board.json"
    board_path.write_text(json.dumps(board), encoding="utf-8")
    return temporary, board_path, board


def test_tampered_metric_is_rejected() -> None:
    temporary, board_path, board = _temporary_board()
    try:
        board["arms"]["field"]["test_mse"] = 999.0
        board_path.write_text(json.dumps(board), encoding="utf-8")
        verdict, payload = verify(board_path, board_path.with_name("tampered-metric.md"))
        assert verdict == "FAIL"
        assert "replayed field metric differs from board" in payload["failures"]
    finally:
        temporary.cleanup()


def test_non_sibling_checkpoint_path_is_rejected() -> None:
    temporary, board_path, board = _temporary_board()
    try:
        board["checkpoint"]["path"] = str(SOURCE_DIR / "l28-field.pt")
        board_path.write_text(json.dumps(board), encoding="utf-8")
        verdict, payload = verify(board_path, board_path.with_name("tampered-path.md"))
        assert verdict == "FAIL"
        assert "candidate checkpoint path is not the board sibling" in payload["failures"]
    finally:
        temporary.cleanup()


if __name__ == "__main__":
    test_tampered_metric_is_rejected()
    test_non_sibling_checkpoint_path_is_rejected()
    print("L28 verifier tamper tests passed")
