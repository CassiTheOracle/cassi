"""Run the frozen L28 field-world-model board once."""

from __future__ import annotations

import argparse
from pathlib import Path

from field_world_model import train_board


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("_diag/l28-field-world-model"))
    args = parser.parse_args()
    board = train_board(args.out_dir)
    print(f"board={args.out_dir / 'l28-board.json'}")
    print(f"field_test_mse={board['arms']['field']['test_mse']:.10g}")
    print(f"stateless_test_mse={board['arms']['stateless']['test_mse']:.10g}")
    print(f"gru_test_mse={board['arms']['gru']['test_mse']:.10g}")
    print(f"field_reset_test_mse={board['arms']['field-reset']['test_mse']:.10g}")
    print(f"field_shuffled_test_mse={board['arms']['field-shuffled']['test_mse']:.10g}")
    print(f"duplicate_match={board['mechanical']['duplicate_match']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
