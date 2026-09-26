"""Run the second disjoint real A-A-B-B chronological holdout.

The field implementation and protocol are the same as the first real campaign;
only the receipt-backed source trio changes.  This wrapper keeps the first
campaign receipt immutable while binding this run to a separate source set.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import run_generation2_real_chronological_holdout as base


base.SCHEMA = "cassifi.generation2-real-chronological-holdout-pair2.v1"
base.SLICE_SCHEMA = "cassifi.generation2-real-chronological-holdout-pair2-slice.v1"
base.EXPERIMENT_ID = "generation2-real-chronological-holdout-pair2-v1"
base.OUTPUT = "CassiFI/_diag/generation2-real-chronological-holdout-pair2-v1.json"
base.DEVELOPMENT_ROOT = (
    "CassiCosmos/_diag/matter_formation/energy_gaussian_s20260910_v0p5"
)
base.REGIME_A_ROOT = "CassiCosmos/_diag/matter_formation/attractor_ic2"
base.REGIME_B_ROOT = "CassiCosmos/_diag/matter_formation/attractor_ic7"
base.ANALYSIS_SOURCES = tuple(
    sorted(
        set(base.ANALYSIS_SOURCES)
        | {"CassiFI/run_generation2_real_chronological_holdout_pair2.py"}
    )
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    output = (args.out or workspace / base.OUTPUT).resolve()
    result = base.run(workspace)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(base._canonical(result) + b"\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "aggregate": result["aggregate"],
                "receipt": str(output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
