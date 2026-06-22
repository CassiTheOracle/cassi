"""BerryPhaseMemory — Topological associative memory keyed by IIR trajectory phases.

Computes 26-dimensional Berry phase fingerprints (13 chakras × 2 hemispheres)
from the IIR state transition (h1 → h2) using the shoelace formula. Stores
compressed field representations keyed by these phase fingerprints.

Unlike content-based memory (QiPatternMemory), phase-based retrieval captures
the *shape* of the field trajectory — robust to amplitude noise and complementary
to content memory.

Adapted from berry_brain.py compute_berry_phases for the MuonCord architecture.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class BerryPhaseMemory(nn.Module):
    """Topological memory bank keyed by Berry phase fingerprints.

    Args:
        n_slots: Number of memory slots (default 512).
        key_dim: Berry phase fingerprint dimension (26: 13 chakras × 2 hemi).
        C: Number of chakras.
        d_shared: Shared projection dimension for compressed values.
        chakra_widths: List of per-chakra field widths.
        chakra_offsets: Buffer of cumulative offsets into the field dimension.
    """

    def __init__(self, n_slots: int = 512, key_dim: int = 26,
                 C: int = 13, d_shared: int = 16,
                 chakra_widths: list = None, chakra_offsets: torch.Tensor = None):
        super().__init__()
        self.n_slots = n_slots
        self.key_dim = key_dim
        self.C = C
        self.d_shared = d_shared
        self.chakra_widths = chakra_widths or [1] * C
        self.chakra_offsets = chakra_offsets

        # Keys: normalized phase fingerprints (stored, not learned)
        self.register_buffer('keys', F.normalize(torch.randn(n_slots, key_dim), dim=-1))
        # Values: compressed per-chakra field representations
        self.register_buffer('values', torch.zeros(n_slots, C, d_shared))
        # Round-robin write pointer (avoids float32 precision issues in LRU)
        self.register_buffer('write_ptr', torch.zeros(1, dtype=torch.long))

    @staticmethod
    def compute_phases(h_curr: torch.Tensor, h_next: torch.Tensor,
                       chakra_widths: list, chakra_offsets: torch.Tensor,
                       C: int) -> torch.Tensor:
        """Compute Berry phases from IIR state transition.

        For each chakra, computes the signed area of the h_curr → h_next
        transition segment via the shoelace formula.

        Args:
            h_curr: [B, N, d] or [B, C, max_W] current IIR state.
            h_next: [B, N, d] or [B, C, max_W] next IIR state.
            chakra_widths: List of per-chakra widths.
            chakra_offsets: [C] cumulative offsets.
            C: Number of chakras.

        Returns:
            [B, C] Berry phases (one scalar per chakra).
        """
        B = h_curr.shape[0]

        # If h_curr is [B, N, d], use offsets into last dim
        # If h_curr is [B, C, max_W], use widths directly
        phases = []
        for c in range(C):
            w = chakra_widths[c]

            if h_curr.ndim == 3 and h_curr.shape[1] == C:
                # [B, C, max_W] format — slice chakra dim
                x = h_curr[:, c, :w]  # [B, w]
                y = h_next[:, c, :w]  # [B, w]
            else:
                # [B, N, d] format — use offsets into last dim
                start = int(chakra_offsets[c].item())
                end = start + w
                x = h_curr[:, :, start:end].mean(dim=1)  # [B, w] — pool over N
                y = h_next[:, :, start:end].mean(dim=1)  # [B, w]

            if w >= 2:
                # Shoelace: 0.5 * Σ(x_i·y_{i+1} - x_{i+1}·y_i)
                area = 0.5 * (x[:, :-1] * y[:, 1:] - x[:, 1:] * y[:, :-1]).sum(dim=-1)
            elif w == 1:
                area = x[:, 0] * y[:, 0]
            else:
                area = torch.zeros(B, device=x.device)

            phases.append(area)

        return torch.stack(phases, dim=1)  # [B, C]

    @torch.no_grad()
    def read(self, query_phases: torch.Tensor, top_k: int = 4) -> torch.Tensor:
        """Retrieve values for similar topological configurations.

        Args:
            query_phases: [B, key_dim] normalized phase fingerprints.
            top_k: Number of nearest slots to retrieve.

        Returns:
            [B, C, d_shared] weighted sum of retrieved values.
        """
        B = query_phases.shape[0]
        # Cosine similarity between query and all keys
        sim = F.cosine_similarity(
            query_phases.unsqueeze(1),  # [B, 1, key_dim]
            self.keys.unsqueeze(0),     # [1, n_slots, key_dim]
            dim=-1)                      # [B, n_slots]

        _, idx = sim.topk(top_k, dim=-1)  # [B, top_k]
        weights = F.softmax(sim.gather(-1, idx), dim=-1)  # [B, top_k]

        # Weighted sum of retrieved values
        retrieved = self.values[idx]  # [B, top_k, C, d_shared]
        result = (retrieved * weights.unsqueeze(-1).unsqueeze(-1)).sum(dim=1)
        return result  # [B, C, d_shared]

    @torch.no_grad()
    def write(self, phases: torch.Tensor, values: torch.Tensor, batch_idx: int = 0):
        """Store a phase→value pair, round-robin eviction.

        Args:
            phases: [key_dim] normalized phase fingerprint.
            values: [C, d_shared] compressed field representation.
            batch_idx: Ignored (round-robin write pointer).
        """
        slot = int(self.write_ptr.item()) % self.n_slots
        self.write_ptr.add_(1)
        self.keys.data[slot] = phases
        self.values.data[slot] = values
