"""Differentiable mirror of the native batched Cassi modal recurrence.

This module follows the production ``GGML_OP_CASSI_MODAL`` tensor contract and
its linear x-fast mode ordering.  It is a training/reference surface; the native
GGML/Vulkan operation remains the inference implementation.

The native contract is:

* layer modes: ``[2*M, L, T]``
* persistent state: ``[8*M, S]``
* mode symbols: ``[M]``
* token-to-sequence routing: ``[T]``
* correction: ``[2*M, T]``
* final state: ``[8*M, S]``

State components for each mode are ordered
``EY.re, EY.im, EI.re, EI.im, VY.re, VY.im, VI.re, VI.im``.  This ordering is
not the canonical conjugate-pair ordering used by the older L18 Python field
codec; checkpoints must bind ``MODE_LAYOUT_ID`` and never mix the two layouts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import NamedTuple

import torch
from torch import Tensor, nn
from torch.nn import functional as F


MODE_LAYOUT_ID = "cassi.modal.native-linear-x-fast.v1"
OPERATOR_PROFILE_ID = "cassi.modal.recurrence.v1"
DEFAULT_GRID_N = 32


class CassiModalTorchError(ValueError):
    """Invalid tensor, recurrence, or adapter configuration."""


@dataclass(frozen=True)
class CassiModalConfig:
    """Scalar controls frozen by the production native recurrence."""

    retained_weight: float = 0.9
    phi: float = 1.618033988749895
    dt: float = 0.005
    omega2: float = 20.0
    coupling: float = 1.0
    steps_per_layer: int = 4

    def __post_init__(self) -> None:
        finite = (
            self.retained_weight,
            self.phi,
            self.dt,
            self.omega2,
            self.coupling,
        )
        if not all(math.isfinite(value) for value in finite):
            raise CassiModalTorchError("modal controls must be finite")
        if not 0.0 <= self.retained_weight <= 1.0:
            raise CassiModalTorchError("retained_weight must be in [0, 1]")
        if self.phi <= 0.0 or self.dt <= 0.0 or self.omega2 <= 0.0 or self.coupling <= 0.0:
            raise CassiModalTorchError("phi, dt, omega2, and coupling must be positive")
        if isinstance(self.steps_per_layer, bool) or not isinstance(self.steps_per_layer, int) or self.steps_per_layer < 1:
            raise CassiModalTorchError("steps_per_layer must be a positive integer")


class CassiModalOutput(NamedTuple):
    correction: Tensor
    state: Tensor


class CassiFieldAdapterOutput(NamedTuple):
    hidden: Tensor
    residual: Tensor
    gate: Tensor


def native_mode_params(
    mode_count: int,
    *,
    grid_n: int = DEFAULT_GRID_N,
    dtype: torch.dtype = torch.float32,
    device: torch.device | str | None = None,
) -> Tensor:
    """Return the finite-difference symbols used by ``llama-graph.cpp``.

    Mode ``m`` maps to ``x=m%N, y=(m//N)%N, z=m//(N*N)``.  In particular,
    this includes the DC mode at ``m=0`` and intentionally does not use the
    canonical conjugate-pair ordering from the L18 codec.
    """

    if isinstance(mode_count, bool) or not isinstance(mode_count, int) or mode_count < 1:
        raise CassiModalTorchError("mode_count must be a positive integer")
    if isinstance(grid_n, bool) or not isinstance(grid_n, int) or grid_n < 1:
        raise CassiModalTorchError("grid_n must be a positive integer")
    if not dtype.is_floating_point:
        raise CassiModalTorchError("mode parameters require a floating dtype")

    modes = torch.arange(mode_count, dtype=torch.int64, device=device)
    x = (modes % grid_n).to(dtype)
    y = ((modes // grid_n) % grid_n).to(dtype)
    z = (modes // (grid_n * grid_n)).to(dtype)
    scale = torch.as_tensor(2.0 * math.pi / float(grid_n), dtype=dtype, device=device)
    cx = torch.cos(scale * x)
    cy = torch.cos(scale * y)
    cz = torch.cos(scale * z)
    symbol = (
        ((cx - 1.0) + (cy - 1.0) + (cz - 1.0)) / 3.0
        + 2.0 * ((cx * cy - 1.0) + (cy * cz - 1.0) + (cz * cx - 1.0)) / 3.0
    )
    return torch.where(torch.isfinite(symbol), symbol, torch.zeros_like(symbol))


def _validate_modal_inputs(
    layer_modes: Tensor,
    state: Tensor,
    mode_params: Tensor,
    seq_ids: Tensor,
) -> tuple[int, int, int, int]:
    if layer_modes.ndim != 3:
        raise CassiModalTorchError("layer_modes must have shape [2*M, L, T]")
    if layer_modes.shape[0] < 2 or layer_modes.shape[0] % 2:
        raise CassiModalTorchError("layer_modes first dimension must be positive and even")
    mode_count = layer_modes.shape[0] // 2
    layer_count = layer_modes.shape[1]
    token_count = layer_modes.shape[2]
    if layer_count < 1 or token_count < 1:
        raise CassiModalTorchError("layer_modes requires at least one layer and token")

    if state.ndim != 2 or state.shape[0] != 8 * mode_count or state.shape[1] < 1:
        raise CassiModalTorchError("state must have shape [8*M, S] with S >= 1")
    sequence_count = state.shape[1]
    if mode_params.ndim != 1 or mode_params.shape[0] != mode_count:
        raise CassiModalTorchError("mode_params must have shape [M]")
    if seq_ids.ndim != 1 or seq_ids.shape[0] != token_count:
        raise CassiModalTorchError("seq_ids must have shape [T]")

    if not layer_modes.dtype.is_floating_point or state.dtype != layer_modes.dtype or mode_params.dtype != layer_modes.dtype:
        raise CassiModalTorchError("layer_modes, state, and mode_params must share one floating dtype")
    if layer_modes.device != state.device or layer_modes.device != mode_params.device or layer_modes.device != seq_ids.device:
        raise CassiModalTorchError("all modal tensors must share one device")
    if seq_ids.dtype not in (torch.int32, torch.int64):
        raise CassiModalTorchError("seq_ids must use int32 or int64")

    if bool(torch.any(seq_ids < 0).item()) or bool(torch.any(seq_ids >= sequence_count).item()):
        raise CassiModalTorchError("seq_ids contains a sequence outside [0, S)")
    return mode_count, layer_count, token_count, sequence_count


def cassi_modal_forward(
    layer_modes: Tensor,
    state: Tensor,
    mode_params: Tensor,
    seq_ids: Tensor,
    config: CassiModalConfig = CassiModalConfig(),
) -> CassiModalOutput:
    """Evaluate the native recurrence with an autograd-preserving graph.

    Tokens are processed in ascending order.  Each token mutates only the state
    selected by ``seq_ids[token]``; interleaved sequences therefore carry their
    own recurrent histories exactly as the native CPU and Vulkan kernels do.
    """

    mode_count, layer_count, token_count, sequence_count = _validate_modal_inputs(
        layer_modes, state, mode_params, seq_ids
    )

    # Native state semantics are state[8*mode + component, sequence].
    unpacked = state.transpose(0, 1).reshape(sequence_count, mode_count, 8)
    ey_re, ey_im, ei_re, ei_im, vy_re, vy_im, vi_re, vi_im = unpacked.unbind(dim=-1)

    retained = config.retained_weight
    incoming = 1.0 - retained
    phi = config.phi
    dt = config.dt
    omega2 = config.omega2
    coupling = config.coupling
    symbol = mode_params.reshape(1, mode_count)
    corrections: list[Tensor] = []

    for token in range(token_count):
        mask = F.one_hot(seq_ids[token].to(torch.int64), num_classes=sequence_count).to(layer_modes.dtype).reshape(sequence_count, 1)

        for layer in range(layer_count):
            signal_re = layer_modes[0::2, layer, token].reshape(1, mode_count)
            signal_im = layer_modes[1::2, layer, token].reshape(1, mode_count)

            candidate = retained * ey_re + incoming * 0.5 * signal_re
            ey_re = ey_re + mask * (candidate - ey_re)
            candidate = retained * ey_im + incoming * 0.5 * signal_im
            ey_im = ey_im + mask * (candidate - ey_im)
            candidate = retained * ei_re - incoming * 0.5 / phi * signal_re
            ei_re = ei_re + mask * (candidate - ei_re)
            candidate = retained * ei_im - incoming * 0.5 / phi * signal_im
            ei_im = ei_im + mask * (candidate - ei_im)

            for _ in range(config.steps_per_layer):
                diff_re = ey_re - phi * ei_re
                diff_im = ey_im - phi * ei_im
                acc_y_re = (symbol - omega2) * ey_re + omega2 * phi * ei_re
                acc_y_im = (symbol - omega2) * ey_im + omega2 * phi * ei_im
                acc_i_re = symbol * ei_re + omega2 * diff_re
                acc_i_im = symbol * ei_im + omega2 * diff_im

                next_vy_re = vy_re + acc_y_re * dt
                next_vy_im = vy_im + acc_y_im * dt
                next_vi_re = vi_re + acc_i_re * dt
                next_vi_im = vi_im + acc_i_im * dt
                next_ey_re = ey_re + next_vy_re * dt
                next_ey_im = ey_im + next_vy_im * dt
                next_ei_re = ei_re + next_vi_re * dt
                next_ei_im = ei_im + next_vi_im * dt

                vy_re = vy_re + mask * (next_vy_re - vy_re)
                vy_im = vy_im + mask * (next_vy_im - vy_im)
                vi_re = vi_re + mask * (next_vi_re - vi_re)
                vi_im = vi_im + mask * (next_vi_im - vi_im)
                ey_re = ey_re + mask * (next_ey_re - ey_re)
                ey_im = ey_im + mask * (next_ey_im - ey_im)
                ei_re = ei_re + mask * (next_ei_re - ei_re)
                ei_im = ei_im + mask * (next_ei_im - ei_im)

        correction_re = coupling * (ey_re - phi * ei_re)
        correction_im = -coupling * (ey_im - phi * ei_im)
        selected_re = torch.sum(mask * correction_re, dim=0)
        selected_im = torch.sum(mask * correction_im, dim=0)
        corrections.append(torch.stack((selected_re, selected_im), dim=-1).reshape(2 * mode_count))

    correction = torch.stack(corrections, dim=1)
    final_components = torch.stack((ey_re, ey_im, ei_re, ei_im, vy_re, vy_im, vi_re, vi_im), dim=-1)
    final_state = final_components.reshape(sequence_count, 8 * mode_count).transpose(0, 1).contiguous()
    return CassiModalOutput(correction=correction, state=final_state)


def cassi_modal_forward_parallel(
    layer_modes: Tensor,
    state: Tensor,
    mode_params: Tensor,
    config: CassiModalConfig = CassiModalConfig(),
) -> CassiModalOutput:
    """Fast autograd path for a token-major batch with one token per sequence.

    ``layer_modes`` has shape ``[2*M, L, B, T]``.  This is the common training
    layout for independent episodes: all sequence slots advance at each time
    step.  It is mathematically the same recurrence as ``cassi_modal_forward``
    with ``seq_ids = repeat(arange(B), T)`` but avoids a Python loop over every
    flattened token.
    """

    if layer_modes.ndim != 4:
        raise CassiModalTorchError("parallel layer_modes must have shape [2*M, L, B, T]")
    if state.ndim != 2 or mode_params.ndim != 1:
        raise CassiModalTorchError("parallel state and mode_params must be matrices/vectors")
    mode_count = layer_modes.shape[0] // 2
    layer_count = layer_modes.shape[1]
    batch_size = layer_modes.shape[2]
    horizon = layer_modes.shape[3]
    if layer_modes.shape[0] != 2 * mode_count or mode_count < 1 or layer_count < 1 or batch_size < 1 or horizon < 1:
        raise CassiModalTorchError("parallel layer_modes has invalid dimensions")
    if state.shape != (8 * mode_count, batch_size) or mode_params.shape != (mode_count,):
        raise CassiModalTorchError("parallel state/mode_params shape does not match layer_modes")
    if not layer_modes.dtype.is_floating_point or state.dtype != layer_modes.dtype or mode_params.dtype != layer_modes.dtype:
        raise CassiModalTorchError("parallel modal tensors must share one floating dtype")
    if layer_modes.device != state.device or layer_modes.device != mode_params.device:
        raise CassiModalTorchError("parallel modal tensors must share one device")

    unpacked = state.transpose(0, 1).reshape(batch_size, mode_count, 8)
    ey_re, ey_im, ei_re, ei_im, vy_re, vy_im, vi_re, vi_im = unpacked.unbind(dim=-1)
    retained = config.retained_weight
    incoming = 1.0 - retained
    phi = config.phi
    dt = config.dt
    omega2 = config.omega2
    coupling = config.coupling
    symbol = mode_params.reshape(1, mode_count)
    corrections: list[Tensor] = []

    for time in range(horizon):
        for layer in range(layer_count):
            signal_re = layer_modes[0::2, layer, :, time].transpose(0, 1)
            signal_im = layer_modes[1::2, layer, :, time].transpose(0, 1)
            ey_re = retained * ey_re + incoming * 0.5 * signal_re
            ey_im = retained * ey_im + incoming * 0.5 * signal_im
            ei_re = retained * ei_re - incoming * 0.5 / phi * signal_re
            ei_im = retained * ei_im - incoming * 0.5 / phi * signal_im

            for _ in range(config.steps_per_layer):
                diff_re = ey_re - phi * ei_re
                diff_im = ey_im - phi * ei_im
                acc_y_re = (symbol - omega2) * ey_re + omega2 * phi * ei_re
                acc_y_im = (symbol - omega2) * ey_im + omega2 * phi * ei_im
                acc_i_re = symbol * ei_re + omega2 * diff_re
                acc_i_im = symbol * ei_im + omega2 * diff_im
                vy_re = vy_re + acc_y_re * dt
                vy_im = vy_im + acc_y_im * dt
                vi_re = vi_re + acc_i_re * dt
                vi_im = vi_im + acc_i_im * dt
                ey_re = ey_re + vy_re * dt
                ey_im = ey_im + vy_im * dt
                ei_re = ei_re + vi_re * dt
                ei_im = ei_im + vi_im * dt

        correction_re = coupling * (ey_re - phi * ei_re)
        correction_im = -coupling * (ey_im - phi * ei_im)
        corrections.append(torch.stack((correction_re, correction_im), dim=-1).reshape(batch_size, 2 * mode_count))

    correction = torch.stack(corrections, dim=1).permute(2, 0, 1).contiguous()
    final_components = torch.stack((ey_re, ey_im, ei_re, ei_im, vy_re, vy_im, vi_re, vi_im), dim=-1)
    final_state = final_components.reshape(batch_size, 8 * mode_count).transpose(0, 1).contiguous()
    return CassiModalOutput(correction=correction, state=final_state)


def pack_native_output(output: CassiModalOutput) -> Tensor:
    """Pack an output as native ``[correction-by-token, state-by-sequence]``."""

    if output.correction.ndim != 2 or output.state.ndim != 2:
        raise CassiModalTorchError("correction and state must both be matrices")
    return torch.cat((output.correction.transpose(0, 1).reshape(-1), output.state.transpose(0, 1).reshape(-1)))


class CassiFieldAdapter(nn.Module):
    """Bounded low-rank residual driven by a Cassi field correction.

    The up projection is zero-initialized, so an untrained adapter is an exact
    identity while the underlying modal substrate remains active.  Training can
    then learn a bounded correction without modifying the frozen Qwen trunk or
    output head.
    """

    def __init__(self, dimension: int, bottleneck: int = 256, *, max_scale: float = 1.0) -> None:
        super().__init__()
        if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension < 1:
            raise CassiModalTorchError("dimension must be a positive integer")
        if isinstance(bottleneck, bool) or not isinstance(bottleneck, int) or bottleneck < 1:
            raise CassiModalTorchError("bottleneck must be a positive integer")
        if not math.isfinite(max_scale) or max_scale <= 0.0:
            raise CassiModalTorchError("max_scale must be positive and finite")

        self.dimension = dimension
        self.bottleneck = bottleneck
        self.max_scale = float(max_scale)
        self.norm = nn.LayerNorm(dimension)
        self.down = nn.Linear(dimension, bottleneck)
        self.up = nn.Linear(bottleneck, dimension)
        self.gate = nn.Linear(dimension, 1)
        nn.init.zeros_(self.up.weight)
        nn.init.zeros_(self.up.bias)
        nn.init.zeros_(self.gate.weight)
        nn.init.zeros_(self.gate.bias)

    def forward(self, hidden: Tensor, field_correction: Tensor) -> CassiFieldAdapterOutput:
        if hidden.ndim != 2 or field_correction.shape != hidden.shape:
            raise CassiModalTorchError("hidden and field_correction must share shape [D, T]")
        if hidden.shape[0] != self.dimension:
            raise CassiModalTorchError("hidden dimension does not match the adapter")
        if hidden.dtype != field_correction.dtype or hidden.device != field_correction.device:
            raise CassiModalTorchError("hidden and field_correction must share dtype and device")

        features = self.norm(field_correction.transpose(0, 1))
        residual = self.up(F.gelu(self.down(features)))
        gate = torch.sigmoid(self.gate(features)) * self.max_scale
        residual = (gate * residual).transpose(0, 1)
        return CassiFieldAdapterOutput(hidden=hidden + residual, residual=residual, gate=gate.transpose(0, 1))
