#!/usr/bin/env python3
"""Run the continuing Cassi research organism through its durable owner path."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from cassi_research_organism import OrganismError, ResearchOrganism


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--hive-home", type=Path, default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    initialize = sub.add_parser("init", help="create or resume the organism")
    initialize.add_argument("--mission", default="Understand and improve Cassi")
    initialize.add_argument(
        "--member",
        action="append",
        dest="members",
        default=None,
        help="independent member identity; repeat for a population",
    )

    round_parser = sub.add_parser(
        "round",
        help="discover, evaluate, transfer, and publish one population round",
    )
    round_parser.add_argument("--index", type=int, default=None)

    boundary = sub.add_parser(
        "boundaries",
        help="exercise negative transfer and recovery boundaries",
    )
    boundary.add_argument("--index", type=int, default=0)

    sub.add_parser("expand", help="advance one bounded construction expansion")
    sub.add_parser("status", help="inspect canonical root/member state")

    resident = sub.add_parser("resident", help="advance the underlying resident")
    resident.add_argument("--steps", type=int, default=1)

    rollback = sub.add_parser(
        "rollback",
        help="move only the publication pointer; effects remain journaled",
    )
    rollback.add_argument("generation_id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        members = (
            tuple(args.members)
            if args.command == "init" and args.members
            else ("member-000", "member-001")
        )
        organism = ResearchOrganism(
            args.home,
            workspace=args.workspace,
            mission=getattr(args, "mission", "Understand and improve Cassi"),
            member_ids=members,
            hive_home=args.hive_home,
        )
        if args.command == "init":
            result = organism.initialize()
        elif args.command == "round":
            result = organism.run_population_round(args.index)
        elif args.command == "boundaries":
            result = organism.exercise_boundaries(args.index)
        elif args.command == "expand":
            result = organism.expand_frontier()
        elif args.command == "resident":
            result = organism.advance_resident(args.steps)
        elif args.command == "rollback":
            result = organism.rollback(args.generation_id)
        else:
            result = organism.inspect()
        print(_json(result), end="")
        return 0
    except Exception as exc:
        print(
            _json(
                {
                    "schema": "cassifi.research-organism-error.v1",
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "recoverable": isinstance(exc, (OrganismError, OSError)),
                }
            ),
            end="",
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
