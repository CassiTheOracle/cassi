"""HarmonyBrain — Unified φ-Garden with Qi-Fluid, Gating, and Sparse Attention.

Single class with mode flags instead of 4 separate files:
  mode='qi'      → Qi-fluid rate modulation (original HarmonyBrain)
  mode='gated'   → Harmony-gated specialist features
  mode='combined'→ Both Qi-fluid + gating
  mode='sparse'  → Combined + dynamic top-k sparse specialist attention
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi.phi_garden import PhiGardenBrain
from cassi.cord import PHI, PHI_INV


class HarmonyBrain(PhiGardenBrain):
    """Conscious workspace with configurable harmony-based attention.

    Args:
        mode: 'qi' | 'gated' | 'combined' | 'sparse'
        min_k: minimum specialists for sparse mode (ignored otherwise)
    """

    def __init__(self, D=1040, n_specialists=5, n_slots=512,
                 memory_value_dim=26, readout_hidden=520, byte_mode=False,
                 mode='qi', min_k=1):
        super().__init__(D=D, n_specialists=n_specialists, n_slots=n_slots,
                         memory_value_dim=memory_value_dim,
                         readout_hidden=readout_hidden, byte_mode=byte_mode)

        self.mode = mode
        self.min_k = min_k
        self.N = n_specialists
        self.use_qi = mode in ('qi', 'combined', 'sparse')
        self.use_gating = mode in ('gated', 'combined', 'sparse')
        self.use_sparse = mode == 'sparse'

        # Persistent harmony state [N, N]
        self.register_buffer('harmony_state',
                             torch.zeros(n_specialists, n_specialists))

        if self.use_qi:
            # Qi fluid: accumulated harmony-weighted field energy [B, D]
            self.register_buffer('qi_fluid', torch.zeros(1, D))
            self.harmony_gate_qi = nn.Sequential(
                nn.Linear(D, D // 4),
                nn.ReLU(),
                nn.Linear(D // 4, D),
                nn.Sigmoid(),
            )

        if self.use_gating:
            # Specialist harmony gate: per-spec scaling [N] → [N]
            self.harmony_proj = nn.Sequential(
                nn.Linear(n_specialists, n_specialists),
                nn.ReLU(),
                nn.Linear(n_specialists, n_specialists),
                nn.Sigmoid(),
            )
            self.harmony_temp_scale = nn.Parameter(torch.ones(1) * 0.5)

        if self.use_sparse:
            # Learnable aperture control: harmony → effective k
            self.aperture_net = nn.Sequential(
                nn.Linear(1, 8),
                nn.ReLU(),
                nn.Linear(8, 1),
                nn.Sigmoid(),
            )

        # Meta-cord influence: observes field dynamics before competition
        # and biases which specialists get to harmonize (GWT broadcast controller)
        self.meta_harmony_gate = nn.Sequential(
            nn.Linear(D, n_specialists),
            nn.Sigmoid(),
        )

        # GWT workspace broadcast: consensus representation → specialist re-weighting
        self.workspace_broadcast = nn.Sequential(
            nn.Linear(D, 128),
            nn.ReLU(),
            nn.Linear(128, n_specialists),
        )

        if self.use_qi:
            # Meta-cord alternative Qi-fluid attention gate
            self.meta_qi_gate = nn.Sequential(
                nn.Linear(D, D // 4),
                nn.ReLU(),
                nn.Linear(D // 4, D),
                nn.Sigmoid(),
            )

    def reset_workspace(self, batch_size=1, reset_energy=False):
        super().reset_workspace(batch_size, reset_energy=reset_energy)
        if self.use_qi:
            self.qi_fluid = torch.zeros(batch_size, self.D, device=self.qi_fluid.device)

    def compute_harmony(self, all_f_stack):
        """Compute pairwise harmony and per-specialist scores.

        all_f_stack: [N, B, D]
        Returns:
          harmony_matrix: [N, N, B] pairwise cosine similarities
          harmony_score:  [N, B] per-specialist mean agreement
        """
        N, B, D = all_f_stack.shape
        f_norm = F.normalize(all_f_stack, dim=-1)
        sim = torch.einsum('nbd,mcd->nmb', f_norm, f_norm)
        mask = ~torch.eye(N, dtype=torch.bool, device=sim.device)
        harmony_matrix = sim * mask.unsqueeze(-1).float()
        harmony_score = harmony_matrix.sum(dim=1) / (N - 1)
        return harmony_matrix, harmony_score

    def _dynamic_topk_mask(self, scores, overall_harmony):
        """Vectorized sparse mask: keep top-k specialists per sample.

        scores: [N, B]
        overall_harmony: [1, B]
        Returns:
          mask: [N, B]
          k_eff: [B]
        """
        N, B = scores.shape

        aperture = self.aperture_net(overall_harmony.T).squeeze(-1)  # [B]
        k_float = self.min_k + aperture * (self.N - self.min_k)
        k_eff = k_float.clamp(self.min_k, self.N).long()  # [B]

        # Vectorized top-k — always use N to avoid device→host sync
        topk_vals, topk_idx = scores.topk(self.N, dim=0)  # [N, B]

        # Build mask without Python loop: scatter where position < k_eff
        rows = torch.arange(self.N, device=scores.device).unsqueeze(1).expand(-1, B)  # [N, B]
        valid = rows < k_eff.unsqueeze(0)  # [N, B]
        mask = torch.zeros_like(scores)
        mask.scatter_(0, topk_idx, valid.float())

        return mask, k_eff

    def forward(self, x, use_memory=True, return_workspace=False, byte_mode=None):
        if byte_mode is None:
            byte_mode = self.byte_mode

        if byte_mode:
            field = self.spine.byte_encoder.encode_sequence(x, T=4)
        else:
            field = x

        B = field.shape[0]
        device = field.device

        if self.workspace_fwd.shape[0] != B:
            self.reset_workspace(B)
        if self.workspace_fwd.device != device:
            self.workspace_fwd = self.workspace_fwd.to(device)
            self.workspace_rev = self.workspace_rev.to(device)
            self.field_history = self.field_history.to(device)
            if self.use_qi:
                self.qi_fluid = self.qi_fluid.to(device)

        # State buffers are persistent workspace state, not graph nodes.
        # Detach them at the start of each forward to prevent cross-batch
        # gradient accumulation and in-place corruption after optimizer steps.
        self.workspace_fwd = self.workspace_fwd.detach()
        self.workspace_rev = self.workspace_rev.detach()
        self.field_history = self.field_history.detach()
        if self.use_qi:
            self.qi_fluid = self.qi_fluid.detach()

        # --- Spine ---
        if getattr(self, '_spine_frozen', None) is None:
            self._spine_frozen = not any(p.requires_grad for p in self.spine.parameters())
        if self._spine_frozen:
            with torch.no_grad():
                pred_spine, trajectories = self.spine(
                    field, return_trajectories=True, byte_mode=False
                )
                repr_external = trajectories['repr']
            pred_spine = pred_spine.detach()
            repr_external = repr_external.detach()
        else:
            pred_spine, trajectories = self.spine(
                field, return_trajectories=True, byte_mode=False
            )
            repr_external = trajectories['repr']

        # --- Memory ---
        all_f_spine = None
        boundary_res = None
        if use_memory and self.berry_memory.n_filled.item() > 0:
            all_f_spine = self.spine.compute_all_f(trajectories['psi'])
            boundary_res = self.compute_boundary_residual(
                all_f_spine.unsqueeze(0)
            )
            berry_key = self.compute_berry_key(trajectories, boundary_res)
            retrieved, attn = self.berry_memory.query(berry_key, temperature=0.1)
            workspace_bias = self.memory_decompressor(retrieved)
        else:
            workspace_bias = torch.zeros(B, self.D, device=device)
            attn = torch.zeros(B, self.berry_memory.n_slots, device=device)

        # --- Field history ---
        field_current = repr_external + PHI_INV * workspace_bias
        self.field_history = torch.cat([
            self.field_history[:, 1:, :],
            field_current.unsqueeze(1)
        ], dim=1)

        # --- Meta-cord preview of field dynamics (pre-workspace) ---
        # The meta-cord observes raw field history and decides which specialists
        # should be allowed to broadcast to the workspace (GWT controller).
        meta_field_repr = self.meta_cord.compute_all_f(
            self.field_history, self.spine.chakra_gain
        )  # [B, D]
        meta_harmony_bias = self.meta_harmony_gate(meta_field_repr).T  # [N, B]

        # --- Specialists (batched across N) ---
        all_f_stack = self._compute_all_f_specialists_batched(
            self.field_history, self.spine.chakra_gain
        )  # [N, B, D]

        # === HARMONY ===
        harmony_matrix, harmony_score = self.compute_harmony(all_f_stack)
        # Meta-cord bias: boost/depress specialist harmony based on field preview
        harmony_score = harmony_score + 0.1 * meta_harmony_bias
        # Detach harmony_state to prevent cross-batch gradient accumulation
        harmony_state_old = self.harmony_state.detach()
        self.harmony_state = PHI_INV * harmony_state_old + PHI_INV**2 * harmony_matrix.mean(dim=-1)

        overall_harmony = harmony_score.mean(dim=0, keepdim=True)  # [1, B]
        harmony_scalar = overall_harmony.mean()

        # === GATING ===
        if self.use_gating:
            harmony_gate = self.harmony_proj(harmony_score.T).T  # [N, B]
            temperature = PHI * (1.0 + self.harmony_temp_scale * (1.0 - overall_harmony))
            # Clamp to avoid -inf * 0 = NaN in sparse masking
            temperature = temperature.clamp(min=1e-6)
        else:
            harmony_gate = torch.ones_like(harmony_score)
            temperature = PHI

        # === SPARSE ATTENTION ===
        amplitudes = all_f_stack.norm(dim=-1)  # [N, B]
        # Detach specialist_energy to prevent cross-batch gradient accumulation
        specialist_energy_old = self.specialist_energy.detach()
        effective_energy = torch.tanh(specialist_energy_old.unsqueeze(1))  # [N, 1]
        combined_score = effective_energy * amplitudes * (1.0 + harmony_gate)

        if self.use_sparse:
            sparse_mask, k_eff = self._dynamic_topk_mask(combined_score, overall_harmony)
            # Use a finite large-negative constant instead of -inf so that the
            # subsequent multiplication with learnable temperature does not produce
            # NaN gradients from -inf * 0 in the softmax backward.
            neg_large = torch.finfo(combined_score.dtype).min / 4
            sparse_score = combined_score.masked_fill(~sparse_mask.bool(), neg_large)
            weights = F.softmax(sparse_score * temperature, dim=0)
            contributions = (weights * sparse_mask).sum(dim=1)
        else:
            weights = F.softmax(combined_score * temperature, dim=0)
            contributions = weights.sum(dim=1)
            k_eff = None
            sparse_mask = None

        self.specialist_energy = PHI_INV * specialist_energy_old + (1 - PHI_INV) * (1.0 - contributions)
        self.specialist_energy = torch.clamp(self.specialist_energy, 0.1, 2.0)

        # === FUSION ===
        if self.use_gating:
            gated_features = all_f_stack * harmony_gate.unsqueeze(-1)
        else:
            gated_features = all_f_stack
        all_f_workspace = torch.einsum('nb,nbd->bd', weights, gated_features)

        field_last = self.field_history[:, -1, :]
        repr_workspace = self.spine.fusion(
            torch.cat([field_last, all_f_workspace * 0.5], -1)
        ) + field_last

        # === GWT WORKSPACE BROADCAST ===
        # The workspace consensus is broadcast back to specialists,
        # refining which specialists get to contribute (GWT "broadcast to all").
        workspace_consensus = all_f_workspace.detach()  # [B, D]
        broadcast_bias = torch.tanh(self.workspace_broadcast(workspace_consensus)).T  # [N, B]
        refined_weights = weights * (1.0 + 0.2 * broadcast_bias)
        refined_weights = refined_weights / (refined_weights.sum(dim=0, keepdim=True) + 1e-8)
        all_f_workspace = torch.einsum('nb,nbd->bd', refined_weights, gated_features)
        repr_workspace = self.spine.fusion(
            torch.cat([field_last, all_f_workspace * 0.5], -1)
        ) + field_last

        # === QI-FLUID ===
        if self.use_qi:
            # Detach old qi_fluid to prevent cross-batch gradient accumulation,
            # but allow gradients from current step to train harmony_gate_qi.
            qi_fluid_old = self.qi_fluid.detach()
            self.qi_fluid = PHI_INV * qi_fluid_old + PHI_INV**2 * harmony_scalar * all_f_workspace
            attention = self.harmony_gate_qi(self.qi_fluid)
            repr_workspace = attention * repr_workspace + (1 - attention) * field_last

        # === DUAL WORKSPACE ===
        self.workspace_fwd = PHI_INV * self.workspace_fwd + PHI_INV**2 * repr_workspace
        self.workspace_rev = PHI_INV * self.workspace_rev + PHI_INV**2 * self.workspace_fwd
        conscious = self.workspace_fwd - self.workspace_rev

        # === META-CORD (workspace observer) ===
        workspace_history = torch.stack([
            self.workspace_fwd, self.workspace_rev, conscious, field_last,
        ], dim=1)
        meta_repr = self.meta_cord.compute_all_f(workspace_history, self.spine.chakra_gain)

        # Meta-cord refines Qi-fluid attention post-hoc
        if self.use_qi:
            meta_attention = self.meta_qi_gate(meta_repr)
            attention = 0.7 * attention + 0.3 * meta_attention
            # Re-apply attention to get meta-cord influenced workspace
            repr_workspace = attention * repr_workspace + (1 - attention) * field_last
            # Update conscious state with meta-cord influence
            self.workspace_fwd = PHI_INV * self.workspace_fwd + PHI_INV**2 * repr_workspace
            conscious = self.workspace_fwd - self.workspace_rev

        meta_fused = self.spine.fusion(
            torch.cat([workspace_history[:, -1, :], meta_repr * 0.5], -1)
        ) + workspace_history[:, -1, :]
        self.workspace_fwd = self.workspace_fwd + PHI_INV**3 * meta_fused

        # === READOUT ===
        if self.use_qi:
            qi_readout_gate = torch.sigmoid(self.qi_fluid.mean(dim=-1, keepdim=True))
            residual = self.readout(conscious)
            pred_enhanced = pred_spine + qi_readout_gate * residual
        else:
            residual = self.readout(conscious)
            pred_enhanced = pred_spine + residual

        # === MEMORY ENCODING ===
        surprise = conscious.norm(dim=-1).mean().item()
        if not hasattr(self, '_surprise_ema'):
            self._surprise_ema = surprise
        self._surprise_ema = 0.95 * self._surprise_ema + 0.05 * surprise

        if use_memory and self._surprise_ema > 0.3:
            if all_f_spine is None:
                all_f_spine = self.spine.compute_all_f(trajectories['psi'])
            if boundary_res is None:
                boundary_res = self.compute_boundary_residual(all_f_spine.unsqueeze(0))
            berry_key = self.compute_berry_key(trajectories, boundary_res)
            workspace_summary = self.workspace_fwd.view(B, self.spine.C, -1).mean(dim=-1)
            value = torch.cat([workspace_summary, boundary_res], dim=1)
            # Write is a state update — keep it out of the autograd graph
            with torch.no_grad():
                self.berry_memory.write(berry_key.detach(), value.detach(), mode='ema')

        info = {
            'pred_spine': pred_spine,
            'conscious': conscious,
            'weights': weights,
            'energy': self.specialist_energy.detach(),
            'surprise': surprise,
            'harmony': harmony_score.detach(),
            'harmony_matrix': self.harmony_state.clone(),
            'mean_harmony': overall_harmony.detach(),
        }
        if self.use_gating:
            info['harmony_gate'] = harmony_gate.detach()
        if self.use_qi:
            info['qi_fluid'] = self.qi_fluid.clone()
            info['qi_readout_gate'] = qi_readout_gate.detach()
        if self.use_sparse:
            info['sparse_mask'] = sparse_mask.detach()
            info['k_eff'] = k_eff.detach()
        if use_memory and self.berry_memory.n_filled.item() > 0:
            info['memory_attn'] = attn.detach()

        if return_workspace:
            return pred_enhanced, info
        return pred_enhanced
