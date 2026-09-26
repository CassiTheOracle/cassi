#!/usr/bin/env python3
"""GroupingMemory — position-domain hierarchical byte-group memory.

Stores aggregate field representations for word-level byte groups,
keyed by the field's own source representation. Works alongside
SpectralMemory (frequency-domain) to form a hierarchical memory:

    bytes → words (GroupingMemory, position) → modes (SpectralMemory, frequency)

No MLPs — keys ARE the mean-pooled real part of the source field
across the word span. The MultiScaleByteEmbedder already transforms bytes
into field representations; the memory reuses those representations.

Cassi-native principles:
    - φ-weighted EMA writes (PHI_INV decay, 1-PHI_INV update strength)
    - Keys from the field's own representation (no separate encoder)
    - Content-addressable slot matching via cosine similarity
    - Read injects template boost across the entire word span
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

from _chakra_utils import PHI, PHI_INV


class GroupingMemory(nn.Module):
    """Position-domain memory for word-level field aggregates.

    Detects words via delimiter boundaries (0x20 space, 0x0A newline,
    0x09 tab, 0x00 null). The byte-signature key for a word IS the
    mean-pooled real part of the source (pre-PDE embedder output) across
    the word span. The stored value is the mean-pooled complex field ψ
    (post-PDE integration) across the same span.

    On write: cosine-similarity match against stored slot keys. If above
    threshold (0.5), φ-EMA update the slot. Otherwise, evict the
    least-recently-used slot (highest count) and write fresh.

    On read: for word spans whose source-derived key matches a stored slot
    (cosine > 0.5), inject the stored aggregate field at ALL positions
    of the span as a template boost.

    Args:
        d: Field dimension per position.
        num_slots: Number of content-addressable word slots.
        max_batch_size: Maximum batch size for persistent buffers.
    """

    def __init__(self, d: int, num_slots: int = 256,
                 max_batch_size: int = 32):
        super().__init__()
        self.d = d
        self.num_slots = num_slots

        # ── Memory bank ──
        # slots:     aggregated field per slot   [num_slots, d] complex
        # keys:      source-derived keys         [num_slots, d] real
        # counts:    age counter (LRU eviction)  [num_slots]
        self.register_buffer("slots",
                             torch.zeros(num_slots, d, dtype=torch.cfloat))
        self.register_buffer("keys",
                             torch.zeros(num_slots, d))
        self.register_buffer("counts",
                             torch.zeros(num_slots, dtype=torch.long))

        # ── Word boundary delimiters ──
        self.delimiters = {0x20, 0x0A, 0x09, 0x00}

    # ════════════════════════════════════════════════
    #  Span detection
    # ════════════════════════════════════════════════

    def _get_spans(self, x: torch.Tensor,
                   psi: torch.Tensor | None = None) -> list:
        """Detect content-word spans between delimiter bytes.

        Vectorized via diff on padded delimiter mask — no per-position .item().

        Args:
            x: [B, N] token ids.
            psi: Optional [B, N, d] complex field for aggregation.

        Returns:
            Per-batch list of (start, end, byte_seq, agg_or_None, residual) tuples.
            residual = 0-d tensor (boundary psi residual) when psi is provided,
            else 1.0 (Python float, default for read path).
        """
        B, N = x.shape
        device = x.device
        is_delim = torch.zeros_like(x, dtype=torch.bool)
        for d in self.delimiters:
            is_delim |= (x == d)

        results: list[list] = [[] for _ in range(B)]
        for b in range(B):
            delim = is_delim[b]  # [N]

            # Find word boundaries via diff on padded array.
            # Padding with True ensures edges[0] is a word start (T→F)
            # and edges[-1] is a word end (F→T) for edge content.
            padded = torch.empty(N + 2, dtype=torch.bool, device=device)
            padded[0] = True
            padded[1:N + 1] = delim
            padded[N + 1] = True
            diff = padded[1:] != padded[:-1]  # [N+1]
            edges = torch.where(diff)[0]  # [num_transitions]

            if len(edges) < 2:
                continue  # no words (all delimiters or empty)

            starts = edges[0::2]  # word start positions (padded indices)
            ends = edges[1::2]    # word end positions (exclusive, padded indices)

            # Convert to original token positions: padded index = original index
            for s, e in zip(starts.tolist(), ends.tolist()):
                byte_seq = x[b, s:e]
                agg = psi[b, s:e].mean(dim=0) if psi is not None else None
                if psi is not None:
                    res_psi = self._compute_boundary_residual(psi, b, e)
                    results[b].append((s, e, byte_seq, agg, res_psi))
                else:
                    results[b].append((s, e, byte_seq, agg, 1.0))
        return results

    def _compute_boundary_residual(self, psi: torch.Tensor, b: int, end: int) -> torch.Tensor:
        """L2 distance across the delimiter boundary, φ-normalized.

        Computes ||psi[b, end-1] - psi[b, end+1]|| / sqrt(d)
        using the real parts of both field vectors. End-of-sequence
        (end >= N) returns 1.0 as default residual.

        Returns 0-d tensor (no .item() syncs).
        """
        N = psi.shape[1]
        if end >= N:
            return psi.new_tensor(1.0)
        end_plus = min(end + 1, N - 1)
        # Psi residual: L2 distance between the real parts / sqrt(d)
        delta_psi = psi[b, end - 1].real - psi[b, end_plus].real
        return delta_psi.norm() / (self.d ** 0.5)

    # ════════════════════════════════════════════════
    #  Write
    # ════════════════════════════════════════════════

    @torch.no_grad()
    def write(self, psi: torch.Tensor, source: torch.Tensor,
              x: torch.Tensor, gate: torch.Tensor | None = None):
        """Store word-level field aggregates.

        Key = mean-pooled source.real across the word span.
        Value = mean-pooled psi (complex) across the word span.

        Same word → same key (same source aggregate) → same slot.
        The ψ aggregate captures the PDE-enhanced representation.

        Args:
            psi: [B, N, d] complex field (post-PDE integration).
            source: [B, N, d] complex field (pre-PDE embedder output).
            x: [B, N] token ids.
            gate: Optional Qi-gated write strength scalar or [B].
        """
        B = x.shape[0]
        spans = self._get_spans(x, psi=psi)
        update_strength = 1.0 - PHI_INV
        for b in range(B):
            if isinstance(gate, torch.Tensor) and gate.dim() > 0:
                g = gate[b].item()
            elif isinstance(gate, torch.Tensor):
                g = gate.item()
            else:
                g = 1.0

            batch_spans = spans[b]
            m = len(batch_spans)
            if m == 0:
                continue

            # ── Batch key extraction (GPU ops, no sync) ──
            keys = []
            for start, end, byte_seq, agg, residual_psi in batch_spans:
                keys.append(source[b, start:end].mean(dim=0).real)
            keys_tensor = torch.stack(keys)  # [m, d]

            # ── Batched slot matching (GPU op, no sync) ──
            sims = F.cosine_similarity(
                keys_tensor.unsqueeze(1),  # [m, 1, d]
                self.keys.unsqueeze(0),    # [1, num_slots, d]
                dim=2
            )  # [m, num_slots]
            best_idx_list = sims.argmax(dim=1).tolist()    # 1 sync
            best_score_list = sims.max(dim=1).values.tolist()  # 1 sync

            # ── Per-word EMA updates (no syncs in critical path) ──
            for i in range(m):
                start, end, byte_seq, agg, residual_psi = batch_spans[i]
                best = best_idx_list[i]
                best_sim = best_score_list[i]
                if best_sim > 0.5:
                    idx = best
                else:
                    # LRU eviction: oldest slot (rare, accept the sync)
                    idx = self.counts.argmax().item()

                residual_scale = residual_psi / (1.0 + residual_psi)
                effective_gate = g * residual_scale
                self.slots[idx] = (PHI_INV * self.slots[idx]
                                   + update_strength * effective_gate * agg)
                self.keys[idx] = keys[i]
                # Reset age for written slot, increment all
                self.counts[idx] = 0
                self.counts += 1

    # ════════════════════════════════════════════════
    #  Read
    # ════════════════════════════════════════════════

    @torch.no_grad()
    def read(self, source: torch.Tensor, x: torch.Tensor) -> torch.Tensor:
        """Inject stored word aggregates at known word spans.

        Same key derivation as write (mean-pooled source.real), so the
        same word retrieves the same slot. Injects the slot's stored
        aggregate at ALL positions of the span as a template boost.

        Args:
            source: [B, N, d] complex field (post-embed, pre-PDE).
            x: [B, N] token ids.

        Returns:
            boost: [B, N, d] complex, additive field boost.
        """
        B, N, d = source.shape
        boost = torch.zeros(B, N, d, dtype=torch.cfloat, device=source.device)
        spans = self._get_spans(x)
        for b in range(B):
            batch_spans = spans[b]
            m = len(batch_spans)
            if m == 0:
                continue

            # ── Batch key extraction (GPU ops, no sync) ──
            keys = []
            for start, end, _, _, _ in batch_spans:
                keys.append(source[b, start:end].mean(dim=0).real)
            keys_tensor = torch.stack(keys)  # [m, d]

            # ── Batched slot matching ──
            sims = F.cosine_similarity(
                keys_tensor.unsqueeze(1),
                self.keys.unsqueeze(0),
                dim=2
            )
            best_idx_list = sims.argmax(dim=1).tolist()
            best_score_list = sims.max(dim=1).values.tolist()

            # ── Inject boost for matching words ──
            for i in range(m):
                best = best_idx_list[i]
                if best_score_list[i] > 0.5:
                    start, end, _, _, _ = batch_spans[i]
                    boost[b, start:end] = self.slots[best].unsqueeze(0)
        return boost

    # ════════════════════════════════════════════════
    #  State management
    # ════════════════════════════════════════════════

    def reset_state(self):
        """Clear all stored memory."""
        self.slots.zero_()
        self.keys.zero_()
        self.counts.zero_()
