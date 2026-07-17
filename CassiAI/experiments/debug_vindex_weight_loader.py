#!/usr/bin/env python3
"""Smoke-test VindexWeightDataset on a LARQL vindex directory."""

import argparse
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cassi.vindex_weight_dataset import (
    VindexWeightDataset, build_vindex_loader, sample_train_batch, sample_val_batch,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--vindex-dir', required=True)
    parser.add_argument('--window-bytes', type=int, default=128)
    parser.add_argument('--bs', type=int, default=4)
    parser.add_argument('--val-frac', type=float, default=0.02)
    args = parser.parse_args()

    print('=== Direct dataset smoke test ===')
    sampler = VindexWeightDataset(args.vindex_dir, window_bytes=args.window_bytes)
    print(f'Total quantized bytes: {sampler.size:,}')
    print('Per-file scale info:')
    for name, w_min, inv_scale, count in sampler._scales:
        print(f'  {name}: count={count:,} w_min={w_min:.6f} inv_scale={inv_scale:.6f}')

    rng = np.random.RandomState(0)
    x, y, starts = sampler.sample_batch(args.bs, rng=rng)
    print(f'Sample batch x: {tuple(x.shape)} dtype={x.dtype} min={x.min().item()} max={x.max().item()}')
    print(f'Sample batch y: {tuple(y.shape)} dtype={y.dtype} min={y.min().item()} max={y.max().item()}')
    assert 0 <= x.min() and x.max() <= 255, 'x bytes out of range'
    assert 0 <= y.min() and y.max() <= 255, 'y bytes out of range'

    print('\n=== Train/val loader contract test ===')
    sampler2, total_size, n_train, n_val, val_offset, train_rng, val_rng = build_vindex_loader(
        args.vindex_dir, val_frac=args.val_frac, window_bytes=args.window_bytes)
    print(f'total={total_size:,} n_train={n_train:,} n_val={n_val:,} val_offset={val_offset:,}')

    x2, y2 = sample_train_batch(sampler2, args.bs, train_rng)
    print(f'Train helper x: {tuple(x2.shape)} dtype={x2.dtype}')
    assert x2.dtype == torch.uint8

    x3, y3 = sample_val_batch(sampler2, args.bs, val_offset, val_rng)
    print(f'Val helper x: {tuple(x3.shape)} dtype={x3.dtype}')
    assert x3.dtype == torch.uint8

    print('\nAll checks passed.')


if __name__ == '__main__':
    main()
