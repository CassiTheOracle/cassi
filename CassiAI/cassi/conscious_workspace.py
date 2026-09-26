"""ConsciousWorkspace — Sparse competitive broadcast layer.

A small bottleneck workspace above the resonant field. The field is compressed
into a W-dimensional workspace, k-WTA competition selects the top-k active slots
(gated by qi contrast), and the sparse winners broadcast back to field dimension.

Inspired by Global Workspace Theory (Baars, Dehaene) and the HoneybeeBrain's
mushroom-body sparse attention. Complements ResonantAttention with a hierarchical
bottleneck: field → compressed workspace → broadcast.
"""

import torch
import torch.nn as nn

from cassi.cord import PHI_INV


class ConsciousWorkspace(nn.Module):
    """Sparse competitive workspace above the resonant field.

    Args:
        d: Field dimension.
        W: Workspace dimension (default: d // 4, min 16).
        sparsity: Fraction of workspace slots active (default 0.25).
    """

    def __init__(self, d: int, W: int = None, sparsity: float = 0.25):
        super().__init__()
        self.d = d
        self.W = W or max(d // 4, 16)
        self.sparsity = sparsity
        self.k_active = max(1, int(self.W * sparsity))

        self.compress = nn.Linear(d, self.W, bias=False)
        self.broadcast = nn.Linear(self.W, d, bias=False)

        nn.init.normal_(self.compress.weight, std=0.02)
        nn.init.normal_(self.broadcast.weight, std=0.02)

    def forward(self, psi_real: torch.Tensor, psi_imag: torch.Tensor,
                qi_contrast: torch.Tensor):
        """Compress field → compete → broadcast back.

        Args:
            psi_real, psi_imag: [B, N, d] field state.
            qi_contrast: [B, N] per-position qi / qi_mean.

        Returns:
            boost_re, boost_im: [B, N, d] field deltas.
        """
        B, N, d = psi_real.shape

        # Complex magnitude as workspace input
        mag = (psi_real.pow(2) + psi_imag.pow(2)).sqrt()  # [B, N, d]
        w = self.compress(mag)  # [B, N, W]

        # k-WTA competition per-position: only top-k_active dims fire per position
        _, topk_idx = w.topk(self.k_active, dim=-1)  # [B, N, k_active]
        mask = torch.zeros_like(w)
        mask.scatter_(-1, topk_idx, 1.0)
        w_sparse = w * mask
        # Gate winners by qi contrast: high-qi positions compete harder
        qi_gate = qi_contrast.unsqueeze(-1).clamp(min=0.5, max=2.0)  # [B, N, 1]
        w_sparse = w_sparse * qi_gate

        # Broadcast back to field dimension
        boost = self.broadcast(w_sparse)  # [B, N, d]

        # Small scale — workspace is a nudge, not a rewrite
        return boost, boost  # symmetric for real and imag
