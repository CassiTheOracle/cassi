"""Throwaway: does the learned mode bank change the real op's readout?

Runs the native field through ``NativeLlamaSession.graph_trial`` (real llama.cpp
context, real Cassi Qi op) on the 0.8B, seeding one nonzero field state and then
replaying it under each read configuration.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))

from cassi_llama_capture import (  # noqa: E402
    NativeLlamaSession,
    write_zero_state,
    _read_f32,
)

RUNTIME = ROOT / "native" / "llama.cpp" / "b8-learn" / "bin" / "Release"
MODEL = ROOT / "Qwen3.5-0.8B-Q4_0.gguf"
BANK = ROOT / "_diag" / "field-bank" / "measured-32.bin"
OUT = ROOT / "_diag" / "bank-effect"
LAYER = 12
PROMPT = "Cassi field memory probe: the resonant pond remembers the stone."

ARMS = {
    "ramp-normalized": dict(read_absolute=False, unwritten_latch=False, mode_bank=None),
    "bank-normalized": dict(read_absolute=False, unwritten_latch=False, mode_bank=BANK),
    "ramp-absolute": dict(read_absolute=True, unwritten_latch=False, mode_bank=None),
    "bank-absolute": dict(read_absolute=True, unwritten_latch=False, mode_bank=BANK),
    "bank-absolute-latch": dict(read_absolute=True, unwritten_latch=True, mode_bank=BANK),
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    seed_dir = OUT / "seed"
    if not seed_dir.is_dir():
        write_zero_state(OUT / "zero.f32")
        with NativeLlamaSession(RUNTIME, MODEL, gpu_layers=0, context_tokens=256) as session:
            result = session.graph_trial(
                prompt=PROMPT,
                sequence_id="bank-effect",
                state_path=OUT / "zero.f32",
                output_dir=seed_dir,
                layer=LAYER,
                displacement=0,
                injection_scale=1.0,
                substitute=0.0,
                capture_id="bank-effect-seed",
            )
        print(f"seed state-after written, {len(result['receipt']['state_successor']['path'])} bytes")

    seed_state = seed_dir / "state-after.f32"
    seed_values = _read_f32(seed_state, elements=4 * 9 * 6144)
    print(f"seed state: |x| = {float(np.linalg.norm(seed_values)):.6f} "
          f"max = {float(np.max(np.abs(seed_values))):.6e} "
          f"nonzero = {int(np.count_nonzero(seed_values))}")

    receipts: dict[str, dict] = {}
    finals: dict[str, np.ndarray] = {}
    states: dict[str, np.ndarray] = {}
    for name, knobs in ARMS.items():
        arm_dir = OUT / name
        if arm_dir.is_dir():
            receipt = json.loads((arm_dir / "graph-trial-receipt.json").read_text(encoding="utf-8"))
        else:
            with NativeLlamaSession(RUNTIME, MODEL, gpu_layers=0, context_tokens=256) as session:
                result = session.graph_trial(
                    sequence_id="bank-effect",
                    prompt=PROMPT,
                    state_path=seed_state,
                    output_dir=arm_dir,
                    layer=LAYER,
                    displacement=0,
                    injection_scale=1.0,
                    substitute=0.0,
                    capture_id=f"bank-effect-{name}",
                    **knobs,
                )
            receipt = result["receipt"]
        receipts[name] = receipt
        finals[name] = _read_f32(arm_dir / "logits.f32", elements=int(receipt["logits"]["elements"]))
        states[name] = _read_f32(arm_dir / "state-after.f32", elements=int(receipt["state_successor"]["elements"]))
        bank = receipt["configuration"]["mode_bank"]
        print(f"{name:22s} state|dx| vs seed = {float(np.linalg.norm(states[name] - seed_values)):.6f} "
              f"bank = {None if bank is None else (bank['damping_min'], bank['damping_max'])}")

    print()
    names = list(ARMS)
    print(f"{'pair':45s} {'logits max|d|':>14s} {'logits KL':>12s} {'state max|d|':>14s} {'state rel':>12s}")
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            dl = float(np.max(np.abs(finals[left] - finals[right])))
            a = np.exp(finals[left] - finals[left].max())
            b = np.exp(finals[right] - finals[right].max())
            a /= a.sum()
            b /= b.sum()
            kl = float(np.sum(a * np.log((a + 1e-12) / (b + 1e-12))))
            ds = float(np.max(np.abs(states[left] - states[right])))
            base = max(float(np.linalg.norm(states[left])), 1e-30)
            rel = float(np.linalg.norm(states[left] - states[right])) / base
            print(f"{left + ' vs ' + right:45s} {dl:14.6e} {kl:12.6e} {ds:14.6e} {rel:12.6e}")

    print()
    seam_dir = OUT / "seam-check"
    if not seam_dir.is_dir():
        with NativeLlamaSession(RUNTIME, MODEL, gpu_layers=0, context_tokens=256) as session:
            result = session.graph_trial(
                sequence_id="bank-effect",
                prompt=PROMPT,
                state_path=seed_state,
                output_dir=seam_dir,
                layer=LAYER,
                displacement=3,
                injection_scale=0.0,
                substitute=1.0,
                capture_id="bank-effect-seam",
                read_absolute=True,
                mode_bank=BANK,
                row_width=1024,
                memory_fill=True,
            )
    seam = json.loads((seam_dir / "graph-trial-receipt.json").read_text(encoding="utf-8"))
    graph = seam["graph"]
    print(f"seam: field_width={graph['qi_state_field_width']} row_width={graph['qi_state_row_width']} "
          f"write_owner={graph['qi_state_write_owner']} logits_max={float(np.max(np.abs(_read_f32(seam_dir / 'logits.f32', elements=int(seam['logits']['elements']))))):.4f}")

    (OUT / "summary.json").write_text(json.dumps({
        "arms": {name: receipts[name]["configuration"] for name in names},
        "seed_state_norm": float(np.linalg.norm(seed_values)),
        "state_norms": {name: float(np.linalg.norm(states[name])) for name in names},
        "state_nonzero": {name: int(np.count_nonzero(states[name])) for name in names},
    }, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
