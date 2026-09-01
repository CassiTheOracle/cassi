"""Read-only four-coordinate phase portrait for cyclic chromatic fields."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import torch
from torch import Tensor

from cassi_cyclic_chromatic_field import CyclicChromaticFieldController
from cassi_qi_field import QiFieldError, QiFieldState

CHROMATIC_PHASE_PORTRAIT_PROFILE_ID = "cassi.qi-chromatic-phase-portrait.v1"
CHROMATIC_PHASE_PORTRAIT_PANEL_NAMES = ("C", "D", "VC", "VD")
_CHANNEL_COUNT = 7


@dataclass(frozen=True)
class ChromaticPhasePortrait:
    """A bounded display plus absolute phase-space diagnostics."""

    rgb: Tensor
    panel_amplitude: Tensor
    panel_phase: Tensor
    panel_peak_amplitude: Tensor
    panel_side: int
    side: int


def _positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise QiFieldError(f"{name} must be a positive integer")
    return value


def chromatic_phase_portrait(
    controller: CyclicChromaticFieldController,
    state: QiFieldState,
    *,
    panel_side: int = 16,
) -> ChromaticPhasePortrait:
    """Project ``C,D,VC,VD`` into a deterministic hue/brightness mosaic."""

    controller._validate_state(state)
    panel_side = _positive_int("panel_side", panel_side)
    width = controller.config.wave_mode_count
    if panel_side > math.isqrt(width):
        raise QiFieldError("panel_side squared must not exceed active mode count")

    common, differential, common_velocity, differential_velocity = (
        controller._active_coordinates(state)
    )
    common, differential, common_velocity, differential_velocity = (
        value.to(dtype=torch.complex128)
        for value in (common, differential, common_velocity, differential_velocity)
    )
    constants = controller._constants(state)
    white = constants["white"].to(dtype=torch.complex128)[:, None, None]
    chromatic = (
        constants["channel_phase"].conj().to(dtype=torch.complex128)[:, None, None]
        / math.sqrt(_CHANNEL_COUNT)
    )
    spectra = torch.stack(
        (
            (white * common).sum(dim=0),
            (chromatic * differential).sum(dim=0),
            (white * common_velocity).sum(dim=0),
            (chromatic * differential_velocity).sum(dim=0),
        ),
        dim=0,
    )
    count = panel_side * panel_side
    indices = torch.div(
        torch.arange(count, device=state.field.device) * width,
        count,
        rounding_mode="floor",
    )
    selected = (
        spectra.index_select(1, indices)
        .permute(2, 0, 1)
        .reshape(state.batch_size, 4, panel_side, panel_side)
    )
    wave = torch.fft.ifft2(selected, norm="ortho")
    amplitude = wave.abs()
    phase = torch.angle(wave)
    peak = amplitude.amax(dim=(-2, -1))
    scale = torch.clamp_min(peak, torch.finfo(amplitude.dtype).tiny)
    brightness = torch.sqrt(amplitude / scale[:, :, None, None])
    hue = phase / (2.0 * math.pi)
    offsets = amplitude.new_tensor((0.0, -1.0 / 3.0, 1.0 / 3.0))
    hue_rgb = 0.5 + 0.5 * torch.cos(
        2.0
        * math.pi
        * (hue[:, :, None, :, :] + offsets[None, None, :, None, None])
    )
    panels = (brightness[:, :, None, :, :] * hue_rgb).clamp(0.0, 1.0)
    separator = amplitude.new_zeros(state.batch_size, 3, panel_side, 1)
    top = torch.cat((panels[:, 0], separator, panels[:, 1]), dim=3)
    bottom = torch.cat((panels[:, 2], separator, panels[:, 3]), dim=3)
    horizontal = amplitude.new_zeros(
        state.batch_size, 3, 1, 2 * panel_side + 1
    )
    rgb = torch.cat((top, horizontal, bottom), dim=2)
    return ChromaticPhasePortrait(
        rgb=rgb,
        panel_amplitude=amplitude,
        panel_phase=phase,
        panel_peak_amplitude=peak,
        panel_side=panel_side,
        side=2 * panel_side + 1,
    )


__all__ = [
    "CHROMATIC_PHASE_PORTRAIT_PANEL_NAMES",
    "CHROMATIC_PHASE_PORTRAIT_PROFILE_ID",
    "ChromaticPhasePortrait",
    "chromatic_phase_portrait",
]
