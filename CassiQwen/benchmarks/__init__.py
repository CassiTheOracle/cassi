"""CassiQwen benchmark and workcase entrypoints."""

from __future__ import annotations

import sys
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent
_CASSIQWEN_ROOT = _PACKAGE_ROOT.parent
for _path in (_CASSIQWEN_ROOT, _PACKAGE_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
