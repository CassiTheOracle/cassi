#!/usr/bin/env python3
"""Stream bytes through QiCube — 3D grid PDE with Qi-driven learning.

Slides a 3D window over a byte sequence. Each window is processed by
the 3D PDE. Qi (self-surprise) drives local weight updates.
No backward passes, no optimizer, no training phase.

Usage:
    python3 qi_cube_run.py datasets/active/TinyStories-Instruct-train.txt \
        --d 128 --stride 512
"""

import argparse
import time

import torch

from qi_cube import QiCube


def main():
    parser = argparse.ArgumentParser(
        description="Stream bytes through QiCube — 3D PDE with Qi-driven learning")
    parser.add_argument("file", type=str, help="text file to stream")
    parser.add_argument("--d", type=int, default=64, help="field dimension per voxel")
    parser.add_argument("--grid", type=str, default="16,16,16",
                        help="grid shape as H,W,D")
    parser.add_argument("--stride", type=int, default=512,
                        help="window slide stride (bytes)")
    parser.add_argument("--lr", type=float, default=0.01,
                        help="global learning rate")
    parser.add_argument("--qi-target", type=float, default=0.1,
                        help="target Qi level for homeostasis")
    parser.add_argument("--max-bytes", type=int, default=None,
                        help="stop after N bytes")
    parser.add_argument("--gen-every", type=int, default=10000,
                        help="generate every N bytes (0=disabled)")
    args = parser.parse_args()

    grid_shape = tuple(int(d) for d in args.grid.split(","))
    Grid = grid_shape[0] * grid_shape[1] * grid_shape[2]
    print(f"Grid: {grid_shape} ({Grid:,} bytes per window)")

    DEVICE = 'cuda:0' if torch.cuda.is_available() else 'cpu'
    print(f"Device: {DEVICE}")

    model = QiCube(
        grid_shape=grid_shape,
        d=args.d,
        lr=args.lr,
        qi_target=args.qi_target,
        stride=args.stride,
    ).to(DEVICE)
    model.train()

    with open(args.file, 'rb') as f:
        data = f.read()
    if args.max_bytes:
        data = data[:args.max_bytes]
    total = len(data)
    print(f"Streaming {total:,} bytes through QiCube(d={args.d})")

    t0 = time.time()
    last_report = time.time()
    n_windows = 0

    offset = 0
    while offset + Grid <= total:
        qi = model.ingest_window(data, offset, learn=True)
        n_windows += 1

        now = time.time()
        if now - last_report >= 2.0 or n_windows <= 3:
            elapsed = now - t0
            rate = offset / elapsed if elapsed > 0 else 0
            E = model._field_energy(model.psi_prev).item()
            qi_t = model.qi_target

            print(
                f"win {n_windows:6d}  offset {offset:7d}  "
                f"qi={qi:.4f}  qi_t={qi_t:.3f}  "
                f"E={E:.3f}  rate={rate:.0f} B/s"
            )

            if args.gen_every > 0 and n_windows % (args.gen_every // args.stride) == 0:
                gen = model.generate(data, max(0, offset - 64), seed_len=64, max_new=128)
                gen_str = "".join(chr(b) if 32 <= b < 127 else '.' for b in gen)
                print(f"  gen: {gen_str}")

            last_report = now

        offset += args.stride

    elapsed = time.time() - t0
    print(f"\nDone — {total:,} bytes, {n_windows} windows in {elapsed:.1f}s "
          f"({total/elapsed:.0f} B/s)")


if __name__ == "__main__":
    main()
