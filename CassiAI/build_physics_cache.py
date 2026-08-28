#!/usr/bin/env python3
"""Build physics training cache from datasets/fields/.

Scans all field files, normalizes per-family (z-score), extracts sliding windows
of consecutive frames, and saves a compact cache tensor for training.

Usage:
    python3 build_physics_cache.py [--fields-dir DIR] [--output PATH]
        [--win-len N] [--max-per-file N] [--val-frac F]
"""

import argparse
import os
import sys
import time

import torch


def main():
    parser = argparse.ArgumentParser(
        description="Build physics training cache.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--fields-dir", default="datasets/fields",
                        help="Directory containing physics field .pt files")
    parser.add_argument("--output", default="datasets/physics_cache.pt",
                        help="Output cache path")
    parser.add_argument("--d", type=int, default=1024,
                        help="Expected spatial dimension (flattened)")
    parser.add_argument("--win-len", type=int, default=8,
                        help="Frames per window (source=N-1, target=shifted 1)")
    parser.add_argument("--max-per-file", type=int, default=10,
                        help="Max windows per file (subsampling)")
    parser.add_argument("--val-frac", type=float, default=0.1,
                        help="Fraction of windows per family held out for val")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = torch.Generator().manual_seed(args.seed)
    field_files = sorted([
        f for f in os.listdir(args.fields_dir) if f.endswith(".pt")
    ])
    print(f"Found {len(field_files)} field files in {args.fields_dir}")

    # Known NaN families — skip entirely
    nan_families = {"burgers", "pfc", "yang"}
    skipped_nan = 0
    skipped_shape = 0
    skipped_short = 0
    families_seen = set()

    all_windows = []   # list of [win_len, D] tensors
    all_family_ids = []  # list of ints
    family_names = []
    family_map = {}
    norm_stats = {}    # family_name -> (mean, std) per-family z-score

    t_start = time.time()

    for idx, fname in enumerate(field_files):
        family = fname.split("_")[0]
        if family in nan_families:
            skipped_nan += 1
            continue

        if idx % 500 == 0 and idx > 0:
            elapsed = time.time() - t_start
            print(f"  [{idx}/{len(field_files)}] {elapsed:.0f}s, "
                  f"{len(all_windows)} windows so far")

        path = os.path.join(args.fields_dir, fname)
        try:
            field = torch.load(path, map_location="cpu", weights_only=True)
        except Exception:
            continue

        if not isinstance(field, torch.Tensor) or field.numel() == 0:
            continue

        # ── Flatten spatial dims → [T, D] ──
        orig_shape = field.shape
        if field.dim() == 3:
            # [T, H, W] → [T, H*W]
            field = field.reshape(field.shape[0], -1)
        elif field.dim() == 4:
            # [T, D, H, W] → [T, D*H*W]
            field = field.reshape(field.shape[0], -1)
        elif field.dim() == 2:
            pass  # already [T, D]
        else:
            skipped_shape += 1
            continue

        T, D = field.shape
        if D != args.d:
            skipped_shape += 1
            continue
        if T < args.win_len:
            skipped_short += 1
            continue

        # ── NaN / Inf check ──
        if not torch.isfinite(field).all():
            continue
        # ── Skip families with extreme outliers ──
        # Outliers corrupt z-score: some spatial dims get near-zero std
        # while others dominate, producing blowup values after normalization.
        if field.abs().max() > 1e5:
            skipped_shape += 1
            continue

        # ── Per-family z-score normalization with clipping ──
        if family not in norm_stats:
            f_mean = field.mean(dim=0, keepdim=True)       # [1, D]
            f_std = field.std(dim=0, keepdim=True).clamp_min(1e-6)  # [1, D]
            norm_stats[family] = (f_mean, f_std)

        mean, std = norm_stats[family]
        field_norm = ((field - mean) / std).clamp(-5.0, 5.0)  # [T, D]


        # ── Family id ──
        if family not in family_map:
            family_map[family] = len(family_names)
            family_names.append(family)
        family_id = family_map[family]

        # ── Sliding windows ──
        max_start = T - args.win_len
        n_possible = max_start + 1
        n_windows = min(args.max_per_file, n_possible)

        if max_start == 0:
            starts = [0]
        else:
            starts = torch.randint(
                0, max_start + 1, (n_windows,), generator=rng
            ).tolist()

        for start in starts:
            window = field_norm[start:start + args.win_len]  # [win_len, D]
            if not torch.isfinite(window).all():
                continue
            all_windows.append(window)
            all_family_ids.append(family_id)

        families_seen.add(family)

    # ── Build tensors ──
    if len(all_windows) == 0:
        print("ERROR: no windows collected — check data paths and formats")
        sys.exit(1)

    windows = torch.stack(all_windows)  # [N, win_len, D]
    family_ids = torch.tensor(all_family_ids, dtype=torch.long)
    N = windows.shape[0]

    # Train/val split per family
    train_idx = []
    val_idx = []
    for fid in range(len(family_names)):
        mask = family_ids == fid
        indices = mask.nonzero(as_tuple=False).squeeze(-1)
        n_val = max(1, int(len(indices) * args.val_frac))
        perm = torch.randperm(len(indices), generator=rng)
        val_idx.append(indices[perm[:n_val]])
        train_idx.append(indices[perm[n_val:]])

    train_idx = torch.cat(train_idx) if train_idx else torch.tensor([], dtype=torch.long)
    val_idx = torch.cat(val_idx) if val_idx else torch.tensor([], dtype=torch.long)

    # ── Report ──
    elapsed = time.time() - t_start
    print(f"\n=== Cache built in {elapsed:.0f}s ===")
    print(f"  Families used:     {len(family_names)}")
    print(f"  Families skipped (NaN): {len([f for f in nan_families if f in families_seen or True])}")
    print(f"  Files skipped (NaN fam): {skipped_nan}")
    print(f"  Files skipped (shape):   {skipped_shape}")
    print(f"  Files skipped (short):   {skipped_short}")
    print(f"  Total windows:    {N:,}")
    print(f"  Win length:       {args.win_len}")
    print(f"  Dim per frame:    {args.d}")
    print(f"  Tensor shape:     {windows.shape}")
    print(f"  Memory (GB):      {windows.numel() * 4 / 1e9:.2f}")
    print(f"  Train windows:    {len(train_idx):,}")
    print(f"  Val windows:      {len(val_idx):,}")
    print(f"  Families:         {family_names}")

    # ── Save ──
    cache = {
        "windows": windows,                # [N, win_len, D] float32
        "family_ids": family_ids,          # [N] long
        "family_names": family_names,      # list of str
        "train_idx": train_idx,            # [N_train] long
        "val_idx": val_idx,                # [N_val] long
        "norm_stats": {
            fam: (mean.tolist(), std.tolist())
            for fam, (mean, std) in norm_stats.items()
        },
        "win_len": args.win_len,
        "D": args.d,
    }

    torch.save(cache, args.output)
    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
