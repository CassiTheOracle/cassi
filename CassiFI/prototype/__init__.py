"""CassiFI field-intelligence package."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
for _path in (
    ROOT,
    ROOT / "training",
    ROOT / "tests",
    ROOT / "verification",
    ROOT / "runtime",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
