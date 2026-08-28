"""HoneybeeBrain — Competitive sparse workspace inspired by mushroom body architecture.

Key innovations over HarmonyBrain:
  - Workspace: small (W=256), sparse (10% active), competitive (k-WTA)
  - Per-specialist projections: each specialist maps to its own workspace region
  - Conscious: expansive broadcast from sparse workspace (W → D)
  - Qi: entropy of workspace competition (cognitive arousal)
  - Meta-cord: predicts next workspace winners (foresight)
  - Berry memory: keys = workspace winner patterns (thoughts, not observations)
  - Soul: EMA of workspace winner distributions (personality)
  - Breath: controls workspace capacity (metronome of cognition)
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi.phi_garden import PhiGardenBrain
from cassi.cord import PHI, PHI_INV
from cassi.breath import Breath


class HoneybeeBrain(PhiGardenBrain):
    """Competitive sparse workspace brain.

    Args:
        D: full field dimension (broadcast / conscious / prediction)
        W: workspace dimension (compact integration hub)
        sparsity: fraction of workspace slots active (default 0.10)
        n_specialists: number of specialist chakras
    """

    def __init__(self, D=16384, W=256, n_specialists=13, n_slots=512,
                 memory_value_dim=39, readout_hidden=520, byte_mode=False,
                 sparsity=0.10, min_k=1):
        nn.Module.__init__(self)
        self.D = D
        self.W = W
        self.sparsity = sparsity
        self.k_active = max(1, int(W * sparsity))
        self.N = n_specialists
        self.byte_mode = byte_mode
        self.min_k = min_k

        from cassi.cord import CordPhysics
        self.spine = CordPhysics(D=D, byte_mode=byte_mode)

        self.region_size = W // n_specialists
        self.projections = nn.ModuleList([
            nn.Linear(D, self.region_size) for _ in range(n_specialists)
        ])

        self.workspace_broadcast = nn.Sequential(
            nn.Linear(W, D // 2),
            nn.ReLU(),
            nn.Linear(D // 2, D),
        )

        self.readout = nn.Sequential(
            nn.Linear(D, readout_hidden),
            nn.ReLU(),
            nn.Linear(readout_hidden, 1024),
        )

        self.register_buffer('qi_arousal', torch.zeros(1))

        self.meta_oracle = nn.Sequential(
            nn.Linear(W + 3, W // 2),
            nn.ReLU(),
            nn.Linear(W // 2, W),
        )

        self.breath = Breath()
        self.register_buffer('specialist_energy', torch.ones(n_specialists))
        self.register_buffer('field_history', torch.zeros(1, 4, D))
        self.register_buffer('workspace', torch.zeros(1, W))
        self.register_buffer('slot_energy', torch.ones(1, W))
        self.register_buffer('soul', torch.zeros(W))

        from cassi.berry_brain import BerryMemory
        self.berry_memory = BerryMemory(
            key_dim=W,
            value_dim=memory_value_dim,
            n_slots=n_slots,
        )
        self.memory_decompressor = nn.Linear(memory_value_dim, D)

        self.pulse_active = False
        self.pulse_batch_count = 0
        self.pulse_duration = 50
        self.pulse_cooldown = 100
        self._batches_since_pulse = self.pulse_cooldown
        self.register_buffer('rigidity_hist', torch.zeros(20))
        self._rigidity_idx = 0

        self.register_buffer('_surprise_ema_buf', torch.zeros(1))

    def load_spine(self, checkpoint_path: str):
        """Load spine from checkpoint."""
        state = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
        if isinstance(state, dict) and 'model' in state:
            state = state['model']
        if any(k.startswith('_orig_mod.') for k in state.keys()):
            state = {k.replace('_orig_mod.', ''): v for k, v in state.items()}
        spine_keys = [k for k in state.keys() if k.startswith('spine.')]
        if spine_keys:
            state = {k.replace('spine.', ''): v for k, v in state.items() if k.startswith('spine.')}
        try:
            missing, unexpected = self.spine.load_state_dict(state, strict=False)
            if missing and not all(k.startswith('byte_encoder') for k in missing):
                print(f"[HoneybeeBrain.load_spine] Warning: unexpected missing keys: {missing}")
            if unexpected:
                print(f"[HoneybeeBrain.load_spine] Warning: unexpected keys: {unexpected}")
        except RuntimeError as e:
            # PyTorch 2.x raises on size mismatch even with strict=False
            print(f"[HoneybeeBrain.load_spine] Skipped mismatched spine weights (D mismatch expected): {e}")

    def reset_workspace(self, batch_size=1, reset_energy=False):
        """Reset workspace for new episode."""
        if self.workspace.shape[0] != batch_size:
            self.workspace = torch.zeros(batch_size, self.W, device=self.workspace.device)
            self.slot_energy = torch.ones(batch_size, self.W, device=self.slot_energy.device)
        else:
            self.workspace.zero_()
            self.slot_energy.fill_(1.0)
        self.field_history = torch.zeros(batch_size, 4, self.D, device=self.field_history.device)
        self.qi_arousal.zero_()
        self.soul.zero_()
        self._surprise_ema_buf.zero_()
        if reset_energy:
            self.specialist_energy.fill_(1.0)
        self.breath.reset()
        self.pulse_active = False
        self.pulse_batch_count = 0
        self._batches_since_pulse = self.pulse_cooldown
        self._rigidity_idx = 0
        self.rigidity_hist.zero_()

    def _compute_candidates(self, B, device, trajectories, specialist_energy):
        """Project each specialist to its workspace region and build candidates."""
        all_f_stack = self.spine.compute_all_f_stack(trajectories['psi'])
        candidates = torch.zeros(B, self.W, device=device)
        for c in range(self.N):
            start = c * self.region_size
            end = start + self.region_size
            region = self.projections[c](all_f_stack[c])
            energy = torch.tanh(specialist_energy[c])
            candidates[:, start:end] = energy * region
        return candidates

    def _compete_and_update(self, workspace, slot_energy, candidates, k_dynamic, phi_inv_breath):
        """k-WTA competition: select winners, update workspace and slot energy."""
        topk_vals, topk_idx = candidates.topk(k_dynamic, dim=-1)

        new_workspace = torch.zeros_like(workspace)
        new_workspace.scatter_(1, topk_idx, topk_vals)
        new_workspace = new_workspace * torch.tanh(slot_energy)

        workspace = phi_inv_breath * workspace + phi_inv_breath ** 2 * new_workspace

        active_mask = torch.zeros_like(workspace)
        active_mask.scatter_(1, topk_idx, torch.ones_like(topk_vals))
        slot_energy = PHI_INV * slot_energy + PHI_INV ** 2 * (1.0 - active_mask)
        slot_energy = torch.clamp(slot_energy, 0.1, 2.0)

        return workspace, slot_energy, topk_vals, topk_idx

    def _compute_qi(self, candidates, qi_arousal):
        """Qi = entropy of workspace competition (cognitive arousal)."""
        candidate_probs = F.softmax(candidates, dim=-1)
        qi_entropy = -(candidate_probs * torch.log(candidate_probs + 1e-8)).sum(dim=-1).mean()
        qi_arousal = PHI_INV * qi_arousal + PHI_INV ** 2 * qi_entropy
        return qi_entropy, qi_arousal

    def _compute_meta_cord(self, workspace, breath, qi_arousal, topk_vals, topk_idx, B, k_dynamic):
        """Meta-cord predicts next workspace winners."""
        meta_input = torch.cat([
            workspace,
            breath['beat'].expand(B, 1),
            qi_arousal.expand(B, 1),
            workspace.norm(dim=-1, keepdim=True),
        ], dim=-1)
        winner_probs = self.meta_oracle(meta_input)

        winner_mask = (workspace != 0).float()
        strong_predictions = (torch.tanh(winner_probs).abs() > 0.5).float()
        combined_mask = torch.clamp(winner_mask + strong_predictions, 0, 1)
        workspace = workspace + 0.1 * torch.tanh(winner_probs) * combined_mask

        meta_target = torch.zeros(B, self.W, device=workspace.device)
        meta_target.scatter_(1, topk_idx, torch.ones_like(topk_vals))
        meta_loss = F.binary_cross_entropy_with_logits(
            winner_probs, meta_target, reduction='sum'
        ) / (B * k_dynamic + 1e-8)

        return workspace, meta_loss

    def _update_soul(self, topk_idx, topk_vals, B, device):
        """Slow EMA of workspace winner distributions across full batch."""
        winner_dist = torch.zeros(B, self.W, device=device)
        winner_dist.scatter_(1, topk_idx, torch.ones_like(topk_vals))
        winner_dist = winner_dist.mean(dim=0)
        with torch.no_grad():
            self.soul.mul_(0.99).add_(0.01 * winner_dist)

    def _store_memory(self, B, device, workspace, topk_idx, topk_vals,
                      qi_entropy, surprise, breath, k_dynamic, use_memory):
        """Store workspace winner pattern in berry memory."""
        with torch.no_grad():
            self._surprise_ema_buf.mul_(0.95).add_(0.05 * surprise.detach())

        if not use_memory or self._surprise_ema_buf.item() <= 0.3:
            return

        with torch.no_grad():
            workspace_key = torch.zeros(B, self.W, device=device)
            workspace_key.scatter_(1, topk_idx, torch.ones_like(topk_vals))
            vdim = self.berry_memory.value_dim
            value = torch.zeros(B, vdim, device=device)
            value[:, 0] = workspace.view(B, -1).mean(dim=-1)
            value[:, 1] = qi_entropy
            value[:, 2] = surprise
            value[:, 3] = breath['yang']
            value[:, 4] = breath['yin']
            value[:, 5] = breath['beat']
            value[:, 6] = k_dynamic / self.W
            if vdim > 7:
                ws_compressed = workspace.view(B, -1)[:, :vdim - 7]
                value[:, 7:7 + ws_compressed.shape[1]] = ws_compressed
            self.berry_memory.write(workspace_key, value, mode='ema')

    def _get_neuro_modulation(self, qi_entropy):
        """Return neuroplasticizer modulation signals for the optimizer."""
        # Default: no modulation
        modulation = {
            'lr_scale': 1.0,
            'theta_shift': 0.0,
            'reset_state': False,
        }

        # On pulse onset, reset momentum and boost LR
        if self.pulse_active and self.pulse_batch_count == 1:
            modulation['reset_state'] = True
            modulation['lr_scale'] = 2.0
            modulation['theta_shift'] = 0.3

        # During sustained high arousal, slightly reduce LR (avoid oscillation)
        if self.qi_arousal.item() > 5.0 and not self.pulse_active:
            modulation['lr_scale'] = 0.8

        return modulation

    def _copy_state_to_buffers(self, workspace, slot_energy, qi_arousal):
        """Copy local computation state back to registered buffers."""
        with torch.no_grad():
            if self.workspace.shape == workspace.shape:
                self.workspace.copy_(workspace.detach())
            else:
                self.workspace = workspace.detach()
            if self.slot_energy.shape == slot_energy.shape:
                self.slot_energy.copy_(slot_energy.detach())
            else:
                self.slot_energy = slot_energy.detach()
            if self.qi_arousal.shape == qi_arousal.shape:
                self.qi_arousal.copy_(qi_arousal.detach())
            else:
                self.qi_arousal = qi_arousal.detach()

    def forward(self, x, use_memory=True, return_workspace=False, byte_mode=None, store_experience=True):
        """Forward pass with competitive sparse workspace."""
        if byte_mode is None:
            byte_mode = self.byte_mode

        if byte_mode:
            field = self.spine.byte_encoder.encode_sequence(x, T=4)
        else:
            field = x

        B = field.shape[0]
        device = field.device

        if self.workspace.shape[0] != B:
            self.reset_workspace(B)

        # Local copies with broken view relationship for safe autograd
        workspace = self.workspace.detach().clone()
        slot_energy = self.slot_energy.detach().clone()
        qi_arousal = self.qi_arousal.detach().clone()
        specialist_energy = self.specialist_energy.detach().clone()

        # Breath
        breath = self.breath.step()
        phi_breath = PHI + 0.15 * breath['yang']
        phi_inv_breath = 1.0 / phi_breath
        k_dynamic = max(1, min(int(self.k_active * (0.5 + 0.5 * (1.0 + breath['yang']))), self.W))

        # Spine
        pred_spine, trajectories = self.spine(field, return_trajectories=True, byte_mode=False)
        repr_external = trajectories['repr']

        # Field history
        with torch.no_grad():
            self.field_history.copy_(torch.cat([
                self.field_history[:, 1:, :],
                repr_external.unsqueeze(1)
            ], dim=1))

        # Workspace competition
        candidates = self._compute_candidates(B, device, trajectories, specialist_energy)
        workspace, slot_energy, topk_vals, topk_idx = self._compete_and_update(
            workspace, slot_energy, candidates, k_dynamic, phi_inv_breath
        )

        # Qi
        qi_entropy, qi_arousal = self._compute_qi(candidates, qi_arousal)

        # Meta-cord
        workspace, meta_loss = self._compute_meta_cord(
            workspace, breath, qi_arousal, topk_vals, topk_idx, B, k_dynamic
        )

        # Conscious and prediction
        conscious = self.workspace_broadcast(workspace)
        surprise = conscious.norm(dim=-1).mean()
        residual = self.readout(conscious)
        pred_enhanced = pred_spine + residual

        # Soul
        self._update_soul(topk_idx, topk_vals, B, device)

        # Neuroplasticizer
        self._batches_since_pulse += 1
        if not self.pulse_active and self._batches_since_pulse >= self.pulse_cooldown:
            self.rigidity_hist[self._rigidity_idx % 20] = qi_entropy.detach()
            self._rigidity_idx += 1
            if self._rigidity_idx >= 20:
                rigidity = 1.0 / (1.0 + self.rigidity_hist.std())
                if rigidity.item() > 0.6:
                    self.pulse_active = True
                    self.pulse_batch_count = 0
                    self._batches_since_pulse = 0
                    self.breath.reset()
                    slot_energy = torch.ones_like(slot_energy)

        if self.pulse_active:
            self.pulse_batch_count += 1
            if self.pulse_batch_count >= self.pulse_duration:
                self.pulse_active = False

        # Memory
        self._store_memory(B, device, workspace, topk_idx, topk_vals,
                           qi_entropy, surprise, breath, k_dynamic, use_memory)

        # Copy state back to buffers
        self._copy_state_to_buffers(workspace, slot_energy, qi_arousal)

        # Neuroplasticizer modulation signal for optimizer
        neuro_modulation = self._get_neuro_modulation(qi_entropy)

        info = {
            'pred_spine': pred_spine,
            'conscious': conscious,
            'workspace': workspace,
            'candidates': candidates,
            'winners': topk_idx,
            'winner_strengths': topk_vals,
            'energy': specialist_energy.detach(),
            'surprise': surprise,
            'qi_arousal': qi_arousal.detach(),
            'mean_harmony': qi_arousal.detach(),
            'soul': self.soul.detach(),
            'breath_yang': breath['yang'],
            'breath_yin': breath['yin'],
            'beat': breath['beat'],
            'phase_diff': breath['phase_diff'],
            'freq_ratio': breath['freq_ratio'],
            'pulse_active': float(self.pulse_active),
            'k_active': k_dynamic,
            'changepoint': False,
            'meta_loss': meta_loss.detach(),
            'neuro_modulation': neuro_modulation,
        }

        if return_workspace:
            return pred_enhanced, info
        return pred_enhanced
