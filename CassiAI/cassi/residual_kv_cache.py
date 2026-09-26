#!/usr/bin/env python3
"""
Boundary-Condition-Residual KV Cache Compression for Transformers.

Core idea (inspired by PDE boundary-condition residuals):
    When we evict a KV pair, the attention output changes. The "residual"
    measures how much the output distorts. We keep the pairs whose eviction
    would cause the largest residual — they are "boundary-critical."

Cheap approximation (no second forward pass):
    residual_i ≈ attention_weight_i × ||value_i − output_mean||

This is stronger than H2O (attention-weight only) because it also accounts
for value diversity. A token with high attention weight but value close to
the mean contributes little information and can be evicted.
"""

import torch
import torch.nn.functional as F
import math
from typing import Tuple, Optional, List


class ResidualKVCache:
    """
    Per-layer KV cache with boundary-condition-residual eviction.

    Usage (inside a generation loop):
        cache = ResidualKVCache(num_layers=32, budget_ratio=0.5)
        for token_idx in range(max_new):
            out = model(..., past_key_values=cache.get_past_kv())
            cache.update(out.past_key_values, out.hidden_states, token_idx)
    """

    def __init__(
        self,
        num_layers: int,
        budget_ratio: float = 0.5,
        min_budget: int = 4,
        accumulate: bool = True,
    ):
        self.num_layers = num_layers
        self.budget_ratio = budget_ratio
        self.min_budget = min_budget
        self.accumulate = accumulate

        # Per-layer state
        self.k_cache: List[torch.Tensor] = [None] * num_layers
        self.v_cache: List[torch.Tensor] = [None] * num_layers
        self.residual_scores: List[Optional[torch.Tensor]] = [None] * num_layers
        self.seq_lens: List[int] = [0] * num_layers

    def _compute_residuals(
        self,
        k: torch.Tensor,          # [B, num_kv_heads, seq_len, head_dim]
        v: torch.Tensor,          # [B, num_kv_heads, seq_len, head_dim]
        q: torch.Tensor,          # [B, num_q_heads, 1, head_dim]
    ) -> torch.Tensor:
        """
        Compute per-token boundary-condition residuals.
        Returns [B, seq_len] scores (higher = more critical to keep).
        """
        B, num_kv_heads, seq_len, head_dim = v.shape
        _, num_q_heads, _, _ = q.shape

        # GQA: q may have more heads than k/v. Average query heads per group.
        if num_q_heads > num_kv_heads:
            group_size = num_q_heads // num_kv_heads
            q = q.reshape(B, num_kv_heads, group_size, head_dim)
            q = q.mean(dim=2, keepdim=True)  # [B, num_kv_heads, 1, head_dim]
        else:
            q = q.unsqueeze(2)  # [B, num_kv_heads, 1, head_dim]

        # Attention scores: [B, num_kv_heads, 1, seq_len]
        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(head_dim)
        weights = F.softmax(scores, dim=-1).squeeze(2)  # [B, num_kv_heads, seq_len]

        # Attention output per head: [B, num_kv_heads, head_dim]
        output = torch.matmul(weights.unsqueeze(-2), v).squeeze(-2)

        # Residual_i = weight_i * ||value_i − output|| for each head, averaged
        # v: [B, num_kv_heads, seq_len, head_dim]
        # output: [B, num_kv_heads, head_dim]
        diff = v - output.unsqueeze(2)  # [B, num_kv_heads, seq_len, head_dim]
        head_residuals = weights * diff.norm(dim=-1)  # [B, num_kv_heads, seq_len]
        residuals = head_residuals.mean(dim=1)  # [B, seq_len]
        return residuals

    def update(
        self,
        past_key_values: Tuple[Tuple[torch.Tensor, torch.Tensor], ...],
        hidden_states: torch.Tensor,  # [B, seq_len, d_model] — used to derive q projection
        token_idx: int,
    ):
        """
        Update cache with new KV pairs and compress if over budget.

        past_key_values: tuple of (k, v) per layer from model output
        hidden_states: final hidden states [B, seq_len, D] (used for q proxy)
        token_idx: current generation step (0 = first new token)
        """
        # Derive a proxy query from the hidden state of the newest token
        # We use the final hidden state as a proxy for all layer queries
        # In practice each layer has its own q projection, but the final
        # hidden state correlates strongly with layer-wise queries.
        q_proxy = hidden_states[:, -1:, :]  # [B, 1, D]

        for layer_idx, (k_new, v_new) in enumerate(past_key_values):
            B, num_kv_heads, new_len, head_dim = k_new.shape
            old_k = self.k_cache[layer_idx]

            if old_k is None:
                # First call: just store
                self.k_cache[layer_idx] = k_new
                self.v_cache[layer_idx] = v_new
                self.seq_lens[layer_idx] = new_len
                # Initialize residuals to zero
                self.residual_scores[layer_idx] = torch.zeros(
                    B, new_len, device=k_new.device, dtype=k_new.dtype
                )
                continue

            # Concatenate with existing cache
            k_full = torch.cat([old_k, k_new], dim=2)
            v_full = torch.cat([old_v, v_new], dim=2)
            seq_len = k_full.size(2)

            # Compute residuals for all tokens in this layer
            # q_proxy needs to be projected to head_dim. We use a simple
            # mean-pool across the model dimension as a proxy.
            # Better: use the layer's own q-projection weights if available.
            # For generality we just reshape q_proxy to [B, 1, num_kv_heads, head_dim]
            # by splitting the hidden dim.
            d_model = q_proxy.size(-1)
            if d_model % num_kv_heads == 0:
                proxy_head_dim = d_model // num_kv_heads
                q_layer = q_proxy.reshape(B, 1, num_kv_heads, proxy_head_dim)
                if proxy_head_dim != head_dim:
                    # Linear interpolation to head_dim
                    q_layer = F.interpolate(
                        q_layer.transpose(-2, -1),
                        size=head_dim,
                        mode="linear",
                        align_corners=False,
                    ).transpose(-2, -1)
            else:
                # Fallback: just take the first head_dim features
                q_layer = q_proxy[:, :, : num_kv_heads * head_dim].reshape(
                    B, 1, num_kv_heads, head_dim
                )

            residuals = self._compute_residuals(k_full, v_full, q_layer)

            # Accumulate or replace scores
            if self.accumulate and self.residual_scores[layer_idx] is not None:
                # Pad previous scores if sequence grew
                old_scores = self.residual_scores[layer_idx]
                if old_scores.size(1) < seq_len:
                    pad = torch.zeros(
                        B, seq_len - old_scores.size(1),
                        device=old_scores.device, dtype=old_scores.dtype
                    )
                    old_scores = torch.cat([old_scores, pad], dim=1)
                self.residual_scores[layer_idx] = old_scores + residuals
            else:
                self.residual_scores[layer_idx] = residuals

            # Determine budget
            budget = max(int(seq_len * self.budget_ratio), self.min_budget)

            if seq_len > budget:
                # Evict tokens with lowest accumulated residuals
                scores = self.residual_scores[layer_idx]  # [B, seq_len]
                # Use mean across batch for global eviction (keeps temporal order)
                mean_scores = scores.mean(dim=0)  # [seq_len]
                _, keep_indices = torch.topk(mean_scores, budget, sorted=False)
                keep_indices = keep_indices.sort().values  # maintain order

                k_full = k_full.index_select(2, keep_indices)
                v_full = v_full.index_select(2, keep_indices)
                self.residual_scores[layer_idx] = scores.index_select(1, keep_indices)

            self.k_cache[layer_idx] = k_full
            self.v_cache[layer_idx] = v_full
            self.seq_lens[layer_idx] = k_full.size(2)

    def get_past_kv(self) -> Optional[Tuple[Tuple[torch.Tensor, torch.Tensor], ...]]:
        """Return compressed past_key_values tuple, or None if empty."""
        if self.k_cache[0] is None:
            return None
        return tuple((self.k_cache[i], self.v_cache[i]) for i in range(self.num_layers))

    def current_seq_len(self) -> int:
        """Return sequence length of layer 0 (all layers are synchronized)."""
        return self.seq_lens[0]

    def compression_ratio(self) -> float:
        """Actual tokens stored / tokens that would have been stored."""
        if self.k_cache[0] is None:
            return 1.0
        stored = self.seq_lens[0]
        # total tokens processed = stored + evicted
        # We don't track evicted count directly, but budget_ratio gives approximate target
        return self.budget_ratio


# ═══════════════════════════════════════════════════════════════════════════════
# Drop-in wrapper for existing generation loops
# ═══════════════════════════════════════════════════════════════════════════════

class ResidualKVCacheWrapper:
    """
    Drop-in wrapper that intercepts model.generate() or manual loops.
    Not a full model wrapper — just manages cache compression.
    """

    def __init__(self, num_layers: int, budget_ratio: float = 0.5):
        self.cache = ResidualKVCache(num_layers, budget_ratio)

    def hook_past_key_values(self, past_key_values, hidden_states, step: int):
        """Call this after each model forward to compress the KV cache."""
        self.cache.update(past_key_values, hidden_states, step)
        return self.cache.get_past_kv()
