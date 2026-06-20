"""QiPatternMemory — adaptive pattern-neuron bank for QiField.

Pattern neurons are learnable key/value slots that grow and dissolve based on
running statistics of Qi and query-key similarity.  Growth and dissolution are
slot-management heuristics; only the keys, values, query projection, thermostat,
and std-logits participate in backpropagation.
"""

from typing import Any, Dict, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F


class QiPatternMemory(nn.Module):
    """Adaptive pattern-neuron bank with complex-valued read/write.

    Args:
        d: Dimension of the (real) field query.
        max_neurons: Maximum number of pattern-neuron slots.
    """

    def __init__(self, d: int, max_neurons: int = 512):
        super().__init__()
        self.d = d
        self.max_neurons = max_neurons

        # Learnable keys and complex values.
        self.keys = nn.Parameter(torch.empty(max_neurons, d))
        self.values_real = nn.Parameter(torch.empty(max_neurons, d))
        self.values_imag = nn.Parameter(torch.empty(max_neurons, d))
        self.query_proj = nn.Linear(d, d, bias=False)

        nn.init.normal_(self.keys, std=0.02)
        nn.init.zeros_(self.values_real)
        nn.init.zeros_(self.values_imag)
        nn.init.normal_(self.query_proj.weight, std=0.02)

        # Adaptive threshold logits.
        # grow_std_logit -> F.softplus ≈ 1.0 (moderate-Qi tail, not too rare)
        self.grow_std_logit = nn.Parameter(torch.tensor(0.95))
        # novelty_std_logit -> F.softplus ≈ 1.5 (threshold well below mean similarity)
        self.novelty_std_logit = nn.Parameter(torch.tensor(1.35))

        # Persistent slot state (not gradient-bearing).
        self.register_buffer('usage', torch.zeros(max_neurons, dtype=torch.long))
        self.register_buffer('age', torch.zeros(max_neurons, dtype=torch.long))
        self.register_buffer('born', torch.zeros(max_neurons, dtype=torch.bool))
        self.register_buffer('key_ema', torch.zeros(max_neurons, d))
        self.register_buffer('birth_step', torch.full((max_neurons,), -1, dtype=torch.long))

        # Running statistics of Qi and similarity (momentum 0.99).
        self.register_buffer('qi_mean', torch.zeros(1))
        self.register_buffer('qi_std', torch.ones(1))
        self.register_buffer('sim_mean', torch.zeros(1))
        self.register_buffer('sim_std', torch.ones(1))

        # Per-sequence Qi EMA, reset by QiField.reset_state().
        self.register_buffer('qi_ema', torch.zeros(1, 1))

        # Pattern thermostat: online multiplier for how many slots may be born.
        self.thermostat = nn.Sequential(
            nn.Linear(5, 16), nn.Tanh(),
            nn.Linear(16, 1), nn.Softplus())
        # Init small and set the final bias so initial max_new_raw ≈ 2.0.
        for m in self.thermostat.modules():
            if isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, std=0.02)
                nn.init.zeros_(m.bias)
                m.bias.data.fill_(2.0)

    def _ensure_qi_ema(self, N: int, device: torch.device, dtype: torch.dtype) -> None:
        """Lazily resize the per-sequence Qi EMA buffer."""
        if (self.qi_ema.shape[1] != N or self.qi_ema.device != device
                or self.qi_ema.dtype != dtype):
            self.qi_ema.data = torch.zeros(1, N, device=device, dtype=dtype)

    @staticmethod
    def _entropy(p: torch.Tensor) -> torch.Tensor:
        """Shannon entropy of a discrete distribution."""
        p = p.clamp_min(1e-8)
        return -(p * p.log()).sum()

    def forward(self, query: torch.Tensor, qi: torch.Tensor, top_k: int = 8
                ) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, Any]]:
        """Retrieve pattern residuals for the current field state.

        Args:
            query: [B, N, d] real field state.
            qi: [B, N] Qi values. Always supplied by the caller; pass zeros during
                inference if truly unavailable.
            top_k: Number of neurons to retrieve per position.

        Returns:
            residual_real, residual_imag, diagnostics
        """
        B, N, d = query.shape
        assert d == self.d
        device = query.device
        dtype = query.dtype

        # Lightweight inference path: maintain qi_ema even though grow() is not
        # called.  During training, grow() owns the single update per field step.
        if not self.training:
            self._ensure_qi_ema(N, device, dtype)
            with torch.no_grad():
                self.qi_ema.data.copy_(
                    0.9 * self.qi_ema + 0.1 * qi.mean(dim=0, keepdim=True))

        query = self.query_proj(query)
        active_mask = self.born
        n_active = int(active_mask.sum().item())
        if n_active == 0:
            zero = torch.zeros_like(query)
            diagnostics = {
                'pm_active': 0,
                'pm_usage_entropy': torch.tensor(0.0, device=device, dtype=dtype),
                'pm_max_usage': 0,
                'pm_born_ratio': torch.tensor(0.0, device=device, dtype=dtype),
                'pm_commit_loss': torch.tensor(0.0, device=device, dtype=dtype),
                'p_k': torch.zeros(0, device=device, dtype=dtype),
            }
            return zero, zero, diagnostics

        active_idx = torch.nonzero(active_mask, as_tuple=False).view(-1)
        keys_active = self.keys[active_idx]  # [active, d]
        sim = torch.matmul(query, keys_active.T)  # [B, N, active]

        k = min(top_k, n_active)
        top_vals, top_idx = torch.topk(sim, k, dim=-1)  # [B, N, k]
        attn = F.softmax(top_vals, dim=-1)  # [B, N, k]

        # Retrieve values via batched indexing.
        vals_real_active = self.values_real[active_idx]  # [active, d]
        vals_imag_active = self.values_imag[active_idx]
        gathered_real = vals_real_active[top_idx]  # [B, N, k, d]
        gathered_imag = vals_imag_active[top_idx]
        gathered_keys = keys_active[top_idx]

        attn_expanded = attn.unsqueeze(-1)  # [B, N, k, 1]
        retrieved_keys = (gathered_keys * attn_expanded).sum(dim=2)  # [B, N, d]
        residual_real = (gathered_real * attn_expanded).sum(dim=2)   # [B, N, d]
        residual_imag = (gathered_imag * attn_expanded).sum(dim=2)   # [B, N, d]

        # Commitment: keys should reconstruct the projected query.
        commit_loss = ((query.detach() - retrieved_keys) ** 2).mean()

        # Update usage counters for retrieved slots.
        with torch.no_grad():
            flat_retrieved = active_idx[top_idx.reshape(-1)]
            self.usage.data[flat_retrieved] += 1

        # Distribution over born neurons used in this forward.
        p_full = torch.zeros(self.max_neurons, device=device, dtype=dtype)
        neuron_global_idx = active_idx[top_idx.reshape(-1)].view(-1)
        p_full.scatter_add_(0, neuron_global_idx, attn.reshape(-1))
        p_full = p_full / (B * N)
        entropy = self._entropy(p_full)

        born_ratio = self.born.float().mean()
        diagnostics = {
            'pm_active': n_active,
            'pm_usage_entropy': entropy,
            'pm_max_usage': int(self.usage.max().item()),
            'pm_born_ratio': born_ratio,
            'pm_commit_loss': commit_loss,
            'p_k': attn.mean(dim=(0, 1)),
        }
        return residual_real, residual_imag, diagnostics

    def grow(self, query: torch.Tensor, qi: torch.Tensor,
             current_step: int = 0) -> int:
        """Potentially grow new pattern-neuron slots.

        Args:
            query: [B, N, d] projected or unprojected field state.
            qi: [B, N] Qi values.
            current_step: Global training step for birth records.

        Returns:
            Number of new neurons created.
        """
        if current_step < 50:
            # Burn-in: let running statistics stabilize.
            with torch.no_grad():
                self.age[self.born] += 1
            return 0

        B, N, d = query.shape
        device = query.device
        dtype = query.dtype

        with torch.no_grad():
            # Update running statistics of Qi.
            qi_mean = qi.mean()
            qi_std = qi.std().clamp_min(1e-6)
            self.qi_mean.data.copy_(0.99 * self.qi_mean + 0.01 * qi_mean)
            self.qi_std.data.copy_(0.99 * self.qi_std + 0.01 * qi_std)
            grow_threshold = self.qi_mean + F.softplus(self.grow_std_logit) * self.qi_std

            # Update per-sequence Qi EMA (single owner: grow()).
            self._ensure_qi_ema(N, device, dtype)
            qi_ema = 0.9 * self.qi_ema + 0.1 * qi.mean(dim=0, keepdim=True)
            self.qi_ema.data.copy_(qi_ema.detach())
            qi_ema = qi_ema.expand(B, N)

            # Candidate positions with elevated, sustained Qi.
            candidate_mask = qi_ema > grow_threshold
            if not candidate_mask.any():
                self.age[self.born] += 1
                return 0

            # Use the projected query for similarity (matches forward lookup).
            q_proj = self.query_proj(query).detach().view(-1, d)

            # Max similarity of each position to all born keys.
            if self.born.any():
                active_idx = torch.nonzero(self.born, as_tuple=False).view(-1)
                keys_active = self.keys[active_idx]
                sim_all = torch.matmul(q_proj, keys_active.T)
                max_sim = sim_all.max(dim=-1).values.view(B, N)
            else:
                max_sim = torch.full((B, N), -1e6, device=device, dtype=dtype)

            # Update running statistics of max similarity, ignoring the
            # sentinel -1e6 value used when no neurons are born yet.
            valid_sim = max_sim[max_sim > -1e5]
            if valid_sim.numel() > 0:
                sim_mean = valid_sim.mean()
                sim_std = valid_sim.std().clamp_min(1e-6)
            else:
                sim_mean = self.sim_mean.to(device=device, dtype=dtype)
                sim_std = self.sim_std.to(device=device, dtype=dtype)
            self.sim_mean.data.copy_(0.99 * self.sim_mean + 0.01 * sim_mean)
            self.sim_std.data.copy_(0.99 * self.sim_std + 0.01 * sim_std)

            # Filter to novel positions.
            novelty_threshold = self.sim_mean - F.softplus(self.novelty_std_logit) * self.sim_std
            # Keep the gate in a sensible, positive regime.  If running std is
            # large, the learned threshold can drop below zero and reject every
            # query; floor it relative to the mean similarity.
            novelty_floor = (0.5 * self.sim_mean).clamp(min=0.05)
            novelty_threshold = torch.maximum(novelty_threshold, novelty_floor)
            candidate_mask = candidate_mask & (max_sim < novelty_threshold)
            if not candidate_mask.any():
                self.age[self.born] += 1
                return 0

            # Adaptive cap on how many neurons may be born this step.
            # The thermostat gives a small base rate; we add a capacity-aware
            # boost so the bank fills quickly when nearly empty and tapers as
            # it approaches its target utilization.
            born_ratio = self.born.float().mean()
            thermostat_input = torch.stack([
                self.qi_mean.view(()),
                self.qi_std.view(()),
                self.sim_mean.view(()),
                self.sim_std.view(()),
                born_ratio.view(()),
            ]).to(device=device, dtype=dtype)
            max_new_raw = self.thermostat(thermostat_input.unsqueeze(0)).squeeze()
            headroom = 1.0 - born_ratio
            capacity_boost = headroom * self.max_neurons * 0.05
            n_active = int(self.born.sum().item())
            max_new = min(
                int((max_new_raw + capacity_boost).item() + 0.5),
                self.max_neurons - n_active,
                max(1, self.max_neurons // 4),
            )

            # Score candidates by sustained Qi and take the top few.
            scores = qi_ema[candidate_mask]
            n_candidates = scores.numel()
            n_new = min(max_new, n_candidates)
            if n_new <= 0:
                self.age[self.born] += 1
                return 0

            candidate_flat = torch.nonzero(
                candidate_mask.view(-1), as_tuple=False).view(-1)
            top_indices = torch.topk(scores, n_new).indices
            chosen_flat = candidate_flat[top_indices]

            n_created = 0
            if n_new > 0:
                # Vectorized slot selection: free slots first, then lowest-utilization born slots.
                unborn_idx = torch.nonzero(~self.born, as_tuple=False).view(-1)
                n_unborn = min(int(unborn_idx.numel()), n_new)
                slot_chunks = []
                if n_unborn > 0:
                    slot_chunks.append(unborn_idx[:n_unborn])
                n_needed = n_new - n_unborn
                if n_needed > 0:
                    born_idx = torch.nonzero(self.born, as_tuple=False).view(-1)
                    util = (self.usage[born_idx].float()
                            / (self.age[born_idx].float() + 1.0))
                    _, sort_local = torch.sort(util)
                    slot_chunks.append(born_idx[sort_local[:n_needed]])
                slots = (slot_chunks[0] if len(slot_chunks) == 1
                         else torch.cat(slot_chunks))

                # Batched writes to all selected slots.
                q_new = q_proj[chosen_flat[:slots.numel()]]
                self.keys.data[slots] = q_new
                self.values_real.data[slots] = 0.0
                self.values_imag.data[slots] = 0.0
                self.key_ema.data[slots] = q_new
                self.born.data[slots] = True
                self.usage.data[slots] = 1
                self.age.data[slots] = 0
                self.birth_step.data[slots] = current_step
                n_created = int(slots.numel())

            self.age[self.born] += 1
            return n_created

    def dissolve(self, current_step: int = 0) -> int:
        """Prune under-utilized neurons.

        Args:
            current_step: Global training step for age gating.

        Returns:
            Number of neurons dissolved.
        """
        with torch.no_grad():
            if not self.born.any():
                return 0
            born_idx = torch.nonzero(self.born, as_tuple=False).view(-1)
            util = (self.usage[born_idx].float()
                    / (self.age[born_idx].float() + 1.0))
            age_gate = self.age[born_idx] > max(100, current_step // 10)
            util_eligible = util[age_gate]
            if util_eligible.numel() == 0:
                return 0
            n_dissolve = max(1, int(len(born_idx) * 0.01))
            eligible = born_idx[age_gate]
            sort_idx = torch.sort(util_eligible)[1]
            n_dissolve = min(n_dissolve, sort_idx.numel())
            victims = eligible[sort_idx[:n_dissolve]]

            self.keys.data[victims] = 0.0
            self.values_real.data[victims] = 0.0
            self.values_imag.data[victims] = 0.0
            self.key_ema.data[victims] = 0.0
            self.born.data[victims] = False
            self.usage.data[victims] = 0
            self.age.data[victims] = 0
            self.birth_step.data[victims] = -1
            return int(victims.numel())
