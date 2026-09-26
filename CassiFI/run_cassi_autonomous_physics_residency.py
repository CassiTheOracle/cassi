from __future__ import annotations

"""Run the continuing autonomous physics residency against CassiCosmos."""

import argparse
import json
from pathlib import Path
from typing import Sequence

from cassi_autonomous_physics_residency import run_autonomous_physics_residency


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Let the resident field originate representations, experiment "
            "languages, research programs, and bounded mechanism resolutions "
            "across scheduled nonlinear worlds."
        )
    )
    parser.add_argument("--run-id", default="autonomous-field-research-program-v8")
    parser.add_argument(
        "--home",
        type=Path,
        help=(
            "Evidence home (default: "
            "_diag/autonomous_physics_residency/<run-id>)"
        ),
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7599)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    home = (
        arguments.home
        if arguments.home is not None
        else Path("_diag") / "autonomous_physics_residency" / arguments.run_id
    )
    receipt = run_autonomous_physics_residency(
        home,
        run_id=arguments.run_id,
        host=arguments.host,
        port=arguments.port,
    )
    print(
        json.dumps(
            {
                "body_sha256": receipt["body_sha256"],
                "receipt": str((home / "receipt.json").resolve()),
                "status": receipt["status"],
                "summary": receipt["summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if receipt["status"] == "supported" else 2


if __name__ == "__main__":
    raise SystemExit(main())
