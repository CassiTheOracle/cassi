#!/usr/bin/env python3
"""Run the persistent Cassi research residency.

The residency is restartable: ``run`` advances one durable field phase at a
time, while ``status`` reads the current owner image without advancing it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from cassi_research_residency import (
    DEFAULT_MISSION,
    ResidencyError,
    open_research_residency,
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, required=True, help="persistent residency directory")
    parser.add_argument("--workspace", type=Path, default=Path.cwd(), help="workspace to study")
    parser.add_argument("--hive-home", type=Path, default=None)
    parser.add_argument("--import-skills", action="store_true")
    parser.add_argument("--export-skills", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="create or verify a residency")
    init.add_argument("--mission", default=DEFAULT_MISSION)
    run = sub.add_parser("run", help="advance bounded durable research phases")
    run.add_argument("--steps", type=int, default=1)
    sub.add_parser("status", help="inspect the resident field without advancing")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "init":
            with open_research_residency(args.home, hive_home=args.hive_home,
                                         import_skills=args.import_skills,
                                         export_skills=args.export_skills) as residency:
                residency.initialize(workspace=args.workspace, mission=args.mission)
                result = residency.inspect()
        elif args.command == "run":
            if args.steps < 1 or args.steps > 128:
                raise ResidencyError("--steps must be between 1 and 128")
            with open_research_residency(args.home, hive_home=args.hive_home,
                                         import_skills=args.import_skills,
                                         export_skills=args.export_skills) as residency:
                # Initialization is explicit so a typo cannot silently create a
                # new mission while a previous home is unavailable.
                if not (args.home / "field").exists():
                    raise ResidencyError("residency is not initialized; run init first")
                result = residency.inspect()
                for _ in range(args.steps):
                    result = residency.advance()
        else:
            with open_research_residency(args.home, hive_home=args.hive_home,
                                         import_skills=args.import_skills,
                                         export_skills=args.export_skills) as residency:
                if not (args.home / "field").exists():
                    raise ResidencyError("residency is not initialized; run init first")
                result = residency.inspect()
        print(_json(result), end="")
        return 0
    except Exception as exc:
        print(_json({"schema": "cassifi.research-residency-error.v1",
                     "status": "error", "error": str(exc),
                     "recoverable": True}), end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
