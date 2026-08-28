"""
Berry Memory Brain — permanent topological memory for CordPhysics.

Spine stays minimal: CordPhysics computes predictions + optional trajectories.
Brain does everything else: Berry phase extraction, memory storage/retrieval,
and prediction enhancement.

Design principle: spine = fast predictor, brain = slow permanent memory.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np


def compute_berry_phases(trajectories, widths, spans, device=None):
    """Compute per-chakra Berry phases from IIR trajectories.

    trajectories: dict with 'fwd' and 'rev', each is list of [4, B, W_f] tensors
    widths: list of 13 chakra widths
    spans: list of 4 fiber spans [(0,3), (3,6), (6,9), (9,13)]

    Returns: [B, 26] tensor (13 yang + 13 yin phases)
    """
    batch_size = trajectories['fwd'][0].shape[1]
    if device is None:
        device = trajectories['fwd'][0].device
    phases = []

    for hemisphere in ['fwd', 'rev']:
        traj_list = trajectories[hemisphere]  # list of 4 fiber trajectories

        for c in range(len(widths)):
            w = widths[c]
            if w <= 0:
                phases.append(torch.zeros(batch_size, device=device))
                continue

            # Find which fiber contains chakra c
            for f, (start, end) in enumerate(spans):
                if start <= c < end:
                    fiber_traj = traj_list[f]  # [4, B, W_fiber]
                    c_start = sum(widths[start:c])
                    c_end = c_start + w
                    chakra_traj = fiber_traj[:, :, c_start:c_end]  # [4, B, w]
                    break

            # Vectorized signed area over entire batch
            t = chakra_traj  # [4, B, w]
            if w >= 2:
                x = t[:, :, 0]  # [4, B]
                y = t[:, :, 1]  # [4, B]
            else:
                x = t[:, :, 0]  # [4, B]
                y = torch.cat([
                    torch.zeros(1, batch_size, device=x.device),
                    x[:-1]
                ], dim=0)  # [4, B]

            # Signed area via shoelace formula, summed over time
            area = 0.5 * torch.sum(x[:-1] * y[1:] - x[1:] * y[:-1], dim=0)  # [B]
            phases.append(area)

    return torch.stack(phases, dim=1)  # [B, 26]


class BerryMemory(nn.Module):
    """Permanent topological memory bank keyed by Berry phases.

    Fixed-size slot memory. Each slot stores:
      - key: 26-dim Berry fingerprint (normalized)
      - value: D-dim representation + 1024-dim residual
      - count: how many times this pattern was seen
      - age: timesteps since last access
    """

    def __init__(self, D=1040, n_slots=4096, key_dim=26, value_dim=1040,
                 ema_decay=0.9, similarity_threshold=0.85):
        super().__init__()
        self.D = D
        self.n_slots = n_slots
        self.key_dim = key_dim
        self.value_dim = value_dim
        self.ema_decay = ema_decay
        self.similarity_threshold = similarity_threshold

        # Memory banks (buffers = not backpropped, but saved in state_dict)
        self.register_buffer('keys', torch.zeros(n_slots, key_dim))
        self.register_buffer('values', torch.zeros(n_slots, value_dim))
        self.register_buffer('counts', torch.zeros(n_slots))
        self.register_buffer('ages', torch.zeros(n_slots, dtype=torch.long))
        self.register_buffer('mask', torch.zeros(n_slots, dtype=torch.bool))  # which slots are occupied
        self.register_buffer('n_filled', torch.zeros(1, dtype=torch.long))
        self._n_filled = 0  # Python mirror to avoid GPU→CPU sync on hot path

        # Parallel trajectory store: slot index → list of trajectory milestones
        # Stores sparse dynamical context (conscious, workspace, qi, etc.) alongside
        # the compressed value vector. Not saved in state_dict by default.
        self.trajectory_store = {}
        self._max_traj_per_slot = 4  # keep last N milestones per memory slot

    def _load_from_state_dict(self, state_dict, prefix, local_metadata, strict, missing_keys, unexpected_keys, error_msgs):
        """Re-sync Python mirror after checkpoint load."""
        super()._load_from_state_dict(state_dict, prefix, local_metadata, strict, missing_keys, unexpected_keys, error_msgs)
        # _n_filled is not a buffer, so it resets to 0 on load. Recompute from mask.
        mask = self.mask
        if mask is not None:
            self._n_filled = int(mask.sum().item())
            self.n_filled[0] = self._n_filled

    def query(self, berry_fp, temperature=0.1, topk=64, return_trajectories=False):
        """Retrieve from memory via sparse top-k attention on Berry keys.

        berry_fp: [B, key_dim]
        topk: number of memory slots to attend to (sparse, like specialist attention)
        return_trajectories: if True, also return trajectory milestones for top-k slots
        Returns:
          retrieved: [B, value_dim]
          attn: [B, n_slots]
          trajectories: list of list of dicts (only if return_trajectories=True)
        """
        B = berry_fp.shape[0]
        if self._n_filled == 0:
            empty_ret = torch.zeros(B, self.value_dim, device=berry_fp.device), \
                        torch.zeros(B, self.n_slots, device=berry_fp.device)
            if return_trajectories:
                return empty_ret[0], empty_ret[1], [[] for _ in range(B)]
            return empty_ret

        q = F.normalize(berry_fp, dim=-1)  # [B, key_dim]
        k = F.normalize(self.keys, dim=-1)  # [n_slots, key_dim]

        # Cosine similarity
        sim = q @ k.T  # [B, n_slots]

        # Mask empty slots with dtype-safe minimum (float16 can't represent -1e9)
        sim = sim.masked_fill(~self.mask.unsqueeze(0), torch.finfo(sim.dtype).min)

        # Sparse top-k attention: only compute softmax over top-k slots.
        # This mirrors the specialist sparse attention in HarmonyBrain.
        k_sparse = min(topk, self._n_filled)
        topk_sim, topk_idx = sim.topk(k_sparse, dim=-1)  # [B, k_sparse]
        attn_sparse = F.softmax(topk_sim / temperature, dim=-1)  # [B, k_sparse]

        # Retrieve via batched matrix multiply: [B, 1, k] @ [B, k, value_dim]
        values_snapshot = self.values.clone()
        retrieved = torch.bmm(
            attn_sparse.unsqueeze(1),
            values_snapshot[topk_idx]
        ).squeeze(1)  # [B, value_dim]

        # Reconstruct full attention for logging/debugging (zero-padded)
        attn = torch.zeros(B, self.n_slots, device=berry_fp.device)
        attn.scatter_(1, topk_idx, attn_sparse)

        if return_trajectories:
            trajectories = []
            for b in range(B):
                batch_trajs = []
                for slot in topk_idx[b].cpu().tolist():
                    batch_trajs.extend(self.trajectory_store.get(slot, []))
                trajectories.append(batch_trajs)
            return retrieved, attn, trajectories

        return retrieved, attn

    def write(self, berry_fp, values, mode='ema', trajectories=None):
        """Write to memory. If similar key exists, EMA-update; else, new slot.

        berry_fp: [B, key_dim]
        values: [B, value_dim]
        mode: 'ema' | 'replace' | 'cumulative'
        trajectories: optional list of B trajectory milestone dicts

        Fully batched GPU implementation for speed.
        """
        B = berry_fp.shape[0]
        if B == 0:
            with torch.no_grad():
                self.ages[self.mask] += 1
            return

        device = berry_fp.device
        # Ensure dtype matches memory buffers (AMP can produce float16 inputs)
        berry_fp = berry_fp.to(self.keys.dtype)
        values = values.to(self.values.dtype)
        q = F.normalize(berry_fp, dim=-1)

        # Batched similarity: [B, n_slots]
        if self._n_filled > 0:
            k = F.normalize(self.keys, dim=-1)
            sims = q @ k.T
            sims = sims.masked_fill(~self.mask.unsqueeze(0), torch.finfo(sims.dtype).min)
            # Guard against NaN from corrupted keys
            if torch.isnan(sims).any():
                sims = torch.nan_to_num(sims, nan=torch.finfo(sims.dtype).min)
            best_sims, best_idx = sims.max(dim=-1)
            # Clamp indices to valid range
            best_idx = best_idx.clamp(0, self.n_slots - 1)
        else:
            best_sims = torch.full((B,), -1.0, device=device)
            best_idx = torch.zeros(B, dtype=torch.long, device=device)

        match_mask = best_sims > self.similarity_threshold
        new_mask = ~match_mask

        # All mutations happen in no_grad to save memory and avoid autograd issues
        with torch.no_grad():
            # --- Update existing slots (vectorized) ---
            if match_mask.any():
                match_idx = best_idx[match_mask]
                match_fp = q[match_mask]
                match_val = values[match_mask]

                # Sanitize indices before unique to prevent overflow crash
                match_idx = match_idx.clamp(0, self.n_slots - 1)
                unique_idx, inverse = torch.unique(match_idx, return_inverse=True)

                # Count per slot
                group_counts = torch.zeros(len(unique_idx), device=device)
                group_counts.scatter_add_(0, inverse, torch.ones(len(inverse), device=device))

                # Sum keys and values per slot
                new_key_sums = torch.zeros(len(unique_idx), self.key_dim, device=device)
                new_key_sums.scatter_add_(0, inverse.unsqueeze(-1).expand(-1, self.key_dim), match_fp)
                new_val_sums = torch.zeros(len(unique_idx), self.value_dim, device=device)
                new_val_sums.scatter_add_(0, inverse.unsqueeze(-1).expand(-1, self.value_dim), match_val)

                # Average per group
                avg_keys = new_key_sums / group_counts.unsqueeze(-1).clamp(min=1)
                avg_vals = new_val_sums / group_counts.unsqueeze(-1).clamp(min=1)

                if mode == 'ema':
                    old_counts = self.counts[unique_idx]
                    alpha = 1.0 / (old_counts + 1.0)
                    self.keys[unique_idx] = (1 - alpha.unsqueeze(-1)) * self.keys[unique_idx] + alpha.unsqueeze(-1) * avg_keys
                    self.values[unique_idx] = (1 - alpha.unsqueeze(-1)) * self.values[unique_idx] + alpha.unsqueeze(-1) * avg_vals
                elif mode == 'replace':
                    self.keys[unique_idx] = avg_keys
                    self.values[unique_idx] = avg_vals
                else:  # cumulative
                    self.keys[unique_idx] = self.keys[unique_idx] + avg_keys
                    self.values[unique_idx] = self.values[unique_idx] + avg_vals

                self.counts[unique_idx] += 1
                self.ages[unique_idx] = 0

            # --- Write new slots ---
            if new_mask.any():
                new_fp = q[new_mask]
                new_val = values[new_mask]
                N_new = new_fp.shape[0]

                # Discover empty slots dynamically; never use n_filled as a contiguous pointer
                empty = torch.where(~self.mask)[0]
                n_empty = empty.shape[0]
                if n_empty >= N_new:
                    assigned = empty[:N_new]
                else:
                    assigned_empty = empty[:N_new]  # PyTorch slice past end is safe
                    n_evict = N_new - assigned_empty.shape[0]
                    if n_evict > 0 and self._n_filled > 0:
                        n_evict = min(n_evict, self._n_filled)
                        filled_ages = self.ages.clone()
                        filled_ages[~self.mask] = -1
                        _, evict_idx = torch.topk(filled_ages, n_evict)
                        assigned = torch.cat([assigned_empty, evict_idx])
                    else:
                        assigned = assigned_empty

                n_assign = len(assigned)
                self.keys[assigned] = new_fp[:n_assign]
                self.values[assigned] = new_val[:n_assign]
                self.counts[assigned] = 1
                self.ages[assigned] = 0
                self.mask[assigned] = True

            # Sync Python mirror after writes
            self._n_filled = int(self.mask.sum().item())
            self.n_filled[0] = self._n_filled

            # --- Store process trajectories (sparse milestones) ---
            if trajectories is not None:
                # Build per-batch-item slot assignment
                slot_per_item = torch.zeros(B, dtype=torch.long, device=device)
                slot_per_item[match_mask] = best_idx[match_mask]
                if new_mask.any():
                    slot_per_item[new_mask] = assigned

                # Clear trajectory_store entries for evicted slots
                evicted = set()
                if new_mask.any() and n_empty < N_new:
                    for ev in evict_idx.cpu().tolist():
                        evicted.add(ev)
                        self.trajectory_store.pop(ev, None)

                # Store trajectories, keeping only most recent max_traj_per_slot
                for b in range(B):
                    slot = int(slot_per_item[b].item())
                    traj = trajectories[b]
                    if traj is None:
                        continue
                    if slot not in self.trajectory_store:
                        self.trajectory_store[slot] = []
                    self.trajectory_store[slot].append(traj)
                    if len(self.trajectory_store[slot]) > self._max_traj_per_slot:
                        self.trajectory_store[slot].pop(0)

            # Increment ages for all occupied slots
            self.ages[self.mask] += 1

    def prune(self, min_count=2):
        """Remove slots with count < min_count."""
        keep = self.counts >= min_count
        self.mask &= keep
        self.counts[~keep] = 0
        self.ages[~keep] = 0
        self._n_filled = int(self.mask.sum().item())
        self.n_filled[0] = self._n_filled

    def get_stats(self):
        """Return memory statistics."""
        n = self.n_filled.item()
        if n == 0:
            return {'filled': 0, 'mean_count': 0.0, 'max_age': 0}
        return {
            'filled': n,
            'mean_count': self.counts[:n].mean().item(),
            'max_age': self.ages[:n].max().item(),
        }


class BerryMemoryBrain(nn.Module):
    """Brain that uses Berry-phase memory to enhance CordPhysics predictions.

    Architecture:
      1. CordPhysics spine predicts next frame (frozen or co-trained)
      2. Berry phases extracted from IIR trajectories
      3. Memory bank retrieves similar past patterns
      4. Small MLP fuses (spine_repr, memory_value) → prediction residual
    """

    def __init__(self, D=1040, n_slots=4096, memory_value_dim=1040,
                 enhancer_hidden=256, temperature=0.1):
        super().__init__()
        self.D = D
        self.temperature = temperature

        # Permanent topological memory
        self.memory = BerryMemory(
            D=D, n_slots=n_slots, key_dim=26,
            value_dim=memory_value_dim,
        )

        # Prediction enhancer: (repr, memory_retrieval) → residual correction
        self.enhancer = nn.Sequential(
            nn.Linear(D + memory_value_dim, enhancer_hidden),
            nn.ReLU(),
            nn.Linear(enhancer_hidden, enhancer_hidden),
            nn.ReLU(),
            nn.Linear(enhancer_hidden, 1024),
        )

        # Value encoder: repr → memory_value
        self.value_encoder = nn.Linear(D, memory_value_dim)

    def forward(self, spine, x, use_memory=True):
        """Forward pass with optional memory enhancement.

        x: [B, 4, 1024]
        Returns: dict with 'pred', 'enhanced_pred', 'berry_fp', 'memory_attn'
        """
        # Spine prediction + trajectories
        pred, trajectories = spine(x, return_trajectories=True)
        repr_vec = trajectories['repr']  # [B, D]

        # Berry phases
        berry_fp = compute_berry_phases(
            trajectories, spine.widths, spine.spans, device=x.device)

        if use_memory and self.memory.n_filled.item() > 0:
            # Query memory
            retrieved, attn = self.memory.query(berry_fp, temperature=self.temperature)

            # Enhance prediction
            fusion_input = torch.cat([repr_vec, retrieved], dim=-1)
            residual = self.enhancer(fusion_input)
            enhanced_pred = pred + residual
        else:
            enhanced_pred = pred
            attn = torch.zeros(x.shape[0], self.memory.n_slots, device=x.device)

        return {
            'pred': pred,
            'enhanced_pred': enhanced_pred,
            'repr': repr_vec,
            'berry_fp': berry_fp,
            'memory_attn': attn,
        }

    def memorize(self, spine, x, target, mode='ema'):
        """Store prediction experience in memory.

        x: [B, 4, 1024]
        target: [B, 1024]
        """
        with torch.no_grad():
            pred, trajectories = spine(x, return_trajectories=True)
            repr_vec = trajectories['repr']
            berry_fp = compute_berry_phases(
                trajectories, spine.widths, spine.spans, device=x.device)

            # Encode value: the representation associated with this Berry phase
            value = self.value_encoder(repr_vec)  # [B, value_dim]

        self.memory.write(berry_fp.detach(), value.detach(), mode=mode)

    def get_memory_stats(self):
        return self.memory.get_stats()
