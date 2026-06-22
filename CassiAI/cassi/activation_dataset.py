#!/usr/bin/env python3
"""Activation dataset for function-space distillation.

Loads pre-captured per-layer residuals from a memory-mapped file
and yields (context, target) pairs: given residuals at layers
[L..L+seq_layers-1], predict residual at layer [L+seq_layers].

Output format matches experiments/capture_activations.py:
    residuals.f16: [total_tokens, n_layers, hidden_size] float16
    metadata.json: {n_layers, hidden_size, total_tokens, ...}
"""

import json
import os
import warnings

import numpy as np
import torch


# ── Dataset ──

class ActivationDataset:
    """Load pre-captured layer residuals and yield (context, target) pairs.

    Each sample: given residuals at layers [L..L+seq_layers-1],
    predict residual at layer [L+seq_layers].
    """

    def __init__(self, data_dir: str, seq_layers: int = 10, normalize: bool = True):
        meta_path = os.path.join(data_dir, 'metadata.json')
        with open(meta_path) as f:
            meta = json.load(f)

        self._n_layers = meta['n_layers']
        self._hidden_size = meta['hidden_size']
        self._total_tokens = meta['total_tokens']
        self._seq_layers = seq_layers
        self._normalize = normalize

        if self._total_tokens < 2:
            raise ValueError(
                f'total_tokens ({self._total_tokens}) < 2; need at least two '
                f'tokens for train/val split')
        if seq_layers >= self._n_layers:
            raise ValueError(
                f'seq_layers ({seq_layers}) must be < n_layers '
                f'({self._n_layers})')

        # Memory-map the residual file.
        # Shape: [total_tokens, n_layers, hidden_size]
        self._data = np.memmap(
            os.path.join(data_dir, 'residuals.f16'),
            dtype=np.float16,
            mode='r',
            shape=(self._total_tokens, self._n_layers, self._hidden_size))

        self._max_start_layer = self._n_layers - seq_layers - 1

    @property
    def hidden_size(self) -> int:
        return self._hidden_size

    @property
    def n_layers(self) -> int:
        return self._n_layers

    @property
    def seq_layers(self) -> int:
        return self._seq_layers

    @property
    def total_tokens(self) -> int:
        return self._total_tokens


    def sample_batch(self, batch_size: int, rng=None):
        """Sample a batch of (context, target) pairs.

        For each sample:
        - Randomly choose a token position from [0, total_tokens)
        - Randomly choose a starting layer L from [0, n_layers - seq_layers - 1]
        - Context = residuals[token, L:L+seq_layers]  -> [seq_layers, hidden_size]
        - Target  = residuals[token, L+seq_layers]    -> [hidden_size]

        Returns:
            x: torch.FloatTensor [batch_size, seq_layers, hidden_size]
            y: torch.FloatTensor [batch_size, hidden_size]
        """

        if rng is None:
            rng = np.random.default_rng()

        # Normalize RNG: Generator uses .integers(), RandomState uses .randint()
        _randint = rng.integers if hasattr(rng, 'integers') else rng.randint

        if batch_size > self._total_tokens:
            warnings.warn(
                f'batch_size ({batch_size}) > total_tokens '
                f'({self._total_tokens}), clamping')
            batch_size = self._total_tokens

        token_idx = _randint(0, self._total_tokens, size=batch_size)
        start_layer = _randint(
            0, self._max_start_layer + 1, size=batch_size)

        # Gather context: [B, seq_layers, hidden_size]
        x = np.stack([
            self._data[token_idx[i],
                        start_layer[i]:start_layer[i] + self._seq_layers]
            for i in range(batch_size)
        ]).astype(np.float32)

        # Gather target: [B, hidden_size]
        y = np.stack([
            self._data[token_idx[i],
                        start_layer[i] + self._seq_layers]
            for i in range(batch_size)
        ]).astype(np.float32)

        # Normalize each sample to zero mean / unit std within this batch.
        # This handles the large dynamic range of residual stream values
        # without needing precomputed per-layer statistics.
        if self._normalize:
            # x: [B, seq_layers, hidden_size] -> mean over last dim
            x = (x - x.mean(axis=-1, keepdims=True)) / (x.std(axis=-1, keepdims=True) + 1e-8)
            y = (y - y.mean(axis=-1, keepdims=True)) / (y.std(axis=-1, keepdims=True) + 1e-8)
        return torch.from_numpy(x), torch.from_numpy(y)


class _TokenRangeDataset(ActivationDataset):
    """Subclass that constrains token sampling to [start, end).

    Shares the parent's memory-map and metadata but overrides
    sample_batch to draw tokens from a contiguous range.  Used to
    provide train/val isolation without duplicating the mmap.
    """

    def __init__(self, ds, start, end):
        # Shallow copy: share the memmap and metadata, override range.
        self._data = ds._data
        self._hidden_size = ds._hidden_size
        self._n_layers = ds._n_layers
        self._total_tokens = ds._total_tokens
        self._seq_layers = ds._seq_layers
        self._max_start_layer = ds._max_start_layer
        self._token_start = start
        self._normalize = ds._normalize
        self._token_end = end

    def sample_batch(self, batch_size: int, rng=None):
        if rng is None:
            rng = np.random.default_rng()

        # Normalize RNG: Generator uses .integers(), RandomState uses .randint()
        _randint = rng.integers if hasattr(rng, 'integers') else rng.randint

        if batch_size > self._token_end - self._token_start:
            warnings.warn(
                f'batch_size ({batch_size}) > available tokens '
                f'({self._token_end - self._token_start}), clamping')
            batch_size = self._token_end - self._token_start

        token_idx = _randint(self._token_start, self._token_end,
                             size=batch_size)
        start_layer = _randint(0, self._max_start_layer + 1,
                               size=batch_size)

        x = np.stack([
            self._data[token_idx[i],
                        start_layer[i]:start_layer[i] + self._seq_layers]
            for i in range(batch_size)
        ]).astype(np.float32)

        y = np.stack([
            self._data[token_idx[i],
                        start_layer[i] + self._seq_layers]
            for i in range(batch_size)
        ]).astype(np.float32)

        # Normalize each sample to zero mean / unit std (same as parent).
        if self._normalize:
            x = (x - x.mean(axis=-1, keepdims=True)) / (x.std(axis=-1, keepdims=True) + 1e-8)
            y = (y - y.mean(axis=-1, keepdims=True)) / (y.std(axis=-1, keepdims=True) + 1e-8)
        return torch.from_numpy(x), torch.from_numpy(y)


# ── Helpers ──

def build_activation_loader(data_dir, val_frac=0.02, seq_layers=10, seed=42):
    """Build dataset + train/val split with deterministic RNGs.

    Validation samples the last ``val_frac`` fraction of tokens; training
    samples the remainder.  This avoids token leakage while sharing the
    same memory-mapped data.

    Returns:
        (train_ds, val_ds, n_train, n_val, train_rng, val_rng)
    """
    full = ActivationDataset(data_dir, seq_layers=seq_layers)
    total = full.total_tokens
    n_val = max(1, int(total * val_frac))
    n_train = total - n_val

    train_ds = _TokenRangeDataset(full, 0, n_train)
    val_ds = _TokenRangeDataset(full, n_train, total)

    train_rng = np.random.default_rng(seed)
    val_rng = np.random.default_rng(seed + 1)

    return train_ds, val_ds, n_train, n_val, train_rng, val_rng


def sample_train_batch(dataset, batch_size, rng):
    """Sample training batch. Returns (x, y) CPU float32 tensors."""
    return dataset.sample_batch(batch_size, rng=rng)


def sample_val_batch(dataset, batch_size, rng):
    """Sample validation batch. Returns (x, y) CPU float32 tensors."""
    return dataset.sample_batch(batch_size, rng=rng)


# ── Quick smoke test ──

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print(f'Usage: python3 {sys.argv[0]} <data_dir> [seq_layers]')
        sys.exit(1)
    data_dir = sys.argv[1]
    seq_layers = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    ds = ActivationDataset(data_dir, seq_layers=seq_layers)
    print(f'hidden_size={ds.hidden_size}, n_layers={ds.n_layers}, '
          f'total_tokens={ds.total_tokens}, seq_layers={ds.seq_layers}')

    x, y = ds.sample_batch(4)
    print(f'x: {x.shape} {x.dtype}, y: {y.shape} {y.dtype}')
    assert x.shape == (4, seq_layers, ds.hidden_size), \
        f'x shape mismatch: {x.shape}'
    assert y.shape == (4, ds.hidden_size), \
        f'y shape mismatch: {y.shape}'
    print('ActivationDataset OK')
