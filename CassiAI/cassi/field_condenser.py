"""FieldCondensers — phase-transition from accumulated field state to weights.

Two variants:
  FieldCondenser (original): pools IIR traces, slices into 3 static chakra bands,
    projects each band linearly to its target delta.
  ChakraCondenser (new): passes pooled IIR state through chakras SEQUENTIALLY
    (root(0) → crown(C-1) compression, then crown → root expansion with skip
    connections), projecting targets from bandwidth-matched levels.

Both share the same calling convention: forward(h1, h2, h1_im, h2_im) → Dict.
"""

from typing import Dict, List

import torch
import torch.nn as nn
import torch.nn.functional as F


# ════════════════════════════════════════════════
#  Original: static band-based condenser
# ════════════════════════════════════════════════

class FieldCondenser(nn.Module):
    """Condenses accumulated IIR state into weight deltas for multiple targets.

    Uses three static chakra bands:
      Band 1 (chakras 0-2, widest)   → readout weights
      Band 2 (chakras 3-6)           → pattern-memory neuron seeds
      Band 4 (chakras 10-12, finest) → scalar homeostasis parameters
    """

    def __init__(self, d: int, C: int, V: int, N: int,
                 widths: List[int], offsets: torch.Tensor):
        super().__init__()

        self.d = d
        self.C = C
        self.V = V
        self.N = N

        self.register_buffer('offsets', offsets, persistent=False)

        w1 = int(sum(widths[0:3]))    # chakras 0-2: structural
        w2 = int(sum(widths[3:7]))    # chakras 3-6: pattern seeds
        w4 = int(sum(widths[10:13]))  # chakras 10-12: scalar homeo

        # Band 1: readout weight deltas
        self.C_ry_w = nn.Parameter(torch.randn(d, w1) * 0.005)
        self.C_rz_w = nn.Parameter(torch.randn(d, w1) * 0.005)
        self.C_rby_w = nn.Parameter(torch.randn(d, w1) * 0.005)
        self.C_rbz_w = nn.Parameter(torch.randn(d, w1) * 0.005)

        # Band 2: pattern-memory neuron seeds
        self.C_pm_key = nn.Parameter(torch.randn(d, w2) * 0.005)
        self.C_pm_val_re = nn.Parameter(torch.randn(d, w2) * 0.005)
        self.C_pm_val_im = nn.Parameter(torch.randn(d, w2) * 0.005)

        # Band 4: scalar homeostasis (7 targets)
        self.C_homeo = nn.Parameter(torch.randn(7, w4) * 0.005)

    @torch.no_grad()
    def forward(self, h1: torch.Tensor, h2: torch.Tensor,
                h1_im: torch.Tensor, h2_im: torch.Tensor
                ) -> Dict[str, torch.Tensor]:
        """Condense IIR state into per-target weight deltas.

        Returns dict with keys: readout_y.weight, readout_z.weight,
        readout_bwd_y.weight, readout_bwd_z.weight, pattern_key,
        pattern_val_re, pattern_val_im, homeo, h1_norm.
        """
        trace = (h1 + h2 + h1_im + h2_im).mean(dim=(0, 1))  # [d]
        off = self.offsets

        b1 = trace[off[0].item():off[3].item()]
        delta_ry_w = F.linear(b1, self.C_ry_w)
        delta_rz_w = F.linear(b1, self.C_rz_w)
        delta_rby_w = F.linear(b1, self.C_rby_w)
        delta_rbz_w = F.linear(b1, self.C_rbz_w)

        b2 = trace[off[3].item():off[7].item()]
        delta_pm_key = F.linear(b2, self.C_pm_key)
        delta_pm_val_re = F.linear(b2, self.C_pm_val_re)
        delta_pm_val_im = F.linear(b2, self.C_pm_val_im)

        b4 = trace[off[10].item():off[13].item()]
        delta_homeo = F.linear(b4, self.C_homeo)

        return {
            'readout_y.weight':     delta_ry_w,
            'readout_z.weight':     delta_rz_w,
            'readout_bwd_y.weight': delta_rby_w,
            'readout_bwd_z.weight': delta_rbz_w,
            'pattern_key':          delta_pm_key,
            'pattern_val_re':       delta_pm_val_re,
            'pattern_val_im':       delta_pm_val_im,
            'homeo':                delta_homeo,
            'h1_norm':              h1.norm().detach(),
        }


# ════════════════════════════════════════════════
#  ChakraCondenser: sequential chakra processing
# ════════════════════════════════════════════════

class ChakraCondenser(nn.Module):
    """Condenses IIR state by passing it sequentially through chakras.

    Processes chakras in index order (root=0 → crown=12):
      Root chakras (narrow, Fibonacci) — concrete patterns expand and build
      Heart chakra (widest) — full embodied awareness
      Brain chakras (compressed remainder) — abstract compression

    Each step applies a FiLM gate (bandwidth-dependent selectivity) and SiLU,
    then mixes the flowing signal with the chakra's native state. Skip
    connections feed the expansion pass which reconstructs multi-scale structure.

    Target projections from bandwidth-matched chakra outputs:
      readout weights  ← widest chakra output (most bandwidth)
      pattern memory   ← median-width chakra output
      homeostasis      ← narrowest chakra output (only 7 scalars needed)
    """

    def __init__(self, d: int, C: int, V: int, N: int,
                 widths: List[int], offsets: torch.Tensor):
        super().__init__()

        self.d = d
        self.C = C
        self.V = V
        self.N = N
        self.widths = widths
        self.register_buffer('offsets', offsets, persistent=False)

        # ── Target projection indices: matched to target bandwidth ──
        # widest  → readout weights (needs full d for prediction)
        # median  → pattern memory (balanced)
        # narrowest → homeostasis scalars (needs only 7 floats)
        w_sorted = sorted([(w, i) for i, w in enumerate(widths)])
        self._idx_narrow = w_sorted[0][1]          # e.g. root(0)=3d
        self._idx_wide = w_sorted[-1][1]           # e.g. heart(9)=165d
        self._idx_mid = w_sorted[C // 2][1]        # e.g. solar(6)=39d

        w_narrow = widths[self._idx_narrow]
        w_wide = widths[self._idx_wide]
        w_mid = widths[self._idx_mid]

        # ── Compression pass: sequential chakra→chakra projections ──
        self.compress_W = nn.ParameterList()
        self.compress_G = nn.ParameterList()
        for c in range(C - 1):
            w_curr = widths[c]
            w_next = widths[c + 1]
            self.compress_W.append(nn.Parameter(torch.randn(w_next, w_curr) * 0.005))
            self.compress_G.append(nn.Parameter(torch.randn(w_next, w_curr) * 0.005))

        # ── Target projections ──
        self.proj_homeo = nn.Parameter(torch.randn(7, w_narrow) * 0.005)

        self.proj_pm_key = nn.Parameter(torch.randn(d, w_mid) * 0.005)
        self.proj_pm_val_re = nn.Parameter(torch.randn(d, w_mid) * 0.005)
        self.proj_pm_val_im = nn.Parameter(torch.randn(d, w_mid) * 0.005)

        self.proj_ry_w = nn.Parameter(torch.randn(d, w_wide) * 0.005)
        self.proj_rz_w = nn.Parameter(torch.randn(d, w_wide) * 0.005)
        self.proj_rby_w = nn.Parameter(torch.randn(d, w_wide) * 0.005)
        self.proj_rbz_w = nn.Parameter(torch.randn(d, w_wide) * 0.005)

        # ── Expansion pass: crown(C-1) → root(0) ──
        self.expand_W = nn.ParameterList()
        for c in range(C - 1):
            w_curr = widths[C - 1 - c]
            w_next = widths[C - 2 - c]
            self.expand_W.append(nn.Parameter(torch.randn(w_next, w_curr) * 0.005))

    @torch.no_grad()
    def forward(self, h1: torch.Tensor, h2: torch.Tensor,
                h1_im: torch.Tensor, h2_im: torch.Tensor
                ) -> Dict[str, torch.Tensor]:
        """Condense IIR state via sequential chakra processing.

        Returns same dict format as FieldCondenser (drop-in compatible).
        """
        trace = (h1 + h2 + h1_im + h2_im).mean(dim=(0, 1))  # [d]
        off = self.offsets

        # Extract per-chakra native states
        native = [trace[off[c].item():off[c + 1].item()] for c in range(self.C)]

        # ── Sequential pass: root(0) → crown(C-1) ──
        x = native[0].clone()
        skips = [x.clone()]

        for c in range(self.C - 1):
            gate = torch.sigmoid(F.linear(x, self.compress_G[c]))
            transformed = F.silu(F.linear(x, self.compress_W[c]))
            x = gate * transformed + (1 - gate) * native[c + 1]
            skips.append(x.clone())


        # ── Expansion pass: crown(C-1) → root(0) ──
        # expand_outputs maps chakra_index → expansion state at that level
        x_up = x.clone()
        expand_outputs = {self.C - 1: x_up.clone()}

        for c in range(self.C - 1):
            skip = skips[self.C - 2 - c]
            x_up = F.silu(F.linear(x_up, self.expand_W[c]) + skip)
            expand_outputs[self.C - 2 - c] = x_up.clone()

        # Target projections from bandwidth-matched expansion states
        # Homeostasis from narrowest chakra (after expansion for full context)
        delta_homeo = F.linear(expand_outputs[self._idx_narrow], self.proj_homeo)
        delta_ry_w = F.linear(expand_outputs[self._idx_wide], self.proj_ry_w)
        delta_rz_w = F.linear(expand_outputs[self._idx_wide], self.proj_rz_w)
        delta_rby_w = F.linear(expand_outputs[self._idx_wide], self.proj_rby_w)
        delta_rbz_w = F.linear(expand_outputs[self._idx_wide], self.proj_rbz_w)

        delta_pm_key = F.linear(expand_outputs[self._idx_mid], self.proj_pm_key)
        delta_pm_val_re = F.linear(expand_outputs[self._idx_mid], self.proj_pm_val_re)
        delta_pm_val_im = F.linear(expand_outputs[self._idx_mid], self.proj_pm_val_im)

        return {
            'readout_y.weight':     delta_ry_w,
            'readout_z.weight':     delta_rz_w,
            'readout_bwd_y.weight': delta_rby_w,
            'readout_bwd_z.weight': delta_rbz_w,
            'pattern_key':          delta_pm_key,
            'pattern_val_re':       delta_pm_val_re,
            'pattern_val_im':       delta_pm_val_im,
            'homeo':                delta_homeo,
            'h1_norm':              h1.norm().detach(),
        }
