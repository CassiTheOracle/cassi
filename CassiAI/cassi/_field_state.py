#!/usr/bin/env python3
"""
FieldState -- typed value container for a resonant field's persistent buffers.

Captures psi (real/imag), Q_field, IIR state (h1/h2), and auxiliary scalars.
Provides ``resize_batch`` (clone, not expand) and ``to_buffers`` / ``from_buffers``
for module serialization.

Every module that owns persistent field state delegates buffer management
to FieldState.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn


# ── Known scalar buffer names (stored on the module, captured/restored) ──
_SCALAR_BUFFERS = frozenset({"Q_ema", "Q_trend", "pattern_step", "Q_bar_pos"})


def _state_buffers(module: nn.Module) -> Dict[str, torch.Tensor]:
    """Return *module*'s buffers as a flat dict (excluding non-persistent)."""
    return {k: v for k, v in module.named_buffers()
            if k in _SCALAR_BUFFERS or not k.startswith("_")}


@dataclass
class FieldState:
    """Immutable-ish snapshot of field + IIR + scalar state.

    ``resize_batch`` returns a *new* FieldState with psi/Q expanded to
    ``[B, N, d]`` (cloned, so each batch row is independent).  The
    original ``[1, N, d]`` storage is never mutated.
    """

    psi_real: torch.Tensor          # [1, N, d]
    psi_imag: torch.Tensor          # [1, N, d]
    Q_field: torch.Tensor           # [1, N, d]
    h1: torch.Tensor                # [max_bs, N, d]
    h2: torch.Tensor                # [max_bs, N, d]
    scalars: Dict[str, torch.Tensor] = field(default_factory=dict)

    # ── Serialisation ──

    @classmethod
    def from_buffers(
        cls,
        module: nn.Module,
        h1_name: str = "h1",
        h2_name: str = "h2",
    ) -> "FieldState":
        """Read field state from *module*'s registered buffers.

        Args:
            module: an nn.Module with buffers
                ``psi_real``, ``psi_imag``, ``Q_field``,
                ``{h1_name}``, ``{h2_name}``,
                plus scalar buffers in ``_SCALAR_BUFFERS``.
            h1_name, h2_name: buffer names for IIR state
                (``h1`` / ``h2`` on QiField, ``iir_h1`` / ``iir_h2`` on MindBrainField).
        """
        scalars = {}
        for name in _SCALAR_BUFFERS:
            if hasattr(module, name):
                scalars[name] = getattr(module, name)

        return cls(
            psi_real=module.psi_real,
            psi_imag=module.psi_imag,
            Q_field=module.Q_field,
            h1=getattr(module, h1_name),
            h2=getattr(module, h2_name),
            scalars=scalars,
        )

    def to_buffers(self, module: nn.Module) -> None:
        """Assign state back to *module* via ``register_buffer``.

        Uses *assignment*, not in-place ops (per convention (assignment, not in-place)).
        Only writes the ``[1, N, d]`` root tensors (psi/Q and scalars).
        IIR state (h1/h2) is **not** overwritten -- it lives at
        ``[max_bs, N, d]`` and is managed by the trainer.
        """
        for name in ("psi_real", "psi_imag", "Q_field"):
            buf = getattr(self, name)
            if buf is not None:
                # Keep the root [1, ...] slice
                root = buf[:1] if buf.shape[0] > 1 else buf
                module.register_buffer(name, root)
        for k, v in self.scalars.items():
            if v is not None:
                module.register_buffer(k, v)

    # ── Batch resize ──

    def resize_batch(self, B: int) -> "FieldState":
        """Return a copy with psi/Q expanded to ``[B, N, d]`` (cloned).

        The returned copy shares IIR state (h1/h2) and scalars by
        reference -- only psi/Q are expanded.
        """
        if self.psi_real.shape[0] == B:
            return self  # already correct size
        return FieldState(
            psi_real=self.psi_real[:1].expand(B, -1, -1).clone(),
            psi_imag=self.psi_imag[:1].expand(B, -1, -1).clone(),
            Q_field=self.Q_field[:1].expand(B, -1, -1).clone(),
            h1=self.h1,
            h2=self.h2,
            scalars=self.scalars,
        )

    # ── Utility ──

    def zero_(self) -> None:
        """Zero every tensor in-place (use with care -- mutates module buffers)."""
        for f in (self.psi_real, self.psi_imag, self.Q_field,
                  self.h1, self.h2):
            f.zero_()
        for v in self.scalars.values():
            v.zero_()

    def detach_(self) -> None:
        """Detach all tensors from autograd."""
        for f in (self.psi_real, self.psi_imag, self.Q_field,
                  self.h1, self.h2):
            f.detach_()
        for v in self.scalars.values():
            v.detach_()

    @staticmethod
    def from_buffers_legacy(module: nn.Module) -> "FieldState":
        """Build a FieldState by reading a fixed set of buffers from *module*.

        Convenience for one-off snapshot/restore where you don't want to
        import the full QiField class.
        """
        return FieldState.from_buffers(module)
