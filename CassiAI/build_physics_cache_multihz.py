#!/usr/bin/env python3
"""Build physics cache with multi-horizon windows.

Each window contains input frames + target frames at multiple horizons.
Default: 4 input frames + targets at horizons [1, 4, 16] → 20 total frames.
"""

import torch
import os
import argparse
from pathlib import Path


def build_cache(fields_dir='datasets/fields',
                output='datasets/physics_cache_multihz_v1.pt',
                input_frames=4,
                horizons=(1, 4, 16),
                windows_per_file=10,
                seed=42):
    rng = torch.Generator().manual_seed(seed)
    field_files = sorted([f for f in os.listdir(fields_dir) if f.endswith('.pt')])

    total_frames_needed = input_frames + max(horizons)
    all_windows = []
    all_labels = []
    all_families = []
    family_map = {}
    next_family_id = 0

    for i, fname in enumerate(field_files):
        if i % 500 == 0:
            print(f"Processing {i}/{len(field_files)}: {fname}")

        path = os.path.join(fields_dir, fname)
        field = torch.load(path, map_location='cpu', weights_only=False)

        # family from filename prefix (before first underscore)
        family = fname.split('_')[0]
        if family not in family_map:
            family_map[family] = next_family_id
            next_family_id += 1
        family_id = family_map[family]

        T = field.shape[0]
        if T < total_frames_needed:
            continue

        # Flatten spatial dims → [T, D]
        if field.dim() == 3:
            field = field.view(T, -1)
        elif field.dim() == 2:
            pass  # already flat
        else:
            continue

        D_spatial = field.shape[1]
        if D_spatial != 1024:
            # Skip non-matching dimensions for now
            # TODO: support resampling or multiple spine sizes
            continue

        # Random start positions for windows
        max_start = T - total_frames_needed
        if max_start < 0:
            continue

        n_wins = min(windows_per_file, max_start + 1)
        if max_start == 0:
            starts = [0]
        else:
            starts = torch.randint(0, max_start + 1, (n_wins,), generator=rng).tolist()

        for start in starts:
            window = field[start:start + total_frames_needed]  # [total_frames, D]
            # Skip windows with NaN, Inf, or extreme outliers — these corrupt training.
            if not torch.isfinite(window).all():
                continue
            if window.abs().max() > 100.0:
                continue
            all_windows.append(window)
            all_labels.append(family_id)
            all_families.append(family)

    wins = torch.stack(all_windows)  # [N, total_frames, D]
    labels = torch.tensor(all_labels, dtype=torch.int64)

    print(f"\nBuilt cache:")
    print(f"  Windows: {len(all_windows):,}")
    print(f"  Frames per window: {total_frames_needed}")
    print(f"  Horizons: {horizons}")
    print(f"  Families: {len(family_map)}")
    print(f"  Tensor shape: {wins.shape}")
    print(f"  Approx size: {wins.numel() * 4 / 1e9:.2f} GB")

    cache = {
        'windows': wins,
        'labels': labels,
        'family_map': family_map,
        'input_frames': input_frames,
        'horizons': list(horizons),
    }
    torch.save(cache, output)
    print(f"Saved to {output}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--fields-dir', default='datasets/fields')
    parser.add_argument('--output', default='datasets/physics_cache_multihz_v1.pt')
    parser.add_argument('--input-frames', type=int, default=4)
    parser.add_argument('--horizons', type=int, nargs='+', default=[1, 4, 16])
    parser.add_argument('--windows-per-file', type=int, default=10)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    build_cache(
        fields_dir=args.fields_dir,
        output=args.output,
        input_frames=args.input_frames,
        horizons=tuple(args.horizons),
        windows_per_file=args.windows_per_file,
        seed=args.seed,
    )
