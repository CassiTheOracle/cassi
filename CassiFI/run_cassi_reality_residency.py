from __future__ import annotations

"""Run the integrated Cassi Reality Residency against port 7599."""

import argparse
import json
from pathlib import Path
from typing import Sequence

from cassi_reality_residency import run_reality_residency


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Learn field-owned physical laws from fresh CassiCosmos worlds, "
            "then test sealed transfer, control, restart retention, and lesion."
        )
    )
    parser.add_argument("--run-id", default="reality-residency-v4")
    parser.add_argument(
        "--home",
        type=Path,
        help="Evidence home (default: _diag/reality_residency/<run-id>)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7599)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    home = (
        arguments.home
        if arguments.home is not None
        else Path("_diag") / "reality_residency" / arguments.run_id
    )
    receipt = run_reality_residency(
        home,
        run_id=arguments.run_id,
        host=arguments.host,
        port=arguments.port,
    )
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "receipt": str((home / "receipt.json").resolve()),
                "body_sha256": receipt["body_sha256"],
                "summary": receipt["summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if receipt["status"] == "supported" else 2


if __name__ == "__main__":
    raise SystemExit(main())
