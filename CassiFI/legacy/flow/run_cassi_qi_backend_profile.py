"""CLI entry point for the measured W14B backend profiler."""
from __future__ import annotations

from cassi_qi_backend_profile import main, run

__all__ = ["main", "run"]


if __name__ == "__main__":
    raise SystemExit(main())
