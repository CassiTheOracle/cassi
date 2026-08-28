"""VindexWeightDataset — stream transformer weights from a LARQL vindex as quantized bytes."""

import json
import math
import os

import numpy as np
import torch


def _shape_prod(shape):
    prod = 1
    for dim in shape:
        prod *= dim
    return prod


class VindexWeightDataset:
    """Memory-map weight tensors from a LARQL vindex and yield byte windows.

    Mirrors the StreamingTextSampler contract used by experiments/train_qi_field.py:
      - sample_batch(batch_size, rng=None) -> (x, y, starts)
      - size property -> number of quantized bytes

    Weight files are ingested in this order:
      1. embeddings.bin
      2. gate_vectors.bin
      3. router_weights.bin
      4. norms.bin
      5. Any remaining *.bin files except *_manifest.json companions.

    Storage dtype is inferred per file:
      - Files whose name contains _q4k are treated as raw byte streams.
      - Files referenced by weight_manifest.json use the element size declared there.
      - All other files use the dtype field from index.json (f16 or f32).
    """

    def __init__(self, vindex_dir, window_bytes=1024, stride=None, dtype=torch.uint8,
                 quant_mode='per_tensor', include_files=None):
        self.vindex_dir = vindex_dir
        self.window_bytes = window_bytes
        self.stride = stride if stride is not None else window_bytes // 2
        self.dtype = dtype
        self.quant_mode = quant_mode
        self.include_files = set(include_files) if include_files is not None else None

        self._index = None
        self._files = []          # ordered list of (filename, mmap)
        self._scales = []         # per-tensor (filename, w_min, inv_scale, count)
        self._ring = None         # quantized bytes, aliased for helper compatibility
        self._total_bytes = 0

        self._load()

    @property
    def size(self):
        return self._total_bytes

    def _load(self):
        index_path = os.path.join(self.vindex_dir, 'index.json')
        if not os.path.isfile(index_path):
            raise FileNotFoundError(f'index.json not found in {self.vindex_dir}')

        with open(index_path, 'r', encoding='utf-8') as f:
            self._index = json.load(f)

        # Build a map from filename -> element_bytes using weight_manifest.json.
        manifest_path = os.path.join(self.vindex_dir, 'weight_manifest.json')
        file_element_bytes = {}
        if os.path.isfile(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            for entry in manifest:
                fname = entry.get('file')
                if not fname:
                    continue
                shape = entry.get('shape', [])
                length = entry.get('length', 0)
                nelements = _shape_prod(shape)
                if nelements > 0 and length % nelements == 0:
                    element_bytes = length // nelements
                    # Keep the smallest consistent element size per file.
                    if fname not in file_element_bytes or element_bytes < file_element_bytes[fname]:
                        file_element_bytes[fname] = element_bytes

        # Default element bytes from index dtype.
        dtype_str = self._index.get('dtype', 'f32')
        if dtype_str == 'f32':
            default_element_bytes = 4
        elif dtype_str == 'f16':
            default_element_bytes = 2
        else:
            raise NotImplementedError(f'Unsupported vindex dtype: {dtype_str}')

        # Ordered discovery: known weight files first, then any remaining .bin files.
        # Skip companion/metadata binaries that are not model weights.
        skip_names = {'down_meta.bin'}
        candidates = []
        for name in ('embeddings.bin', 'gate_vectors.bin', 'router_weights.bin', 'norms.bin'):
            path = os.path.join(self.vindex_dir, name)
            if os.path.isfile(path) and name not in skip_names:
                if self.include_files is None or name in self.include_files:
                    candidates.append(name)
        for name in sorted(os.listdir(self.vindex_dir)):
            if name.endswith('.bin') and name not in candidates and name not in skip_names:
                if self.include_files is None or name in self.include_files:
                    candidates.append(name)

        if not candidates:
            names = ', '.join(sorted(self.include_files)) if self.include_files else 'any'
            raise FileNotFoundError(f'No requested .bin weight files found in {self.vindex_dir} (wanted: {names})')

        chunks = []
        for name in candidates:
            path = os.path.join(self.vindex_dir, name)
            size = os.path.getsize(path)

            # q4k-packed files are already byte streams; do not reinterpret as floats.
            if '_q4k' in name:
                element_bytes = 1
            else:
                element_bytes = file_element_bytes.get(name, default_element_bytes)

            if element_bytes == 1:
                arr = np.memmap(path, dtype=np.uint8, mode='r')
                chunks.append(arr.copy())
                self._files.append((name, arr))
                self._scales.append((name, 0.0, 1.0, int(arr.size)))
                continue

            if size % element_bytes != 0:
                raise ValueError(
                    f'{name} size {size} is not divisible by element size {element_bytes}'
                )

            if element_bytes == 2:
                np_dtype = np.float16
            elif element_bytes == 4:
                np_dtype = np.float32
            else:
                raise NotImplementedError(
                    f'Unsupported element size {element_bytes} for {name}'
                )

            arr = np.memmap(path, dtype=np_dtype, mode='r')
            if not np.isfinite(arr).all():
                print(f'Warning: skipping {name}: contains NaN/Inf values')
                continue
            q, w_min, inv_scale = self._quantize(arr)
            self._files.append((name, arr))
            self._scales.append((name, float(w_min), float(inv_scale), int(arr.size)))
            chunks.append(q)

        self._ring = np.concatenate(chunks).astype(np.uint8)
        self._total_bytes = int(self._ring.size)

        # Optional consistency check for gate_vectors.bin against layers metadata.
        if 'layers' in self._index:
            total_layer_length = sum(layer.get('length', 0) for layer in self._index['layers'])
            for name, arr in self._files:
                if name == 'gate_vectors.bin' and arr.nbytes != total_layer_length:
                    print(
                        f'Warning: gate_vectors.bin size {arr.nbytes} != '
                        f'sum of layer lengths {total_layer_length}'
                    )

        print(f'Loaded vindex {self.vindex_dir}:')
        for name, _, inv_scale, count in self._scales:
            print(f'  {name}: {count} elements/bytes')
        print(f'  total quantized stream: {self._total_bytes} bytes')

    def _quantize(self, arr):
        if self.quant_mode == 'per_tensor':
            w_min = arr.min()
            w_max = arr.max()
            scale = 255.0 / (w_max - w_min + 1e-12)
            q = np.clip(np.round((arr - w_min) * scale), 0, 255).astype(np.uint8)
            return q, w_min, 1.0 / scale
        raise ValueError(f'Unknown quant_mode: {self.quant_mode}')

    def sample_batch(self, batch_size, rng=None, curriculum_weights=None):
        """Sample a batch of byte windows from the quantized weight stream."""
        if rng is None:
            rng = np.random

        max_start = self._total_bytes - self.window_bytes - self.stride
        if max_start <= 0:
            raise ValueError(
                f'Not enough data: {self._total_bytes} bytes '
                f'(need {self.window_bytes + self.stride})'
            )

        batch_size = min(batch_size, max_start)
        starts = rng.randint(0, max_start, size=batch_size)
        idx = np.arange(self.window_bytes)
        x_idx = starts[:, None] + idx[None, :]
        y_idx = (starts + self.stride)[:, None] + idx[None, :]
        x = torch.from_numpy(self._ring[x_idx]).to(self.dtype)
        y = torch.from_numpy(self._ring[y_idx]).to(self.dtype)
        return x, y, starts

    def decode(self, bytes_tensor, file_index=0):
        """Convert quantized bytes back to approximate float values for one source file."""
        if file_index >= len(self._scales):
            raise IndexError(f'No scale info for file_index {file_index}')
        _, w_min, inv_scale, _ = self._scales[file_index]
        return bytes_tensor.float() * inv_scale + w_min


def build_vindex_loader(vindex_dir, val_frac=0.02, window_bytes=1024,
                        stride=None, quant_mode='per_tensor', include_files=None):
    """Build a vindex weight loader matching the build_text_loader contract."""
    sampler = VindexWeightDataset(
        vindex_dir, window_bytes=window_bytes, stride=stride, quant_mode=quant_mode,
        include_files=include_files
    )
    total_size = sampler.size
    n_val = int(total_size * val_frac)
    n_train = total_size - n_val
    val_offset = n_train

    train_rng = np.random.RandomState(42)
    val_rng = np.random.RandomState(43)

    return sampler, total_size, n_train, n_val, val_offset, train_rng, val_rng


def sample_train_batch(sampler, batch_size, train_rng):
    """Sample a training batch of byte windows (matches train_langevin_text.py)."""
    x, y, _ = sampler.sample_batch(batch_size, rng=train_rng)
    return x, y


def sample_val_batch(sampler, batch_size, val_offset, val_rng):
    """Sample a validation batch from the held-out tail of the stream."""
    max_start = sampler.size - val_offset - sampler.window_bytes - sampler.stride
    if max_start > 0:
        starts = val_rng.randint(val_offset, val_offset + max_start, size=batch_size)
    else:
        max_start = max(1, sampler.size - sampler.window_bytes - sampler.stride)
        starts = val_rng.randint(0, max_start, size=batch_size)

    idx = np.arange(sampler.window_bytes)
    x_idx = starts[:, None] + idx[None, :]
    y_idx = (starts + sampler.stride)[:, None] + idx[None, :]
    x = torch.from_numpy(sampler._ring[x_idx])
    y = torch.from_numpy(sampler._ring[y_idx])
    return x, y
