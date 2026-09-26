"""Run the third disjoint real A-A-B-B chronological holdout.

The field implementation and release protocol remain unchanged.  This wrapper
binds the campaign to a third receipt-backed source trio and preserves the
previous campaign receipts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import run_generation2_real_chronological_holdout as base


base.SCHEMA = "cassifi.generation2-real-chronological-holdout-pair3.v1"
base.SLICE_SCHEMA = "cassifi.generation2-real-chronological-holdout-pair3-slice.v1"
base.EXPERIMENT_ID = "generation2-real-chronological-holdout-pair3-v1"
base.OUTPUT = "CassiFI/_diag/generation2-real-chronological-holdout-pair3-v1.json"
base.DEVELOPMENT_ROOT = (
    "CassiCosmos/_diag/matter_formation/attractor_scene_calibrated/GC2"
)
base.REGIME_A_ROOT = "CassiCosmos/_diag/matter_formation/attractor_scene_calibrated/G3"
base.REGIME_B_ROOT = "CassiCosmos/_diag/matter_formation/attractor_scene_calibrated/G6"
base.ANALYSIS_SOURCES = tuple(
    sorted(
        set(base.ANALYSIS_SOURCES)
        | {"CassiFI/run_generation2_real_chronological_holdout_pair3.py"}
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
