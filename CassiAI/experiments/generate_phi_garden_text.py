#!/usr/bin/env python3
"""Generate text from trained φ-Garden Brain (byte mode)."""

import torch
import torch.nn.functional as F
import numpy as np
import argparse

from cassi.phi_garden import PhiGardenBrain
from cassi.cord import PHI

DEV = 'cuda'
CKPT_PATH = 'phi_garden_text.pt'
SPINE_PATH = 'cord_simulator_phi_latest.pt'


def clean_bytes(b):
    """Replace non-printable with · for display."""
    return ''.join(chr(c) if 32 <= c < 127 else '·' for c in b)


def generate_samples(garden, seed_bytes, n_tokens=256, temperature=0.8):
    """Autoregressive byte generation.

    Strategy: predict next field, decode to bytes, feed back as new seed.
    Since decode_field is approximate, we do sliding-window with
    field-level prediction (predict next window, decode it, append).
    """
    window = garden.spine.byte_encoder.window_bytes
    stride = garden.spine.byte_encoder.chunk  # bytes per timestep

    generated = bytearray(seed_bytes)
    current = torch.tensor(list(seed_bytes), dtype=torch.uint8, device=DEV).unsqueeze(0)

    garden.eval()
    with torch.no_grad():
        for _ in range(n_tokens // stride):
            garden.reset_workspace(1)
            pred_field, info = garden(current, use_memory=True, return_workspace=True)

            # Decode predicted field to bytes
            pred_bytes = garden.spine.byte_encoder.decode_field_greedy(pred_field)

            # Take first 'stride' bytes as the next generated chunk
            next_chunk = pred_bytes[:stride]
            generated.extend(next_chunk)

            # Slide window: drop first stride bytes, append predicted chunk
            current = torch.tensor(
                list(generated[-window:]), dtype=torch.uint8, device=DEV
            ).unsqueeze(0)

    return generated


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ckpt', default=CKPT_PATH)
    parser.add_argument('--seed', default='Once upon a time,')
    parser.add_argument('--length', type=int, default=512)
    parser.add_argument('--temperature', type=float, default=0.8)
    parser.add_argument('--n-samples', type=int, default=5)
    args = parser.parse_args()

    print(f"Loading model from {args.ckpt}...")
    garden = PhiGardenBrain(
        D=1040, n_specialists=5, n_slots=512,
        memory_value_dim=26, readout_hidden=520,
        byte_mode=True
    ).to(DEV)

    garden.load_spine(SPINE_PATH)

    ckpt = torch.load(args.ckpt, map_location=DEV, weights_only=False)
    state_dict = ckpt['model']

    # Filter out workspace buffers with mismatched batch size —
    # they get reset per-batch anyway
    skip_keys = ['workspace_fwd', 'workspace_rev', 'field_history']
    state_dict = {k: v for k, v in state_dict.items() if k not in skip_keys}

    garden.load_state_dict(state_dict, strict=False)
    garden.eval()

    print(f"Checkpoint: epoch {ckpt.get('epoch', '?')}  val_mae={ckpt.get('val_mae', -1):.4f}")
    print(f"Generating {args.n_samples} samples, length={args.length} bytes each")
    print(f"Temperature: {args.temperature}")
    print("=" * 70)

    seeds = [
        args.seed,
        'The little girl went to',
        'In a dark forest there lived',
        'My favorite thing about school is',
        'One day the robot decided to',
    ]

    for i, seed in enumerate(seeds[:args.n_samples]):
        seed_bytes = seed.encode('utf-8')
        # Pad or truncate seed to window size
        window = garden.spine.byte_encoder.window_bytes
        if len(seed_bytes) < window:
            seed_bytes = bytes([0] * (window - len(seed_bytes))) + seed_bytes
        else:
            seed_bytes = seed_bytes[-window:]

        generated = generate_samples(garden, seed_bytes, args.length, args.temperature)

        # Strip leading nulls and display
        text = clean_bytes(generated).lstrip('·')
        print(f"\n--- Sample {i+1} ---")
        print(f"Seed: {seed}")
        print(f"Generated: {text[:200]}")
        print()


if __name__ == '__main__':
    main()
