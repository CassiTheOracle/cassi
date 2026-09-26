"""Run the adopted two-symbol chromatic recall profile."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassi_ordered_relational_field import (
    ORDERED_RELATIONAL_LAYOUT_PROFILE_ID,
    ORDERED_RELATIONAL_OPERATOR_PROFILE_ID,
    ORDERED_RELATIONAL_PROJECTION_PROFILE_ID,
    OrderedRelationalChromaticFieldConfig,
    OrderedRelationalChromaticFieldController,
    OrderedRelationalChromaticReadout,
)

RUNTIME_SCHEMA = "cassi.adopted-chromatic-recall-runtime.v1"
MODE_COUNT = 2048
EVOLUTION_STEPS = 8


def recall_sequence(
    symbols: Sequence[int], *, device: str | torch.device = "cpu"
) -> dict[str, Any]:
    """Deposit symbols into one field and expose its current/predecessor slots."""
    if not symbols:
        raise ValueError("symbols must not be empty")
    for symbol in symbols:
        if isinstance(symbol, bool) or not isinstance(symbol, int):
            raise TypeError("symbols must contain integers")
        if not 0 <= symbol < 260:
            raise ValueError("symbols must be in [0, 260)")

    target_device = torch.device(device)
    controller = OrderedRelationalChromaticFieldController(
        OrderedRelationalChromaticFieldConfig(mode_count=MODE_COUNT)
    )
    state = controller.new_state(device=target_device, dtype=torch.float32)
    receipts: list[dict[str, Any]] = []
    for index, symbol in enumerate(symbols):
        tick = controller.tick(
            state,
            symbols=(symbol,),
            steps=EVOLUTION_STEPS,
            trust=1.0,
        )
        state = tick.state
        readout = cast(OrderedRelationalChromaticReadout, tick.readout)
        current = int(readout.current_symbols.item())
        relational = int(readout.relational_symbols.item())
        has_predecessor = bool(readout.relational_available.item()) and (
            relational != current
        )
        predecessor = relational if has_predecessor else None
        receipts.append(
            {
                "tick": index,
                "input_symbol": symbol,
                "current_symbol": current,
                "predecessor_symbol": predecessor,
                "current_score": float(readout.scores[0, current].item()),
                "predecessor_score": (
                    float(readout.scores[0, relational].item())
                    if has_predecessor
                    else None
                ),
                "available": bool(readout.available.item()),
                "predecessor_available": has_predecessor,
                "white_coherence": float(readout.white_coherence.item()),
                "clamp_count": tick.clamp_count,
            }
        )

    return {
        "schema_id": RUNTIME_SCHEMA,
        "status": "ok",
        "layout_profile_id": ORDERED_RELATIONAL_LAYOUT_PROFILE_ID,
        "operator_profile_id": ORDERED_RELATIONAL_OPERATOR_PROFILE_ID,
        "projection_profile_id": ORDERED_RELATIONAL_PROJECTION_PROFILE_ID,
        "config_fingerprint": controller.config_fingerprint,
        "device": str(target_device),
        "dtype": "float32",
        "mode_count": MODE_COUNT,
        "field_shape": list(state.field.shape),
        "receipts": receipts,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbols", nargs="+", type=int, help="Symbols in [0, 260).")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--torch-threads", type=int, default=1)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    if arguments.torch_threads < 1:
        raise SystemExit("--torch-threads must be positive")
    torch.set_num_threads(arguments.torch_threads)
    print(
        json.dumps(
            recall_sequence(arguments.symbols, device=arguments.device),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
