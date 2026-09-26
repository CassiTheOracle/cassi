"""CorpusCallosum — Learned inter-hemisphere communication channel.

Two parallel field streams (Yang: fast/forward, Yin: slow/backward) exchange
compressed representations through a bottleneck, analogous to the human corpus
callosum. Each hemisphere sends its conscious state to the other via a learned
compression→expansion pathway.

Adapted from dual_cassi.py for the MuonCord architecture.
"""

import torch
import torch.nn as nn


class CorpusCallosum(nn.Module):
    """Bottleneck communication channel between Yang and Yin streams.

    Args:
        d: Field dimension.
        bottleneck: Compressed channel dimension (default: d // 4, min 8).
    """

    def __init__(self, d: int, bottleneck: int = None):
        super().__init__()
        b = bottleneck or max(d // 4, 8)
        self.d = d
        self.bottleneck = b

        # Yang → shared representation → Yin receives
        self.yang_compress = nn.Linear(d, b, bias=False)
        self.yin_expand = nn.Linear(b, d, bias=False)

        # Yin → shared representation → Yang receives
        self.yin_compress = nn.Linear(d, b, bias=False)
        self.yang_expand = nn.Linear(b, d, bias=False)

        nn.init.normal_(self.yang_compress.weight, std=0.02)
        nn.init.normal_(self.yin_expand.weight, std=0.02)
        nn.init.normal_(self.yin_compress.weight, std=0.02)
        nn.init.normal_(self.yang_expand.weight, std=0.02)

    def exchange(self, yang_psi: torch.Tensor, yin_psi: torch.Tensor):
        """Exchange compressed conscious states between hemispheres.

        Args:
            yang_psi: [B, N, d] Yang stream field state.
            yin_psi:  [B, N, d] Yin stream field state.

        Returns:
            yang_input: [B, 1, d] what Yang receives from Yin.
            yin_input:  [B, 1, d] what Yin receives from Yang.
        """
        # Pool over positions to get hemisphere summaries
        yang_summary = yang_psi.mean(dim=1)  # [B, d]
        yin_summary = yin_psi.mean(dim=1)    # [B, d]

        # Compress each hemisphere's state
        yang_shared = self.yang_compress(yang_summary)  # [B, b]
        yin_shared = self.yin_compress(yin_summary)     # [B, b]

        # Cross: Yang receives Yin's perspective, Yin receives Yang's
        yang_input = self.yin_expand(yin_shared).unsqueeze(1)    # [B, 1, d]
        yin_input = self.yang_expand(yang_shared).unsqueeze(1)   # [B, 1, d]

        return yang_input, yin_input


class Arbitration(nn.Module):
    """Per-output-dimension trust weighting between hemispheres.

    Takes merged output from both hemispheres and learns, per vocabulary
    dimension, which hemisphere to trust more. Features include both
    hemisphere logits, their absolute difference, and dot product.
    """

    def __init__(self, d: int, V: int = 256):
        super().__init__()
        # Pool field to get hemisphere signatures per batch
        self.yang_proj = nn.Linear(d, V, bias=False)
        self.yin_proj = nn.Linear(d, V, bias=False)

        # Gate: 4V features → V trust weights
        self.gate = nn.Sequential(
            nn.Linear(4 * V, V // 2),
            nn.SiLU(),
            nn.Linear(V // 2, V),
            nn.Sigmoid()  # [0,1] — 1 = full Yang trust
        )

        nn.init.normal_(self.yang_proj.weight, std=0.02)
        nn.init.normal_(self.yin_proj.weight, std=0.02)

    def forward(self, yang_psi: torch.Tensor, yin_psi: torch.Tensor) -> torch.Tensor:
        """Compute per-vocab-dim Yang trust weight.

        Args:
            yang_psi: [B, N, d] Yang field after evolution.
            yin_psi:  [B, N, d] Yin field after evolution.

        Returns:
            yang_weight: [B, V] trust weight per output dimension.
        """
        # Pool over positions to get hemisphere signatures
        yg = self.yang_proj(yang_psi.mean(dim=1))  # [B, V]
        yi = self.yin_proj(yin_psi.mean(dim=1))    # [B, V]

        # Four signals for arbitration
        features = torch.cat([
            yg,               # Yang's perspective
            yi,               # Yin's perspective
            (yg - yi).abs(),  # disagreement magnitude
            yg * yi,          # agreement direction
        ], dim=-1)  # [B, 4V]

        return self.gate(features)  # [B, V] — 1=full Yang, 0=full Yin
