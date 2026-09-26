"""HarmonyBrain — Unified φ-Garden with Qi-Fluid, Gating, and Sparse Attention.

Single class with mode flags instead of 4 separate files:
  mode='qi'      → Qi-fluid rate modulation (original HarmonyBrain)
  mode='gated'   → Harmony-gated specialist features
  mode='combined'→ Both Qi-fluid + gating
  mode='sparse'  → Combined + dynamic top-k sparse specialist attention
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi.phi_garden import PhiGardenBrain
from cassi.cord import PHI, PHI_INV
from cassi.breath import Breath


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
            # Qi-fluid = accumulated overlap between Yang (workspace_fwd) and Yin (workspace_rev)
            # Qi energy = total overlap (sum over dimensions)
            # High Qi = workspaces cooperate; Low Qi = workspaces conflict
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

        # P1.1: Meta-cord self-reference buffer (last 4 meta-cord outputs)
        self.register_buffer('meta_history', torch.zeros(1, 4, D))
        # Meta-cord receives 8 timesteps (4 workspace aspects + 4 history)
        # SlimSpecialist IIR hardcodes 4 taps, so we project 8 -> 4
        self.meta_time_proj = nn.Linear(8, 4)

        # GWT workspace broadcast: consensus representation → specialist re-weighting
        self.workspace_broadcast = nn.Sequential(
            nn.Linear(D, 128),
            nn.ReLU(),
            nn.Linear(128, n_specialists),
        )

        # Breath: dual-heart oscillator
        self.breath = Breath()

        # Neuroplasticizer state
        self.pulse_active = False
        self.pulse_batch_count = 0
        self.pulse_duration = 50
        self.pulse_cooldown = 100
        self._batches_since_pulse = self.pulse_cooldown
        self._yin_dose = 0.0
        self._entropy_dose = 0.0
        self.register_buffer('rigidity_harmony_hist', torch.zeros(20))
        self.register_buffer('rigidity_qi_hist', torch.zeros(20))
        self.register_buffer('rigidity_surprise_hist', torch.zeros(20))
        self._rigidity_idx = 0

    def reset_workspace(self, batch_size=1, reset_energy=False):
        super().reset_workspace(batch_size, reset_energy=reset_energy)
        # Qi-fluid persists across batches (awareness accumulates).
        # Only resize when batch size changes; zero-pad new slots.
        if self.use_qi:
            buf = self.qi_fluid
            if buf.shape[0] < batch_size:
                new = torch.zeros(batch_size, self.D, device=buf.device)
                new[:buf.shape[0]] = buf
                self.qi_fluid = new
            elif buf.shape[0] > batch_size:
                self.qi_fluid = buf[:batch_size]
        # Reset breath phases on workspace reset (new episode)
        self.breath.reset()
        self.pulse_active = False
        self.pulse_batch_count = 0
        self._batches_since_pulse = self.pulse_cooldown
        # P1.1: Resize meta-history buffer when batch size changes
        if self.meta_history.shape[0] < batch_size:
            new = torch.zeros(batch_size, 4, self.D, device=self.meta_history.device)
            new[:self.meta_history.shape[0]] = self.meta_history
            self.meta_history = new
        elif self.meta_history.shape[0] > batch_size:
            self.meta_history = self.meta_history[:batch_size]

    def compute_harmony(self, all_f_stack):
        """Compute pairwise harmony and per-specialist scores.

        all_f_stack: [N, B, D]
        Returns:
          harmony_matrix: [N, N, B] pairwise cosine similarities
          harmony_score:  [N, B] per-specialist mean agreement
        """
        N, B, D = all_f_stack.shape
        f_norm = F.normalize(all_f_stack, dim=-1)
        sim = torch.einsum('nbd,mbd->nmb', f_norm, f_norm)
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

    def _get_neuro_modulation(self, qi_energy_mean=None, overall_harmony_mean=None):
        """Return neuroplasticizer modulation signals for the optimizer.

        Adapts HoneybeeBrain's proven optimizer-modulation pattern to
        HarmonyBrain's richer multi-signal rigidity detection.
        """
        modulation = {
            'lr_scale': 1.0,
            'theta_shift': 0.0,
            'reset_state': False,
        }

        # On pulse onset: reset momentum and boost LR
        if self.pulse_active and self.pulse_batch_count == 1:
            modulation['reset_state'] = True
            modulation['lr_scale'] = 2.0
            modulation['theta_shift'] = 0.3

        # During sustained high Qi/harmony without pulse, gently reduce LR
        if not self.pulse_active:
            arousal = 0.0
            if qi_energy_mean is not None:
                arousal = max(arousal, qi_energy_mean.item())
            if overall_harmony_mean is not None:
                arousal = max(arousal, overall_harmony_mean.item())
            if arousal > 5.0:
                modulation['lr_scale'] = 0.8

        return modulation

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
            self.meta_history = self.meta_history.to(device)

        # Breath device sync
        self.breath.t_yang = self.breath.t_yang.to(device)
        self.breath.t_yin = self.breath.t_yin.to(device)

        # State buffers are persistent workspace state, not graph nodes.
        # Detach them at the start of each forward to prevent cross-batch
        # gradient accumulation and in-place corruption after optimizer steps.
        self.workspace_fwd = self.workspace_fwd.detach()
        self.workspace_rev = self.workspace_rev.detach()
        self.field_history = self.field_history.detach()
        if self.use_qi:
            self.qi_fluid = self.qi_fluid.detach()
        self.meta_history = self.meta_history.detach()

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
        if use_memory and self.berry_memory._n_filled > 0:
            all_f_spine = self.spine.compute_all_f(trajectories['psi'])
            boundary_res = self.compute_boundary_residual(
                all_f_spine.unsqueeze(0)
            )
            berry_key = self.compute_berry_key(trajectories, boundary_res)
            with torch.no_grad():
                retrieved, attn = self.berry_memory.query(berry_key, temperature=0.1)
                retrieved = retrieved.detach()
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
            # Clamp the learned scale at use-time to prevent collapse,
            # without in-place mutation that breaks autograd.
            # Clone first so the pulse's later copy_() doesn't invalidate graph nodes.
            temp_scale = self.harmony_temp_scale.clone().clamp(0.0, 2.0)
            temperature = PHI * (1.0 + temp_scale * (1.0 - overall_harmony))
            # Clamp to avoid -inf * 0 = NaN in sparse masking
            temperature = temperature.clamp(min=1e-6)
        else:
            harmony_gate = torch.ones_like(harmony_score)
            temperature = PHI

        # === SPARSE ATTENTION ===
        amplitudes = all_f_stack.norm(dim=-1)  # [N, B]
        # Normalize amplitudes per sample so specialist competition is driven by
        # energy/harmony dynamics, not inherent output-scale differences.
        amplitudes = amplitudes / (amplitudes.mean(dim=0, keepdim=True) + 1e-8)
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
            contributions = (weights * sparse_mask).mean(dim=1)
        else:
            weights = F.softmax(combined_score * temperature, dim=0)
            contributions = weights.mean(dim=1)
            k_eff = None
            sparse_mask = None

        self.specialist_energy = PHI_INV * specialist_energy_old + (1 - PHI_INV) * (1.0 - contributions)
        self.specialist_energy = torch.clamp(self.specialist_energy, 0.3, 2.0)

        # === FUSION ===
        if self.use_gating:
            gated_features = all_f_stack * harmony_gate.unsqueeze(-1)
        else:
            gated_features = all_f_stack
        all_f_workspace = torch.einsum('nb,nbd->bd', weights, gated_features)

        # === GWT WORKSPACE BROADCAST ===
        # The workspace consensus is broadcast back to specialists,
        # refining which specialists get to contribute (GWT "broadcast to all").
        workspace_consensus = all_f_workspace.detach()  # [B, D]
        broadcast_bias = torch.tanh(self.workspace_broadcast(workspace_consensus)).T  # [N, B]
        refined_weights = weights * (1.0 + 0.05 * broadcast_bias)
        refined_weights = refined_weights / (refined_weights.sum(dim=0, keepdim=True) + 1e-8)
        all_f_workspace = torch.einsum('nb,nbd->bd', refined_weights, gated_features)

        field_last = self.field_history[:, -1, :]
        repr_workspace = self.spine.fusion(
            torch.cat([field_last, all_f_workspace * 0.5], -1)
        ) + field_last

        # === QI-FLUID: old Qi gates incoming representation ===
        qi_fluid_old = self.qi_fluid.detach() if self.use_qi else None
        if self.use_qi:
            # High Qi fluid = workspaces cooperating → allow more new info in
            # Low Qi fluid = workspaces in conflict → preserve old state
            attention = self.harmony_gate_qi(qi_fluid_old)
            repr_workspace = attention * repr_workspace + (1 - attention) * field_last

        # === BREATH ===
        # Advance dual-heart oscillators
        breath = self.breath.step()
        phi_breath = PHI + 0.15 * breath['yang']
        phi_inv_breath = 1.0 / phi_breath

        # === DUAL WORKSPACE (with breathing φ) ===
        # Yang inhales → workspace expands
        self.workspace_fwd = phi_inv_breath**2 * self.workspace_fwd + phi_inv_breath * (1.0 + 0.1 * breath['yang']) * repr_workspace
        # Yin exhales → workspace contracts (at Yin rhythm, slower by φ)
        self.workspace_rev = phi_inv_breath * self.workspace_rev + phi_inv_breath**2 * (1.0 + 0.1 * breath['yin']) * self.workspace_fwd
        # Consciousness: harmonious cooperation of Yang and Yin, not conflict
        conscious = phi_inv_breath * self.workspace_fwd + phi_inv_breath**2 * self.workspace_rev

        # Surprise = conscious norm (needed by neuroplasticizer, compute early)
        surprise = conscious.norm(dim=-1).mean()

        # === META-CORD (workspace observer with self-reference, P1.1) ===
        workspace_history = torch.stack([
            self.workspace_fwd, self.workspace_rev, conscious, field_last,
        ], dim=1)  # [B, 4, D]

        # Concatenate workspace observation with meta-cord's own history
        self_referential_input = torch.cat([
            workspace_history,
            self.meta_history[:B],  # [B, 4, D]
        ], dim=1)  # [B, 8, D]

        # Project 8 timesteps -> 4 taps so IIR can process full input
        meta_input_proj = self.meta_time_proj(
            self_referential_input.transpose(1, 2)
        ).transpose(1, 2)  # [B, 4, D]
        meta_repr = self.meta_cord.compute_all_f(meta_input_proj, self.spine.chakra_gain)

        # Update meta-cord history (rolling buffer)
        # Normalize before storing to prevent runaway magnitude accumulation
        self.meta_history = torch.cat([
            self.meta_history[:, 1:, :],
            F.normalize(meta_repr, dim=-1).unsqueeze(1)
        ], dim=1)

        meta_fused = self.spine.fusion(
            torch.cat([workspace_history[:, -1, :], meta_repr * 0.5], -1)
        ) + workspace_history[:, -1, :]
        self.workspace_fwd = self.workspace_fwd + phi_inv_breath**3 * meta_fused

        # === NEUROPLASTICIZER: detect stagnation and pulse ===
        self._batches_since_pulse += 1
        if not self.pulse_active and self._batches_since_pulse >= self.pulse_cooldown:
            # Update rigidity history
            idx = self._rigidity_idx % 20
            self.rigidity_harmony_hist[idx] = harmony_scalar.detach()
            self.rigidity_qi_hist[idx] = (qi_fluid_old.sum(dim=-1).mean() if qi_fluid_old is not None else torch.tensor(0.0))
            self.rigidity_surprise_hist[idx] = surprise.detach() if isinstance(surprise, torch.Tensor) else torch.tensor(float(surprise))
            self._rigidity_idx += 1

            if self._rigidity_idx >= 20:
                rigidity = 1.0 / (1.0 + self.rigidity_harmony_hist.std() + self.rigidity_qi_hist.std() + self.rigidity_surprise_hist.std())
                if rigidity.item() > 0.6:
                    self.pulse_active = True
                    self.pulse_batch_count = 0
                    self._batches_since_pulse = 0
                    dose = 0.3 * rigidity.item()
                    self._yin_dose = dose
                    self._entropy_dose = 2.0 * dose
                    # Gasp: reset breath phases
                    self.breath.reset()
                    # Yin shock: push Yin toward Yang
                    with torch.no_grad():
                        shock = dose * F.normalize(self.workspace_fwd, dim=-1) * self.workspace_rev.norm(dim=-1, keepdim=True)
                        self.workspace_rev = self.workspace_rev + shock
                    # Entropy surge: reset specialist fatigue
                    self.specialist_energy = torch.ones_like(self.specialist_energy)
                    # Boost temperature (pulse sets scale high; clamped at use-time)
                    if hasattr(self, 'harmony_temp_scale'):
                        with torch.no_grad():
                            self.harmony_temp_scale.copy_(torch.tensor(2.0, device=self.harmony_temp_scale.device))

        # Apply pulse decay
        if self.pulse_active:
            self.pulse_batch_count += 1
            progress = self.pulse_batch_count / self.pulse_duration
            if self.pulse_batch_count >= self.pulse_duration:
                self.pulse_active = False
                # Cooldown: gradual return to normal temperature
                if hasattr(self, 'harmony_temp_scale'):
                    with torch.no_grad():
                        self.harmony_temp_scale.copy_(torch.tensor(0.5, device=self.harmony_temp_scale.device))

        # === QI UPDATE: resonant field ===
        if self.use_qi:
            # Qi = overlap + beat resonance
            qi_overlap = self.workspace_fwd * self.workspace_rev  # [B, D]
            # Beat creates natural oscillation in Qi accumulation
            qi_resonance = breath['beat'] * qi_overlap * 0.1
            qi_damping = phi_inv_breath * qi_fluid_old
            self.qi_fluid = qi_damping + phi_inv_breath**2 * qi_overlap + qi_resonance

            # Qi energy = total overlap (positive = harmony, negative = conflict)
            qi_energy = self.qi_fluid.sum(dim=-1, keepdim=True)  # [B, 1]

        # === φ-BALANCE REGULARIZATION (only when stable) ===
        phi_balance_loss = torch.tensor(0.0, device=device)
        qi_energy_bonus = torch.tensor(0.0, device=device)
        if self.use_qi and not self.pulse_active:
            # Frequency ratio should trend toward φ
            # Use clamped frequencies from breath.step() to prevent vanishing gradients
            w_y = breath.get('w_yang', torch.sigmoid(self.breath.omega_yang))
            w_i = breath.get('w_yin', torch.sigmoid(self.breath.omega_yin))
            breath_freq_ratio = w_y / (w_i + 1e-8)
            phi_balance_loss = 0.005 * (torch.log(breath_freq_ratio + 1e-8) - math.log(PHI)).abs()
            # Qi energy should be positive
            qi_energy_bonus = -0.001 * torch.tanh(qi_energy / 100.0).mean()

        # === READOUT ===
        if self.use_qi:
            # High Qi energy = confident readout (workspaces agree)
            # Low/negative Qi energy = uncertain readout (workspaces disagree)
            qi_readout_gate = torch.sigmoid(qi_energy)
            residual = self.readout(conscious)
            pred_enhanced = pred_spine + qi_readout_gate * residual
        else:
            residual = self.readout(conscious)
            pred_enhanced = pred_spine + residual

        # === MEMORY ENCODING ===
        if not hasattr(self, '_surprise_ema_buf'):
            self.register_buffer('_surprise_ema_buf', torch.tensor(0.0))
        if self._surprise_ema_buf.device != conscious.device:
            self._surprise_ema_buf = self._surprise_ema_buf.to(conscious.device)
        with torch.no_grad():
            self._surprise_ema_buf.mul_(0.95).add_(0.05 * surprise.detach())

        if use_memory and self._surprise_ema_buf.item() > 0.3:
            if all_f_spine is None:
                all_f_spine = self.spine.compute_all_f(trajectories['psi'])
            if boundary_res is None:
                boundary_res = self.compute_boundary_residual(all_f_spine.unsqueeze(0))
            berry_key = self.compute_berry_key(trajectories, boundary_res, conscious=conscious)
            workspace_summary = self.workspace_fwd.view(B, self.spine.C, -1).mean(dim=-1)
            conscious_summary = conscious.view(B, self.spine.C, -1).mean(dim=-1)
            value = torch.cat([workspace_summary, boundary_res, conscious_summary], dim=1)
            # Write is a state update — keep it out of the autograd graph
            with torch.no_grad():
                self.berry_memory.write(berry_key.detach(), value.detach(), mode='ema')

        neuro_modulation = self._get_neuro_modulation(
            qi_energy_mean=qi_energy.mean() if self.use_qi else None,
            overall_harmony_mean=overall_harmony.mean(),
        )

        info = {
            'pred_spine': pred_spine,
            'conscious': conscious,
            'workspace_fwd': self.workspace_fwd,
            'workspace_rev': self.workspace_rev,
            'weights': weights,
            'energy': self.specialist_energy.detach(),
            'surprise': surprise,
            'harmony': harmony_score.detach(),
            'harmony_matrix': self.harmony_state.clone(),
            'mean_harmony': overall_harmony.detach(),
            'changepoint': False,
            'neuro_modulation': neuro_modulation,
        }
        if self.use_gating:
            info['harmony_gate'] = harmony_gate.detach()
        if self.use_qi:
            info['qi_fluid'] = self.qi_fluid.clone()
            info['qi_energy'] = qi_energy.detach()
            info['qi_readout_gate'] = qi_readout_gate.detach()
            info['phi_balance_loss'] = phi_balance_loss.detach()
            info['qi_energy_bonus'] = qi_energy_bonus.detach()
            # Breath metrics
            with torch.no_grad():
                info['breath_yang'] = breath['yang']
                info['breath_yin'] = breath['yin']
                info['beat'] = breath['beat']
                info['flow'] = breath['flow']
                info['phase_diff'] = breath['phase_diff']
                info['freq_ratio'] = breath['freq_ratio']
                info['pulse_active'] = float(self.pulse_active)
                yang_norm = self.workspace_fwd.norm(dim=-1)
                yin_norm = self.workspace_rev.norm(dim=-1)
                ratio = yang_norm / (yin_norm + 1e-8)
                qi_sign = (qi_energy.squeeze(-1) > 0).float()
                info['qi_yang_norm'] = yang_norm
                info['qi_yin_norm'] = yin_norm
                info['qi_ratio'] = ratio
                info['qi_sign'] = qi_sign
        if self.use_sparse:
            info['sparse_mask'] = sparse_mask.detach()
            info['k_eff'] = k_eff.detach()
        if use_memory and self.berry_memory._n_filled > 0:
            info['memory_attn'] = attn.detach()

        if return_workspace:
            return pred_enhanced, info
        return pred_enhanced
