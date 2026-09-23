from __future__ import annotations

import sys
from pathlib import Path

_TEST_ROOT = Path(__file__).resolve().parent
_CASSIQWEN_ROOT = _TEST_ROOT.parent
_RESEARCH_ROOT = _CASSIQWEN_ROOT / "research"
_BENCHMARK_ROOT = _CASSIQWEN_ROOT / "benchmarks"
# The entity and its resident brain import the field modules directly, so the
# field tree belongs on the path rather than depending on which module happened
# to insert it first.
_CASSIFI_ROOT = _CASSIQWEN_ROOT.parent / "CassiFI"
for _path in (_CASSIQWEN_ROOT, _RESEARCH_ROOT, _BENCHMARK_ROOT, _CASSIFI_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
