"""StreamingTextSampler — memory-mapped text with prefetching and online support.

Features:
  - Memory-mapped files: text files larger than RAM are fine
  - Ring buffer: supports append-only online learning (new data streamed in)
  - Prefetching: GPU transfer overlaps with CPU sampling
  - Vectorized numpy: no Python loops over bytes
  - Mixed-precision ready: returns float16 fields optionally
"""

import torch
import numpy as np
import os
from threading import Thread
from queue import Queue


class StreamingTextSampler:
    """Sample byte windows from a memory-mapped text file.

    Supports two modes:
      - static: file on disk, random access
      - streaming: ring buffer that grows as new data arrives
    """

    def __init__(self, path, window_bytes=1024, stride=256, device='cuda',
                 prefetch_batches=4, dtype=torch.uint8):
        self.path = path
        self.window_bytes = window_bytes
        self.stride = stride
        self.device = device
        self.prefetch_batches = prefetch_batches
        self.dtype = dtype

        self._mmap = None
        self._size = 0
        self._ring = None
        self._ring_size = 0
        self._mode = 'static'

        if path and os.path.exists(path):
            self._init_mmap(path)
        else:
            # Streaming mode: start empty, data added via append()
            self._mode = 'streaming'
            self._ring = np.zeros(1024 * 1024, dtype=np.uint8)  # 1MB initial
            self._ring_size = 0

        self._prefetch_queue = Queue(maxsize=prefetch_batches)
        self._prefetch_thread = None
        self._prefetch_stop = False

    def _init_mmap(self, path):
        """Initialize memory-mapped file."""
        self._size = os.path.getsize(path)
        self._mmap = np.memmap(path, dtype=np.uint8, mode='r')
        self._mode = 'static'

    def _ensure_ring(self, needed):
        """Grow ring buffer if needed."""
        if self._ring is None:
            return
        if needed > len(self._ring):
            new_size = max(needed, int(len(self._ring) * 1.5))
            new_ring = np.zeros(new_size, dtype=np.uint8)
            new_ring[:self._ring_size] = self._ring[:self._ring_size]
            self._ring = new_ring

    def append(self, data_bytes):
        """Append new bytes for online learning."""
        if self._mode == 'static':
            raise RuntimeError("Cannot append to static mmap. Use streaming mode.")

        n = len(data_bytes)
        self._ensure_ring(self._ring_size + n)

        if isinstance(data_bytes, (bytes, bytearray)):
            self._ring[self._ring_size:self._ring_size + n] = np.frombuffer(data_bytes, dtype=np.uint8)
        else:
            self._ring[self._ring_size:self._ring_size + n] = data_bytes
        self._ring_size += n

    @property
    def size(self):
        if self._mode == 'static':
            return self._size
        return self._ring_size

    def sample_batch(self, batch_size, rng=None, curriculum_weights=None):
        """Sample a batch of byte windows.

        rng: numpy RandomState or None
        curriculum_weights: optional dict of idx -> weight for prioritized sampling
        """
        if rng is None:
            rng = np.random

        max_start = self.size - self.window_bytes - self.stride
        if max_start <= 0:
            raise ValueError(f"Not enough data: {self.size} bytes (need {self.window_bytes + self.stride})")

        # Clamp batch size to available data
        batch_size = min(batch_size, max_start)

        # Get data source
        if self._mode == 'static':
            data = self._mmap
        else:
            data = self._ring[:self._ring_size]

        # Sampling with optional curriculum (only for modest-sized datasets)
        if curriculum_weights and len(curriculum_weights) > 100 and max_start < 10_000_000:
            # Weighted sampling based on curriculum — limited to <10M to avoid huge arrays
            indices = np.arange(max_start)
            weights = np.ones(max_start, dtype=np.float64)
            for idx, w in curriculum_weights.items():
                if 0 <= idx < max_start:
                    weights[idx] = w
            weights /= weights.sum()
            starts = rng.choice(indices, size=batch_size, p=weights)
        else:
            starts = rng.randint(0, max_start, size=batch_size)

        idx = np.arange(self.window_bytes)
        x_idx = starts[:, None] + idx[None, :]
        y_idx = (starts + self.stride)[:, None] + idx[None, :]

        x = torch.from_numpy(data[x_idx]).to(self.device)
        y = torch.from_numpy(data[y_idx]).to(self.device)
        return x, y, starts

    def start_prefetch(self, batch_size, rng):
        """Start background prefetching thread."""
        self._prefetch_stop = False

        def worker():
            while not self._prefetch_stop:
                try:
                    batch = self.sample_batch(batch_size, rng)
                    self._prefetch_queue.put(batch, block=True)
                except Exception:
                    break

        self._prefetch_thread = Thread(target=worker, daemon=True)
        self._prefetch_thread.start()

    def get_prefetched(self):
        """Get a prefetched batch."""
        return self._prefetch_queue.get(block=True)

    def stop_prefetch(self):
        """Stop prefetching thread."""
        self._prefetch_stop = True
        if self._prefetch_thread:
            self._prefetch_thread.join(timeout=1.0)

    def __del__(self):
        self.stop_prefetch()
        if self._mmap is not None:
            del self._mmap


class MixedPrecisionTrainer:
    """Wrapper for mixed-precision training with autocast and gradient scaling."""

    def __init__(self, model, optimizer, enabled=True):
        self.model = model
        self.optimizer = optimizer
        self.enabled = enabled and torch.cuda.is_available()
        self.scaler = torch.amp.GradScaler('cuda', enabled=self.enabled) if self.enabled else None

    def step(self, loss_fn, *args, **kwargs):
        """One training step with optional mixed precision."""
        if not self.enabled:
            loss = loss_fn(*args, **kwargs)
            loss.backward()
            return loss

        with torch.amp.autocast('cuda'):
            loss = loss_fn(*args, **kwargs)

        self.scaler.scale(loss).backward()
        return loss

    def backward(self, loss):
        """Backward pass with optional gradient scaling."""
        if self.enabled:
            self.scaler.scale(loss).backward()
        else:
            loss.backward()
        return loss

    def unscale(self):
        """Unscale gradients (no-op if mixed precision disabled)."""
        if self.enabled:
            self.scaler.unscale_(self.optimizer)

    def step_optimizer(self, clip_grad=1.0, neuro_modulation=None):
        """Optimizer step with gradient clipping.

        When neuro_modulation is provided and mixed precision is enabled,
        we bypass scaler.step() (which cannot pass extra args) and call
        optimizer.step() directly after the already-performed unscale().
        """
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), clip_grad)
        if self.enabled and neuro_modulation is None:
            self.scaler.step(self.optimizer)
        else:
            # scaler.unscale_() already called in optimizer_step();
            # call optimizer directly so neuro_modulation reaches it.
            self.optimizer.step(neuro_modulation=neuro_modulation)

    def update_scaler(self):
        """Update gradient scaler (no-op if disabled)."""
        if self.enabled:
            self.scaler.update()

    def zero_grad(self):
        """Zero gradients."""
        self.optimizer.zero_grad()

    def optimizer_step(self, clip_grad=1.0, neuro_modulation=None):
        """Convenience: full step with unscale, clip, step, update, zero_grad."""
        self.unscale()
        self.step_optimizer(clip_grad, neuro_modulation=neuro_modulation)
        self.update_scaler()
        self.zero_grad()
