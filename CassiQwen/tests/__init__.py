"""CassiQwen tests kept outside the live field-brain runtime root."""

from __future__ import annotations

import sys
from pathlib import Path

_TEST_ROOT = Path(__file__).resolve().parent
_CASSIQWEN_ROOT = _TEST_ROOT.parent
_RESEARCH_ROOT = _CASSIQWEN_ROOT / "research"
_BENCHMARK_ROOT = _CASSIQWEN_ROOT / "benchmarks"
for _path in (_CASSIQWEN_ROOT, _RESEARCH_ROOT, _BENCHMARK_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
