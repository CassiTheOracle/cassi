"""Native Qwen3.6 Qwen3VL-merger vision encoder for the resident Qwen graph.

The GGUF projector is verified and read only through CassiFI's WeightBank.  The
visual transformer below is an explicit batched-token implementation of the
Qwen3VL graph; it does not load a llama runtime or delegate image inference.
"""
from __future__ import annotations

import ctypes
from collections import OrderedDict
from copy import deepcopy
from io import BytesIO
import math
import os
import threading
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np
from PIL import Image, UnidentifiedImageError

from .weight_bank import WeightBank, WeightBankError


_MAX_PNG_BYTES = 32 * 1024 * 1024
_MAX_SOURCE_EDGE = 8192
_MAX_SOURCE_PIXELS = 16 * 1024 * 1024
_MAX_PATCH_TOKENS = 4096
_MAX_RUNTIME_IMAGE_PIXELS = 1024 * 1024
_MAX_CACHED_BLOCKS = 1
_VISION_CACHE_FRACTION = 0.45
_VISION_CACHE_CAP_BYTES = 3 * 1024 * 1024 * 1024
_GELU_SQRT_2_OVER_PI = np.float32(0.7978845608028654)
_GELU_COEF = np.float32(0.044715)


def _available_host_memory_bytes() -> int | None:
    """Return currently available physical RAM, or ``None`` if it is unknown."""
    try:
        if os.name == "nt":
            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("length", ctypes.c_ulong),
                    ("load", ctypes.c_ulong),
                    ("total_physical", ctypes.c_ulonglong),
                    ("available_physical", ctypes.c_ulonglong),
                    ("total_page", ctypes.c_ulonglong),
                    ("available_page", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong),
                    ("available_virtual", ctypes.c_ulonglong),
                    ("available_extended", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return None
            return int(status.available_physical)
        pages = int(os.sysconf("SC_AVPHYS_PAGES"))
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        if pages < 0 or page_size <= 0:
            return None
        return pages * page_size
    except (AttributeError, OSError, ValueError):
        return None


def _vision_block_bytes(width: int, ff_width: int) -> int:
    """Exact float32 payload size for one Qwen visual transformer block."""
    matrix_values = 4 * width * width + 2 * ff_width * width
    vector_values = 9 * width + ff_width
    return (matrix_values + vector_values) * np.dtype(np.float32).itemsize


class QwenVisionError(RuntimeError):
    """The Qwen vision projector or image could not be processed safely."""


class QwenVisionEncoder:
    """Encode one PNG with the verified Qwen3.6-35B-A3B vision projector.

    Activations are row-major float32. ``exchange`` runs after patch embedding,
    each transformer block, and within the merger before its final projection.
    The returned values are consumed by the remaining projector graph.
    """

    def __init__(
        self,
        projector_path: str | Path,
        *,
        backend: str = "cpu",
        library_path: str | Path | None = None,
        threads: int = 8,
    ) -> None:
        if backend not in {"cpu", "rocm", "auto"}:
            raise QwenVisionError("backend must be 'cpu', 'rocm', or 'auto'")
        self._torch = None
        self._device = None
        self._auto_backend = backend == "auto"
        if backend != "cpu":
            try:
                import torch
            except ImportError as exc:
                if backend == "rocm":
                    raise QwenVisionError("backend='rocm' requires PyTorch with ROCm") from exc
                torch = None
            if (
                torch is not None
                and getattr(torch.version, "hip", None) is not None
                and torch.cuda.is_available()
            ):
                self._torch = torch
                self._device = torch.device("cuda")
            elif backend == "rocm":
                raise QwenVisionError(
                    "backend='rocm' requires an available PyTorch ROCm device"
                )

        bank = WeightBank(
            projector_path,
            backend="cpu",
            library_path=library_path,
            threads=threads,
        )
        try:
            metadata = bank.manifest.get("model_metadata")
            if not isinstance(metadata, Mapping):
                raise QwenVisionError("verified projector manifest has no GGUF model metadata")
            self._config = self._validate_projector(bank, metadata)
        except Exception:
            bank.close()
            raise

        self._bank = bank
        self.projector_sha256 = bank.source_sha256
        self._max_cached_blocks = _MAX_CACHED_BLOCKS
        self._block_cache_budget_bytes = 0
        self._block_cache_bytes = 0
        self._cache_hits = 0
        self._cache_dequantizations = 0
        self._exchange_device_copies_avoided = 0
        self._lock = threading.RLock()
        self._closed = False
        self._fixed_tensors: dict[str, Any] = {}
        self._block_cache: OrderedDict[int, dict[str, Any]] = OrderedDict()
        self._rotary_cache_key: tuple[str, int, int, int] | None = None
        self._rotary_cache_tables: tuple[
            np.ndarray, np.ndarray, np.ndarray, np.ndarray
        ] | None = None
        self._rotary_cache_bytes = 0
        self._rotary_cache_hits = 0
        self._last_image_grid: tuple[int, int] | None = None
        self._compute_backend = (
            f"pytorch-rocm:{self._torch.cuda.get_device_name(self._device)}"
            if self._torch is not None
            else "numpy-cpu"
        )
        self._metadata = {
            "source_id": bank.source_id,
            "source_sha256": bank.source_sha256,
            "file_size": int(bank.manifest["file_size"]),
            "general_name": metadata.get("general.name"),
            "projector_type": metadata.get("clip.projector_type"),
            "patch_size": self._config["patch_size"],
            "spatial_merge_size": self._config["merge_size"],
            "vision_width": self._config["width"],
            "vision_layers": self._config["layers"],
            "vision_heads": self._config["heads"],
            "vision_head_width": self._config["head_width"],
            "vision_feed_forward_width": self._config["ff_width"],
            "projection_width": self._config["projection_width"],
            "image_mean": list(self._config["image_mean"]),
            "image_std": list(self._config["image_std"]),
            "compute_backend": self._compute_backend,
            "preprocessing": {
                "resize": "aspect-preserving bilinear, Qwen patch/merge aligned",
                "max_patch_tokens": _MAX_PATCH_TOKENS,
                "max_runtime_pixels": self._config["max_runtime_pixels"],
                "max_source_edge": _MAX_SOURCE_EDGE,
                "max_source_pixels": _MAX_SOURCE_PIXELS,
                "animated_png": "rejected",
            },
            "vision_residency": {
                "block_cache_budget_bytes": 0,
                "block_cache_bytes": 0,
                "cached_blocks": 0,
                "cache_hits": 0,
                "block_dequantizations": 0,
                "exchange_device_copies_avoided": 0,
                "resource_manager_accounting": "unavailable",
                "rotary_cache_bytes": 0,
                "rotary_cache_hits": 0,
            },
        }
        if self._torch is None:
            self._configure_cpu_block_cache()

    @property
    def model_metadata(self) -> dict[str, Any]:
        """Return the verified projector identity and numerical architecture."""
        return deepcopy(self._metadata)

    @property
    def last_image_grid(self) -> tuple[int, int] | None:
        """Merged (rows, columns), row-major with the latest successful embeddings."""
        with self._lock:
            return self._last_image_grid

    @staticmethod
    def _validate_projector(bank: WeightBank, metadata: Mapping[str, Any]) -> dict[str, Any]:
        if metadata.get("clip.projector_type") != "qwen3vl_merger":
            raise QwenVisionError("projector is not a Qwen3VL merger")
        if metadata.get("clip.has_vision_encoder") is not True:
            raise QwenVisionError("projector GGUF does not declare a native vision encoder")
        if metadata.get("clip.use_gelu") is not True:
            raise QwenVisionError("projector does not declare the required GELU activation")

        expected_metadata = {
            "clip.vision.block_count": 27,
            "clip.vision.embedding_length": 1152,
            "clip.vision.feed_forward_length": 4304,
            "clip.vision.attention.head_count": 16,
            "clip.vision.patch_size": 16,
            "clip.vision.spatial_merge_size": 2,
            "clip.vision.projection_dim": 2048,
        }
        for key, expected in expected_metadata.items():
            if metadata.get(key) != expected:
                raise QwenVisionError(
                    f"projector metadata {key} is {metadata.get(key)!r}, expected {expected!r}"
                )

        manifest_tensors = bank.manifest.get("tensors")
        if not isinstance(manifest_tensors, list):
            raise QwenVisionError("verified projector manifest has no tensor table")
        shapes: dict[str, tuple[int, ...]] = {}
        for tensor in manifest_tensors:
            if isinstance(tensor, Mapping) and isinstance(tensor.get("name"), str):
                raw_shape = tensor.get("shape")
                if isinstance(raw_shape, list) and all(
                    isinstance(dim, int) and dim > 0 for dim in raw_shape
                ):
                    shapes[str(tensor["name"])] = tuple(raw_shape)

        width = 1152
        ff_width = 4304
        heads = 16
        head_width = width // heads
        patch_size = 16
        merge_size = 2
        projection_width = 2048
        expected_shapes = {
            "v.patch_embd.weight": (width, 3, patch_size, patch_size),
            "v.patch_embd.bias": (width,),
            "v.position_embd.weight": (48 * 48, width),
            "mm.0.weight": (4 * width, 4 * width),
            "mm.0.bias": (4 * width,),
            "mm.2.weight": (projection_width, 4 * width),
            "mm.2.bias": (projection_width,),
        }
        for layer in range(27):
            prefix = f"v.blk.{layer}."
            expected_shapes.update(
                {
                    prefix + "attn_qkv.weight": (3 * width, width),
                    prefix + "attn_qkv.bias": (3 * width,),
                    prefix + "attn_out.weight": (width, width),
                    prefix + "attn_out.bias": (width,),
                    prefix + "ln1.weight": (width,),
                    prefix + "ln1.bias": (width,),
                    prefix + "ln2.weight": (width,),
                    prefix + "ln2.bias": (width,),
                    prefix + "ffn_up.weight": (ff_width, width),
                    prefix + "ffn_up.bias": (ff_width,),
                    prefix + "ffn_down.weight": (width, ff_width),
                    prefix + "ffn_down.bias": (width,),
                }
            )
        optional_norms: dict[str, dict[str, str | None]] = {}
        for norm_name in ("pre_ln", "post_ln"):
            weight_name = f"v.{norm_name}.weight"
            bias_name = f"v.{norm_name}.bias"
            if weight_name in shapes:
                expected_shapes[weight_name] = (width,)
                if bias_name in shapes:
                    expected_shapes[bias_name] = (width,)
                optional_norms[norm_name] = {
                    "weight": weight_name,
                    "bias": bias_name if bias_name in shapes else None,
                }
            elif bias_name in shapes:
                raise QwenVisionError(f"projector has {bias_name!r} without its norm weight")
        if any(name.startswith("v.deepstack.") for name in shapes):
            raise QwenVisionError("projector deepstack outputs are not supported by this encoder")
        for name, expected_shape in expected_shapes.items():
            actual_shape = shapes.get(name)
            if actual_shape != expected_shape:
                raise QwenVisionError(
                    f"projector tensor {name!r} has shape {actual_shape}, expected {expected_shape}"
                )

        mean = metadata.get("clip.vision.image_mean")
        std = metadata.get("clip.vision.image_std")
        if (
            not isinstance(mean, list)
            or not isinstance(std, list)
            or len(mean) < 3
            or len(std) < 3
            or any(not isinstance(v, (int, float)) or not math.isfinite(float(v)) for v in mean[:3] + std[:3])
            or any(float(v) <= 0 for v in std[:3])
        ):
            raise QwenVisionError("projector image mean/std metadata is missing or invalid")
        max_pixels_from_model = metadata.get("clip.vision.image_max_pixels")
        if (
            isinstance(max_pixels_from_model, bool)
            or not isinstance(max_pixels_from_model, int)
            or max_pixels_from_model <= 0
        ):
            max_pixels_from_model = _MAX_RUNTIME_IMAGE_PIXELS
        max_runtime_pixels = min(
            int(max_pixels_from_model),
            _MAX_RUNTIME_IMAGE_PIXELS,
            _MAX_PATCH_TOKENS * patch_size * patch_size,
        )
        return {
            "width": width,
            "layers": 27,
            "heads": heads,
            "head_width": head_width,
            "ff_width": ff_width,
            "patch_size": patch_size,
            "merge_size": merge_size,
            "projection_width": projection_width,
            "image_mean": tuple(float(v) for v in mean[:3]),
            "image_std": tuple(float(v) for v in std[:3]),
            "max_runtime_pixels": max_runtime_pixels,
            "max_grid_side": int(math.isqrt(_MAX_PATCH_TOKENS)),
            "epsilon": float(metadata["clip.vision.attention.layer_norm_epsilon"]),
            "optional_norms": optional_norms,
        }

    def _require_open(self) -> None:
        if self._closed:
            raise QwenVisionError("Qwen vision encoder is closed")

    def _tensor(
        self,
        name: str,
        shape: tuple[int, ...],
        *,
        cache: bool = False,
    ) -> Any:
        if cache and name in self._fixed_tensors:
            return self._fixed_tensors[name]
        try:
            value = self._bank.tensor(name)
        except WeightBankError:
            raise
        except Exception as exc:
            raise QwenVisionError(f"could not read projector tensor {name!r}: {exc}") from exc
        if value.shape != shape:
            raise QwenVisionError(
                f"projector tensor {name!r} decoded as {value.shape}, expected {shape}"
            )
        value = np.ascontiguousarray(value, dtype=np.float32)
        if not np.isfinite(value).all():
            raise QwenVisionError(f"projector tensor {name!r} contains non-finite values")
        if self._torch is not None:
            value = self._torch.from_numpy(value).to(device=self._device)
        if cache:
            self._fixed_tensors[name] = value
        return value

    def _block(self, index: int) -> dict[str, Any]:
        cached = self._block_cache.get(index)
        if cached is not None:
            if self._torch is not None:
                self._block_cache.move_to_end(index)
            self._cache_hits += 1
            self._metadata["vision_residency"]["cache_hits"] = self._cache_hits
            return cached
        prefix = f"v.blk.{index}."
        width = self._config["width"]
        ff_width = self._config["ff_width"]
        shapes = {
            "ln1.weight": (width,),
            "ln1.bias": (width,),
            "attn_qkv.weight": (3 * width, width),
            "attn_qkv.bias": (3 * width,),
            "attn_out.weight": (width, width),
            "attn_out.bias": (width,),
            "ln2.weight": (width,),
            "ln2.bias": (width,),
            "ffn_up.weight": (ff_width, width),
            "ffn_up.bias": (ff_width,),
            "ffn_down.weight": (width, ff_width),
            "ffn_down.bias": (width,),
        }
        values = {key: self._tensor(prefix + key, shape) for key, shape in shapes.items()}
        block_bytes = (
            sum(
                int(tensor.numel()) * int(tensor.element_size())
                for tensor in values.values()
            )
            if self._torch is not None
            else sum(int(tensor.nbytes) for tensor in values.values())
        )
        self._cache_dequantizations += 1
        if (
            block_bytes <= self._block_cache_budget_bytes
            and self._block_cache_bytes + block_bytes <= self._block_cache_budget_bytes
            and len(self._block_cache) < self._max_cached_blocks
        ):
            if self._torch is None:
                for tensor in values.values():
                    tensor.flags.writeable = False
            self._block_cache[index] = values
            self._block_cache_bytes += block_bytes
        self._metadata["vision_residency"].update(
            block_cache_bytes=self._block_cache_bytes,
            cached_blocks=len(self._block_cache),
            block_dequantizations=self._cache_dequantizations,
        )
        return values

    def _configure_cpu_block_cache(self) -> None:
        """Pin the low-index CPU block cohort that fits the measured RAM budget."""
        available_bytes = _available_host_memory_bytes()
        if available_bytes is None:
            budget = 0
        else:
            fixed_bytes = sum(int(value.nbytes) for value in self._fixed_tensors.values())
            available_for_cache = (
                available_bytes
                + fixed_bytes
                + self._block_cache_bytes
                + self._rotary_cache_bytes
            )
            budget = min(
                int(available_for_cache * _VISION_CACHE_FRACTION),
                _VISION_CACHE_CAP_BYTES,
            )
        block_bytes = _vision_block_bytes(
            self._config["width"], self._config["ff_width"]
        )
        self._block_cache_budget_bytes = budget
        self._max_cached_blocks = min(
            self._config["layers"], budget // max(block_bytes, 1)
        )
        while (
            self._block_cache
            and (
                self._block_cache_bytes > budget
                or len(self._block_cache) > self._max_cached_blocks
            )
        ):
            _old_index, old = self._block_cache.popitem(last=True)
            self._block_cache_bytes -= sum(int(tensor.nbytes) for tensor in old.values())
        self._metadata["vision_residency"].update(
            block_cache_budget_bytes=budget,
            block_cache_bytes=self._block_cache_bytes,
            cached_blocks=len(self._block_cache),
        )

    def _preload_rocm(self) -> None:
        """Cache fixed tensors and budgeted immutable transformer blocks."""
        if self._torch is None:
            return
        width = self._config["width"]
        projection_width = self._config["projection_width"]
        try:
            free_bytes, _total_bytes = self._torch.cuda.mem_get_info(self._device)
            available_for_cache = int(free_bytes) + self._block_cache_bytes
            budget = min(int(available_for_cache * _VISION_CACHE_FRACTION), _VISION_CACHE_CAP_BYTES)
            self._block_cache_budget_bytes = budget
            block_bytes = _vision_block_bytes(width, self._config["ff_width"])
            self._max_cached_blocks = min(
                self._config["layers"], budget // max(block_bytes, 1)
            )
            while self._block_cache and self._block_cache_bytes > budget:
                _old_index, old = self._block_cache.popitem(last=True)
                self._block_cache_bytes -= sum(
                    int(tensor.numel()) * int(tensor.element_size()) for tensor in old.values()
                )
            self._metadata["vision_residency"].update(
                block_cache_budget_bytes=budget,
                block_cache_bytes=self._block_cache_bytes,
                cached_blocks=len(self._block_cache),
            )
            self._tensor("v.patch_embd.weight", (width, 3, 16, 16), cache=True)
            self._tensor("v.patch_embd.bias", (width,), cache=True)
            self._tensor("v.position_embd.weight", (48 * 48, width), cache=True)
            for norm in self._config["optional_norms"].values():
                self._tensor(norm["weight"], (width,), cache=True)
                if norm["bias"] is not None:
                    self._tensor(norm["bias"], (width,), cache=True)
            self._tensor("mm.0.weight", (4 * width, 4 * width), cache=True)
            self._tensor("mm.0.bias", (4 * width,), cache=True)
            self._tensor("mm.2.weight", (projection_width, 4 * width), cache=True)
            self._tensor("mm.2.bias", (projection_width,), cache=True)
            self._torch.cuda.synchronize(self._device)
        except self._torch.OutOfMemoryError as exc:
            if not self._auto_backend:
                raise QwenVisionError("ROCm device cannot retain required Qwen vision weights") from exc
            self._fixed_tensors.clear()
            self._block_cache.clear()
            self._block_cache_bytes = 0
            self._torch.cuda.empty_cache()
            self._torch = None
            self._device = None
            self._max_cached_blocks = _MAX_CACHED_BLOCKS
            self._block_cache_budget_bytes = 0
            self._compute_backend = "numpy-cpu"
            self._metadata["compute_backend"] = self._compute_backend
            self._metadata["vision_residency"].update(
                block_cache_budget_bytes=0, block_cache_bytes=0, cached_blocks=0
            )
        except Exception:
            self._fixed_tensors.clear()
            self._block_cache.clear()
            self._block_cache_bytes = 0
            self._torch.cuda.empty_cache()
            raise

    def _norm(
        self,
        values: Any,
        scale: Any,
        bias: Any | None,
        epsilon: float,
    ) -> Any:
        if isinstance(values, np.ndarray):
            mean = np.mean(values, axis=-1, keepdims=True, dtype=np.float32)
            centered = values - mean
            variance = np.mean(centered * centered, axis=-1, keepdims=True, dtype=np.float32)
            centered *= np.reciprocal(np.sqrt(variance + np.float32(epsilon)))
        else:
            mean = values.mean(dim=-1, keepdim=True)
            centered = values - mean
            variance = (centered * centered).mean(dim=-1, keepdim=True)
            centered = centered * self._torch.rsqrt(variance + epsilon)
        centered *= scale
        if bias is not None:
            centered += bias
        return centered

    def _gelu_in_place(self, values: Any) -> None:
        # Match ggml_vec_gelu_f32, including its tanh approximation.
        if isinstance(values, np.ndarray):
            temp = values.copy()
            np.square(temp, out=temp)
            temp *= _GELU_COEF
            temp += np.float32(1.0)
            temp *= values
            temp *= _GELU_SQRT_2_OVER_PI
            np.tanh(temp, out=temp)
            temp += np.float32(1.0)
            temp *= np.float32(0.5)
            values *= temp
        else:
            temp = values * values
            temp.mul_(_GELU_COEF).add_(1.0).mul_(values).mul_(_GELU_SQRT_2_OVER_PI)
            temp.tanh_().add_(1.0).mul_(0.5)
            values *= temp


    def _exchange(
        self,
        exchange: Callable[[str, np.ndarray], np.ndarray] | None,
        site: str,
        values: np.ndarray,
    ) -> np.ndarray:
        if exchange is None:
            return values
        try:
            steered = exchange(site, values)
        except Exception as exc:
            raise QwenVisionError(f"field exchange failed at {site}: {exc}") from exc
        if not isinstance(steered, np.ndarray):
            raise QwenVisionError(f"field exchange at {site} must return a NumPy array")
        if steered.shape != values.shape:
            raise QwenVisionError(
                f"field exchange at {site} changed shape from {values.shape} to {steered.shape}"
            )
        if not np.issubdtype(steered.dtype, np.number):
            raise QwenVisionError(f"field exchange at {site} returned a non-numeric array")
        steered = np.asarray(steered, dtype=np.float32)
        if not np.isfinite(steered).all():
            raise QwenVisionError(f"field exchange at {site} returned non-finite values")
        if not steered.flags.c_contiguous or not steered.flags.writeable:
            steered = np.array(steered, dtype=np.float32, order="C", copy=True)
        return steered

    def _exchange_device(
        self,
        exchange: Callable[[str, np.ndarray], np.ndarray] | None,
        site: str,
        values: Any,
    ) -> Any:
        if exchange is None:
            return values
        if self._torch is None:
            return self._exchange(exchange, site, values)
        host = values.detach().to(device="cpu").numpy()
        steered = self._exchange(exchange, site, host)
        if np.array_equal(steered, host):
            self._exchange_device_copies_avoided += 1
            self._metadata["vision_residency"]["exchange_device_copies_avoided"] = (
                self._exchange_device_copies_avoided
            )
            return values
        return self._torch.from_numpy(steered).to(device=self._device)


    @staticmethod
    def _aligned_size(width: int, height: int, max_pixels: int, max_edge: int) -> tuple[int, int]:
        alignment = 32

        def nearest(value: float) -> int:
            return max(alignment, int(math.floor(value / alignment + 0.5)) * alignment)

        def floor_align(value: float) -> int:
            return max(alignment, int(math.floor(value / alignment)) * alignment)

        target_w = nearest(float(width))
        target_h = nearest(float(height))
        if max(target_w, target_h) > max_edge:
            scale = max_edge / max(width, height)
            target_w = floor_align(width * scale)
            target_h = floor_align(height * scale)
        if target_w * target_h > max_pixels:
            scale = math.sqrt((width * height) / max_pixels)
            target_w = floor_align(width / scale)
            target_h = floor_align(height / scale)
        while target_w * target_h > max_pixels:
            if target_w >= target_h and target_w > alignment:
                target_w -= alignment
            elif target_h > alignment:
                target_h -= alignment
            else:
                raise QwenVisionError("image cannot fit the bounded Qwen patch grid")
        if target_w > max_edge or target_h > max_edge:
            raise QwenVisionError("image exceeds the maximum aligned Qwen input edge")
        return target_w, target_h

    @staticmethod
    def _resize_bilinear_u8(image: np.ndarray, width: int, height: int) -> np.ndarray:
        source_h, source_w, _channels = image.shape
        if (source_w, source_h) == (width, height):
            return image
        x = np.zeros(1, dtype=np.float32) if width == 1 else np.arange(width, dtype=np.float32) * np.float32((source_w - 1) / (width - 1))
        y = np.zeros(1, dtype=np.float32) if height == 1 else np.arange(height, dtype=np.float32) * np.float32((source_h - 1) / (height - 1))
        x0 = np.floor(x).astype(np.intp)
        y0 = np.floor(y).astype(np.intp)
        x1 = np.minimum(x0 + 1, source_w - 1)
        y1 = np.minimum(y0 + 1, source_h - 1)
        xf = (x - x0).reshape(1, width, 1)
        yf = (y - y0).reshape(height, 1, 1)
        top = image[y0[:, None], x0[None, :], :].astype(np.float32)
        top += (image[y0[:, None], x1[None, :], :].astype(np.float32) - top) * xf
        bottom = image[y1[:, None], x0[None, :], :].astype(np.float32)
        bottom += (image[y1[:, None], x1[None, :], :].astype(np.float32) - bottom) * xf
        top += (bottom - top) * yf
        return top.astype(np.uint8)

    def _decode_png(self, png: bytes) -> tuple[np.ndarray, int, int]:
        if not isinstance(png, bytes) or not png:
            raise QwenVisionError("image input must be non-empty PNG bytes")
        if len(png) > _MAX_PNG_BYTES:
            raise QwenVisionError(f"PNG exceeds the {_MAX_PNG_BYTES}-byte input limit")
        try:
            with Image.open(BytesIO(png)) as source:
                if source.format != "PNG":
                    raise QwenVisionError("Qwen visual input must be a PNG image")
                width, height = source.size
                if (
                    width <= 0
                    or height <= 0
                    or width > _MAX_SOURCE_EDGE
                    or height > _MAX_SOURCE_EDGE
                    or width * height > _MAX_SOURCE_PIXELS
                ):
                    raise QwenVisionError("PNG dimensions exceed the bounded source image limits")
                if getattr(source, "n_frames", 1) != 1:
                    raise QwenVisionError("animated PNGs are not supported; provide a single image frame")
                source.load()
                rgb = np.asarray(source.convert("RGB"), dtype=np.uint8)
        except QwenVisionError:
            raise
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise QwenVisionError(f"cannot decode PNG image: {exc}") from exc

        target_w, target_h = self._aligned_size(
            width,
            height,
            self._config["max_runtime_pixels"],
            _MAX_SOURCE_EDGE,
        )
        rgb = self._resize_bilinear_u8(rgb, target_w, target_h)
        grid_w = target_w // self._config["patch_size"]
        grid_h = target_h // self._config["patch_size"]
        patch_count = grid_w * grid_h
        if patch_count > _MAX_PATCH_TOKENS:
            raise QwenVisionError(
                f"Qwen patch grid has {patch_count} tokens, exceeding the {_MAX_PATCH_TOKENS}-token limit"
            )
        return rgb, grid_h, grid_w

    def _resize_positions(self, source: Any, height: int, width: int) -> Any:
        source_side = int(math.isqrt(source.shape[0]))
        if source_side * source_side != source.shape[0]:
            raise QwenVisionError("learned position embedding table is not a square grid")
        feature_width = source.shape[1]
        source_grid = source.reshape(source_side, source_side, feature_width)
        if (height, width) == (source_side, source_side):
            return source_grid
        if isinstance(source, np.ndarray):
            y = np.linspace(0, source_side - 1, height, dtype=np.float32)
            x = np.linspace(0, source_side - 1, width, dtype=np.float32)
            y0 = np.floor(y).astype(np.intp)
            x0 = np.floor(x).astype(np.intp)
            y1 = np.minimum(y0 + 1, source_side - 1)
            x1 = np.minimum(x0 + 1, source_side - 1)
            yf = y - y0
            xf = x - x0
            result = np.empty((height, width, feature_width), dtype=np.float32)
            for row in range(height):
                top = source_grid[y0[row], x0] + (
                    source_grid[y0[row], x1] - source_grid[y0[row], x0]
                ) * xf[:, None]
                bottom = source_grid[y1[row], x0] + (
                    source_grid[y1[row], x1] - source_grid[y1[row], x0]
                ) * xf[:, None]
                result[row] = top + (bottom - top) * yf[row]
            return result
        image = source_grid.permute(2, 0, 1).unsqueeze(0)
        resized = self._torch.nn.functional.interpolate(
            image,
            size=(height, width),
            mode="bilinear",
            align_corners=True,
        )
        return resized.squeeze(0).permute(1, 2, 0)

    @staticmethod
    def _reorder_patch_grid(values: Any, grid_h: int, grid_w: int) -> Any:
        width = values.shape[-1]
        if isinstance(values, np.ndarray):
            return (
                values.reshape(grid_h // 2, 2, grid_w // 2, 2, width)
                .transpose(0, 2, 1, 3, 4)
                .reshape(grid_h * grid_w, width)
            )
        return (
            values.reshape(grid_h // 2, 2, grid_w // 2, 2, width)
            .permute(0, 2, 1, 3, 4)
            .reshape(grid_h * grid_w, width)
        )


    @staticmethod
    def _rotary_tables(
        rows: np.ndarray,
        columns: np.ndarray,
        head_width: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        # GGML_ROPE_TYPE_VISION uses 18 independent pairs for each spatial axis
        # at d_head=72, with a distinct frequency sequence for each axis.
        axis_pairs = head_width // 4
        frequency = np.power(
            np.float32(10000.0),
            -np.arange(axis_pairs, dtype=np.float32) * np.float32(2.0 / (head_width / 2)),
        )
        row_phase = rows.astype(np.float32)[:, None] * frequency[None, :]
        col_phase = columns.astype(np.float32)[:, None] * frequency[None, :]
        return (
            np.cos(row_phase).astype(np.float32),
            np.sin(row_phase).astype(np.float32),
            np.cos(col_phase).astype(np.float32),
            np.sin(col_phase).astype(np.float32),
        )

    def _rotary_for_grid(
        self, grid_h: int, grid_w: int
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        head_width = self._config["head_width"]
        key = (self.projector_sha256, grid_h, grid_w, head_width)
        if (
            self._torch is None
            and key == self._rotary_cache_key
            and self._rotary_cache_tables is not None
        ):
            self._rotary_cache_hits += 1
            self._metadata["vision_residency"]["rotary_cache_hits"] = (
                self._rotary_cache_hits
            )
            return self._rotary_cache_tables

        if self._torch is None and self._rotary_cache_key != key:
            self._rotary_cache_key = None
            self._rotary_cache_tables = None
            self._rotary_cache_bytes = 0
            self._metadata["vision_residency"]["rotary_cache_bytes"] = 0
        n_patches = grid_h * grid_w
        grid_rows = np.repeat(np.arange(grid_h, dtype=np.int32), grid_w).reshape(
            grid_h, grid_w
        )
        grid_columns = np.broadcast_to(
            np.arange(grid_w, dtype=np.int32), (grid_h, grid_w)
        )
        rows = self._reorder_patch_grid(
            grid_rows.reshape(n_patches, 1), grid_h, grid_w
        )[:, 0]
        columns = self._reorder_patch_grid(
            grid_columns.reshape(n_patches, 1), grid_h, grid_w
        )[:, 0]
        rotary = self._rotary_tables(rows, columns, head_width)
        if self._torch is None:
            rotary_bytes = sum(int(table.nbytes) for table in rotary)
            max_rotary_bytes = (
                _MAX_PATCH_TOKENS
                * 4
                * (head_width // 4)
                * np.dtype(np.float32).itemsize
            )
            if rotary_bytes <= max_rotary_bytes:
                for table in rotary:
                    table.flags.writeable = False
                self._rotary_cache_key = key
                self._rotary_cache_tables = rotary
                self._rotary_cache_bytes = rotary_bytes
                self._metadata["vision_residency"].update(
                    rotary_cache_bytes=rotary_bytes,
                    rotary_cache_hits=self._rotary_cache_hits,
                )
        return rotary


    def _rotate_axis(
        self,
        values: Any,
        start: int,
        cosine: Any,
        sine: Any,
    ) -> None:
        stop = start + 2 * cosine.shape[-1]
        even = values[:, :, start:stop:2].clone() if not isinstance(values, np.ndarray) else values[:, :, start:stop:2].copy()
        odd = values[:, :, start + 1:stop:2].clone() if not isinstance(values, np.ndarray) else values[:, :, start + 1:stop:2].copy()
        if isinstance(values, np.ndarray):
            cos = cosine[:, None, :]
            sin = sine[:, None, :]
        else:
            cos = cosine.unsqueeze(1)
            sin = sine.unsqueeze(1)
        values[:, :, start:stop:2] = even * cos - odd * sin
        values[:, :, start + 1:stop:2] = even * sin + odd * cos

    def _attention(
        self,
        qkv: Any,
        v_width: int,
        heads: int,
        head_width: int,
        rotary: tuple[Any, Any, Any, Any],
    ) -> Any:
        n_tokens = qkv.shape[0]
        qkv = qkv.reshape(n_tokens, 3, heads, head_width)
        query, key, value = qkv[:, 0], qkv[:, 1], qkv[:, 2]
        cos_y, sin_y, cos_x, sin_x = rotary
        self._rotate_axis(query, 0, cos_y, sin_y)
        self._rotate_axis(query, head_width // 2, cos_x, sin_x)
        self._rotate_axis(key, 0, cos_y, sin_y)
        self._rotate_axis(key, head_width // 2, cos_x, sin_x)

        scale = 1.0 / math.sqrt(head_width)
        if isinstance(qkv, np.ndarray):
            context = np.empty((n_tokens, heads, head_width), dtype=np.float32)
            scores = np.empty((n_tokens, n_tokens), dtype=np.float32)
            for head in range(heads):
                np.matmul(query[:, head, :], key[:, head, :].T, out=scores)
                scores *= np.float32(scale)
                scores -= np.max(scores, axis=1, keepdims=True)
                np.exp(scores, out=scores)
                scores /= np.sum(scores, axis=1, keepdims=True, dtype=np.float32)
                context[:, head, :] = scores @ value[:, head, :]
        else:
            context = self._torch.empty(
                (n_tokens, heads, head_width),
                dtype=qkv.dtype,
                device=qkv.device,
            )
            for head in range(heads):
                scores = query[:, head, :] @ key[:, head, :].transpose(0, 1)
                scores.mul_(scale)
                scores.sub_(scores.amax(dim=1, keepdim=True))
                scores = self._torch.softmax(scores, dim=1)
                context[:, head, :] = scores @ value[:, head, :]
        return context.reshape(n_tokens, v_width)

    def encode_png(
        self,
        png: bytes,
        *,
        exchange: Callable[[str, np.ndarray], np.ndarray] | None = None,
    ) -> np.ndarray:
        """Return finite Qwen image-token embeddings with shape ``(N, 2048)``."""
        if exchange is not None and not callable(exchange):
            raise QwenVisionError("exchange must be callable or None")
        with self._lock:
            self._require_open()
            self._last_image_grid = None
            self._preload_rocm()

            rgb, grid_h, grid_w = self._decode_png(png)
            width = self._config["width"]
            patch_size = self._config["patch_size"]
            n_patches = grid_h * grid_w
            normalized = rgb.astype(np.float32)
            normalized *= np.float32(1.0 / 255.0)
            normalized -= np.asarray(self._config["image_mean"], dtype=np.float32)
            normalized /= np.asarray(self._config["image_std"], dtype=np.float32)

            patches_view = np.lib.stride_tricks.sliding_window_view(
                normalized, (patch_size, patch_size), axis=(0, 1)
            )[::patch_size, ::patch_size]
            patches = np.ascontiguousarray(
                patches_view.reshape(n_patches, -1), dtype=np.float32
            )
            patch_weight = self._tensor(
                "v.patch_embd.weight",
                (width, 3, patch_size, patch_size),
                cache=True,
            )
            patch_bias = self._tensor("v.patch_embd.bias", (width,), cache=True)
            if self._torch is None:
                hidden = patches @ patch_weight.reshape(width, -1).T
                hidden += patch_bias
            else:
                patch_values = self._torch.from_numpy(patches).to(device=self._device)
                hidden = patch_values @ patch_weight.reshape(width, -1).T
                hidden += patch_bias
                del patch_values
            hidden = self._reorder_patch_grid(hidden, grid_h, grid_w)

            position_table = self._tensor("v.position_embd.weight", (48 * 48, width), cache=True)
            position = self._resize_positions(position_table, grid_h, grid_w)
            position = self._reorder_patch_grid(position.reshape(n_patches, width), grid_h, grid_w)
            hidden += position

            pre_norm = self._config["optional_norms"].get("pre_ln")
            if pre_norm is not None:
                hidden = self._norm(
                    hidden,
                    self._tensor(pre_norm["weight"], (width,), cache=True),
                    self._tensor(pre_norm["bias"], (width,), cache=True)
                    if pre_norm["bias"] is not None
                    else None,
                    self._config["epsilon"],
                )
            hidden = self._exchange_device(exchange, "vision.patch", hidden)

            rotary: tuple[Any, Any, Any, Any] = self._rotary_for_grid(grid_h, grid_w)
            if self._torch is not None:
                rotary = tuple(
                    self._torch.as_tensor(value, device=self._device) for value in rotary
                )
            if self._torch is None:
                self._configure_cpu_block_cache()

            heads = self._config["heads"]
            head_width = self._config["head_width"]
            epsilon = self._config["epsilon"]
            for index in range(self._config["layers"]):
                layer = self._block(index)
                normed = self._norm(hidden, layer["ln1.weight"], layer["ln1.bias"], epsilon)
                qkv = normed @ layer["attn_qkv.weight"].T
                qkv += layer["attn_qkv.bias"]
                attention = self._attention(qkv, width, heads, head_width, rotary)
                del normed, qkv
                attention = attention @ layer["attn_out.weight"].T
                attention += layer["attn_out.bias"]
                hidden += attention
                del attention

                normed = self._norm(hidden, layer["ln2.weight"], layer["ln2.bias"], epsilon)
                intermediate = normed @ layer["ffn_up.weight"].T
                intermediate += layer["ffn_up.bias"]
                self._gelu_in_place(intermediate)
                feed_forward = intermediate @ layer["ffn_down.weight"].T
                feed_forward += layer["ffn_down.bias"]
                hidden += feed_forward
                del normed, intermediate, feed_forward
                hidden = self._exchange_device(exchange, f"vision.block.{index}", hidden)

            post_norm = self._config["optional_norms"].get("post_ln")
            if post_norm is not None:
                hidden = self._norm(
                    hidden,
                    self._tensor(post_norm["weight"], (width,), cache=True),
                    self._tensor(post_norm["bias"], (width,), cache=True)
                    if post_norm["bias"] is not None
                    else None,
                    epsilon,
                )

            merged = hidden.reshape(n_patches // 4, 4 * width)
            mm0_weight = self._tensor("mm.0.weight", (4 * width, 4 * width), cache=True)
            mm0_bias = self._tensor("mm.0.bias", (4 * width,), cache=True)
            merged = merged @ mm0_weight.T
            merged += mm0_bias
            self._gelu_in_place(merged)
            merged = self._exchange_device(exchange, "vision.merge", merged)

            mm2_weight = self._tensor(
                "mm.2.weight",
                (self._config["projection_width"], 4 * width),
                cache=True,
            )
            mm2_bias = self._tensor(
                "mm.2.bias",
                (self._config["projection_width"],),
                cache=True,
            )
            embeddings = merged @ mm2_weight.T
            embeddings += mm2_bias
            if embeddings.ndim != 2 or embeddings.shape[1] != self._config["projection_width"]:
                raise QwenVisionError("Qwen merger produced an invalid image-token embedding shape")
            if self._torch is None:
                if not np.isfinite(embeddings).all():
                    raise QwenVisionError("Qwen vision graph produced non-finite image-token embeddings")
                result = np.ascontiguousarray(embeddings, dtype=np.float32)
            else:
                if not bool(self._torch.isfinite(embeddings).all().item()):
                    raise QwenVisionError("Qwen vision graph produced non-finite image-token embeddings")
                result = np.ascontiguousarray(
                    embeddings.detach().to(device="cpu").numpy(),
                    dtype=np.float32,
                )
            merged_grid = (
                grid_h // self._config["merge_size"],
                grid_w // self._config["merge_size"],
            )
            if result.shape[0] != merged_grid[0] * merged_grid[1]:
                raise QwenVisionError("Qwen merger output does not match its merged spatial grid")
            self._last_image_grid = merged_grid
            return result

    def close(self) -> None:
        """Release the immutable projector weight bank; safe to call repeatedly."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._fixed_tensors.clear()
            self._block_cache.clear()
            self._block_cache_bytes = 0
            self._rotary_cache_key = None
            self._rotary_cache_tables = None
            self._rotary_cache_bytes = 0
            self._metadata["vision_residency"].update(
                block_cache_bytes=0,
                cached_blocks=0,
                rotary_cache_bytes=0,
            )
            self._bank.close()
            self._last_image_grid = None
            if self._torch is not None:
                self._torch.cuda.empty_cache()

    def __enter__(self) -> "QwenVisionEncoder":
        with self._lock:
            self._require_open()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def __del__(self) -> None:  # pragma: no cover - interpreter shutdown path
        try:
            self.close()
        except Exception:
            pass
