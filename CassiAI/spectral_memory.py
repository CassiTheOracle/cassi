#!/usr/bin/env python3
"""SpectralMemory — Galerkin projection memory replacing PatternMemory.

Projects the field ψ onto chakra modes via learnable key/value projections.
Stores persistent coefficients updated with φ-weighted EMA.
Read injects stored patterns back into the field as a boost term.
"""

import torch
import torch.nn as nn

from _chakra_utils import PHI, PHI_INV, bell_chakra_widths, chakra_offsets


class SpectralMemory(nn.Module):
    """Persistent memory via spectral Galerkin projection onto chakra modes.

    Two modes:
    - ``num_slots=1``: Original single-slot φ-weighted EMA (backward compat).
    - ``num_slots=8`` (default): Hierarchical Spectral Memory (HSM) with
      content-addressable slot attention.  Write selects the best-matching
      slot; read attends over all slots with a learned query.  Optional Qi
      gate suppresses writes during settled (low-entropy) states.

    Args:
        d: Field dimension per position.
        C: Number of chakras (always 13).
        N: Number of spatial positions.
        num_modes: Number of modes stored per chakra.
        num_slots: Number of content-addressable slots (1 = original behavior).
        slot_temp: Softmax temperature for slot attention (lower = harder
                   selection of the most relevant slot).
        max_batch_size: Maximum batch size for persistent buffers.
    """

    def __init__(self, d: int, C: int = 13, N: int = 128,
                 num_modes: int = 32, num_slots: int = 8,
                 slot_temp: float = 0.1, max_batch_size: int = 64):
        super().__init__()
        self.d = d
        self.C = C
        self.N = N
        self.num_modes = num_modes
        self.num_slots = num_slots
        self.slot_temp = slot_temp
        self.max_batch_size = max_batch_size

        # ── φ-scaled chakra widths ──
        widths = bell_chakra_widths(d, C)
        offsets = chakra_offsets(widths)
        self.register_buffer("chakra_offsets", offsets.clone())
        self._chakra_start_end = [
            (int(offsets[c].item()), int(offsets[c].item()) + widths[c])
            for c in range(C)
        ]

        # ── Learnable projection matrices ──
        self.W_key = nn.Parameter(torch.randn(C, d, num_modes) * 0.02)
        self.W_val = nn.Parameter(torch.randn(C, d, num_modes) * 0.02)

        # ── Stored coefficients (persistent, no gradient) ──
        # Shape: [C, num_slots, num_modes] — each slot stores a distinct
        # set of chakra-mode coefficients.
        self.register_buffer("coeffs", torch.zeros(C, num_slots, num_modes))
        # Age counter per slot: used for LRU eviction when all slots are full.
        self.register_buffer("ages", torch.zeros(C, num_slots))

    def reset_state(self):
        """Clear all stored memory."""
        self.coeffs.zero_()
        self.ages.zero_()

    def load_state_dict(self, state_dict, strict=True):
        """Load with backward compat for old single-slot format.

        Old checkpoints stored ``coeffs`` as ``[C, num_modes]`` and ``ages``
        as ``[C]``.  When loading into a multi-slot module, the single-slot
        coefficient is broadcast across all slots (shared initialization).
        """
        if 'coeffs' in state_dict:
            if state_dict['coeffs'].dim() == 2:
                # Old format [C, M] → broadcast to all slots [C, num_slots, M]
                c = state_dict['coeffs'].unsqueeze(1)
                state_dict['coeffs'] = c.expand(-1, self.num_slots, -1).contiguous()
            elif (state_dict['coeffs'].shape[1] == 1
                  and self.num_slots > 1):
                # Single-slot saved from multi-slot module → broadcast
                state_dict['coeffs'] = state_dict['coeffs'].expand(
                    -1, self.num_slots, -1).contiguous()
        if 'ages' in state_dict:
            if state_dict['ages'].dim() == 1:
                a = state_dict['ages'].unsqueeze(-1)
                state_dict['ages'] = a.expand(-1, self.num_slots).contiguous()
            elif (state_dict['ages'].shape[1] == 1
                  and self.num_slots > 1):
                state_dict['ages'] = state_dict['ages'].expand(
                    -1, self.num_slots).contiguous()
        return super().load_state_dict(state_dict, strict=strict)

    @torch.no_grad()
    def write(self, psi: torch.Tensor, gate: torch.Tensor = None):
        """Project field onto chakra modes and store.

        In single-slot mode (num_slots=1): φ-weighted EMA (original behavior).
        In multi-slot mode: find the best-matching slot per chakra via cosine
        similarity and update it.  All slots age; the oldest slot is evicted
        when no slot matches above threshold.

        Args:
            psi: Complex field [B, N, d].
            gate: Optional scalar or [B] tensor in [0, 1].  When provided,
                  the write strength is multiplied by ``gate``.  Intended for
                  Qi-gating: low gate during settled states suppresses writes.
        """
        energy = psi.abs() ** 2  # [B, N, d]
        B = psi.shape[0]

        # Squeeze batch: use mean over B, N per position for simplicity
        # (same as original — mean over batch and spatial dims)

        for c in range(self.C):
            start, end = self._chakra_start_end[c]
            psi_c = energy[:, :, start:end].mean(dim=(0, 1))  # [width_c]
            width_c = end - start
            W_k = self.W_key[c, start:end, :]  # [width_c, num_modes]
            new_coeffs = psi_c @ W_k  # [num_modes]

            if self.num_slots == 1:
                # ── Single-slot: φ-weighted EMA (original behavior) ──
                update = (1.0 - PHI_INV)
                if gate is not None:
                    update = update * gate.item() if gate.dim() == 0 else update * gate[0].item()
                self.coeffs[c, 0] = (
                    PHI_INV * self.coeffs[c, 0] + update * new_coeffs
                )
                self.ages[c, 0] += 1.0

            else:
                # ── Multi-slot: content-addressable slot write ──
                # Cosine similarity between new pattern and each slot
                slots = self.coeffs[c]  # [num_slots, num_modes]
                sim = torch.cosine_similarity(
                    new_coeffs.unsqueeze(0), slots, dim=-1)  # [num_slots]
                best = sim.argmax().item()

                # Qi gate: scale the update (default 1.0 = full update)
                update_strength = (1.0 - PHI_INV)
                if gate is not None:
                    g = gate.item() if gate.dim() == 0 else gate[0].item()
                    update_strength = update_strength * g

                if sim[best] > 0.5:
                    # Update best-matching slot
                    slot_idx = best
                else:
                    # No good match → evict oldest slot
                    slot_idx = self.ages[c].argmax().item()

                self.coeffs[c, slot_idx] = (
                    PHI_INV * self.coeffs[c, slot_idx]
                    + update_strength * new_coeffs
                )
                self.ages[c, slot_idx] = 0.0
                self.ages[c] += 1.0  # age all slots

    def read(self, psi: torch.Tensor) -> torch.Tensor:
        """Retrieve stored patterns and inject into field.

        In single-slot mode: direct mode injection (original behavior).
        In multi-slot mode: content-addressable slot attention.  The current
        field's chakra-mode projection serves as the query; attention over
        stored slots produces a weighted context; the context is expanded
        back through ``W_val``.

        Args:
            psi: Complex field [B, N, d].  Content is used as the attention
                 query in multi-slot mode (meaningful psi required).

        Returns:
            boost: Complex tensor [B, N, d] — memory injection.
        """
        B = psi.shape[0]
        device = psi.device
        boost = torch.zeros(B, self.N, self.d, dtype=torch.cfloat, device=device)

        for c in range(self.C):
            start, end = self._chakra_start_end[c]
            width_c = end - start
            W_v = self.W_val[c, start:end, :]  # [width_c, num_modes]

            if self.num_slots == 1:
                # ── Single-slot: direct injection (original behavior) ──
                mode_injection = (
                    self.coeffs[c, 0].clone().detach() @ W_v.T
                )  # [width_c]
                boost[:, :, start:end] = mode_injection.unsqueeze(0).unsqueeze(0)

            else:
                # ── Multi-slot: slot attention read ──
                # Query = current field's chakra-mode projection
                energy = psi.abs() ** 2  # [B, N, d]
                psi_c = energy[:, :, start:end].mean(dim=(0, 1))  # [width_c]
                W_k = self.W_key[c, start:end, :]  # [width_c, num_modes]
                query = psi_c @ W_k  # [num_modes]

                # Attention over stored slots
                slots = self.coeffs[c].clone().detach()  # [num_slots, num_modes]
                scores = torch.cosine_similarity(
                    query.unsqueeze(0), slots, dim=-1)  # [num_slots]
                attn = torch.softmax(scores / self.slot_temp, dim=-1)  # [num_slots]

                # Weighted context = attend over slots
                context = (attn @ slots)  # [num_modes]

                # Expand context back to field
                mode_injection = context @ W_v.T  # [width_c]
                boost[:, :, start:end] = mode_injection.unsqueeze(0).unsqueeze(0)

        return boost
