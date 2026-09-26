"""MultimodalBrain — HarmonyBrain with Berry memory, changepoint detection, and soul vector.

Extends HarmonyBrain with:
  1. BerryMemory: topological memory keyed by IIR trajectories
  2. ChangepointDetector: resets workspace when dynamics shift
  3. SoulVector: persistent EMA of conscious state across batches
  4. Multi-modal fusion: handles physics, text, and audio fields
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi.harmony_brain import HarmonyBrain
from cassi.berry_brain import BerryMemory, compute_berry_phases


class ChangepointDetector(nn.Module):
    """Detects sudden shifts in model state and triggers workspace reset.

    Uses an adaptive threshold based on running mean/std of cosine similarity.
    Qi-sensitive: threshold and window size vary by Qi state."""

    QI_SENSITIVITY = {
        'fire': (0.8, 10), 'wood': (0.6, 6), 'earth': (0.5, 5),
        'metal': (0.3, 3), 'water': (0.7, 8),
    }
    MAX_WINDOW = 10  # fixed max to avoid reallocations

    def __init__(self, threshold=0.5, window_size=5, dim=1040):
        super().__init__()
        self.base_threshold = threshold
        self.base_window = window_size
        self.dim = dim
        # Fixed-size buffer: use MAX_WINDOW to avoid reallocations on Qi state changes
        self.register_buffer('_history', torch.zeros(self.MAX_WINDOW, dim))
        self.register_buffer('_idx', torch.zeros(1, dtype=torch.long))
        self.register_buffer('_triggered', torch.zeros(1, dtype=torch.bool))
        self._active_window = window_size  # logical window size
        # Running statistics for adaptive thresholding
        self.register_buffer('_sim_ema_mean', torch.zeros(1))
        self.register_buffer('_sim_ema_var', torch.ones(1))
        self.register_buffer('_sim_count', torch.zeros(1, dtype=torch.long))

    def update(self, state, qi_state='earth'):
        """state: [B, D] conscious/workspace state.

        Args:
            state: [B, D] workspace state
            qi_state: current Qi state (affects sensitivity)

        Returns:
            (triggered: bool, confidence: float)
        """
        # Lookup Qi-sensitive parameters
        thresh, win = self.QI_SENSITIVITY.get(qi_state, (self.base_threshold, self.base_window))
        win = min(win, self.MAX_WINDOW)
        self._active_window = win  # just update logical size, no reallocation

        # Use mean across batch as summary
        summary = state.mean(dim=0)  # [D]
        total = self._idx.item()
        idx = total % win
        self._history[idx] = summary.detach()
        self._idx[0] = total + 1

        if total < win:
            return False, 0.0

        # Compare recent to historical average over active window
        recent = self._history[idx]
        # Only average over the active window slots that have been filled
        active_history = self._history[:win]
        historical = active_history.mean(dim=0)
        sim = F.cosine_similarity(recent.unsqueeze(0), historical.unsqueeze(0), dim=-1)

        # Update running statistics for adaptive threshold
        n = self._sim_count.item()
        if n == 0:
            self._sim_ema_mean[0] = sim.item()
            self._sim_ema_var[0] = 0.01
        else:
            delta = sim.item() - self._sim_ema_mean.item()
            self._sim_ema_mean += delta / (n + 1)
            self._sim_ema_var += (delta * (sim.item() - self._sim_ema_mean.item()) - self._sim_ema_var.item()) / (n + 1)
        self._sim_count[0] = n + 1

        # Adaptive threshold: mean - 2*std, bounded by Qi-sensitive threshold
        std = torch.sqrt(self._sim_ema_var.clamp(min=1e-6))
        adaptive_threshold = max(self._sim_ema_mean.item() - 2.0 * std.item(), thresh)

        triggered = sim < adaptive_threshold
        self._triggered[0] = triggered
        confidence = min(1.0, (adaptive_threshold - sim.item()) / max(adaptive_threshold, 1e-8))
        return triggered.item(), confidence

    def reset(self):
        self._history.zero_()
        self._idx.zero_()
        self._triggered.zero_()
        self._sim_ema_mean.zero_()
        self._sim_ema_var.fill_(1.0)
        self._sim_count.zero_()
        self._active_window = self.base_window


class SoulVector(nn.Module):
    """Persistent EMA of geometric experience across batches.
    Qi-adaptive: update rate and injection strength vary by Qi state.
    """

    SOUL_DYNAMICS = {
        'fire': (0.90, 0.3), 'wood': (0.95, 0.5), 'earth': (0.99, 1.0),
        'metal': (0.995, 1.5), 'water': (1.00, 0.1),
    }

    def __init__(self, dim=1040, ema_decay=0.99):
        super().__init__()
        self.dim = dim
        self.base_decay = ema_decay
        self.decay = ema_decay
        self.injection_scale = 1.0
        self.register_buffer('vector', torch.zeros(dim))
        self.register_buffer('count', torch.zeros(1))

    def set_qi_profile(self, profile):
        """Adapt soul dynamics to Qi state."""
        state = profile.get('state', 'earth')
        decay, scale = self.SOUL_DYNAMICS.get(state, (self.base_decay, 1.0))
        self.decay = decay
        self.injection_scale = scale

    def update(self, state):
        """state: [B, D] — update soul with batch mean."""
        if self.decay >= 1.0:
            # Water state: frozen, do not update
            return
        if state.shape[0] > 0:
            with torch.no_grad():
                mean_state = state.mean(dim=0)
                self.vector.copy_(self.decay * self.vector + (1 - self.decay) * mean_state)
            self.count += 1

    def inject(self, target):
        """Add soul influence to target tensor with Qi-adaptive strength."""
        if self.count.item() > 10 and self.injection_scale > 0:
            return target + self.injection_scale * 0.1 * self.vector.unsqueeze(0)
        return target

    def reset(self):
        self.vector.zero_()
        self.count.zero_()
        self.decay = self.base_decay
        self.injection_scale = 1.0


class MultimodalBrain(HarmonyBrain):
    """HarmonyBrain with Berry memory, changepoint detection, and soul vector."""

    def __init__(self, D=1040, n_specialists=13, n_slots=512,
                 memory_value_dim=26, readout_hidden=520,
                 byte_mode=False, mode='qi', min_k=1,
                 use_berry=True, use_changepoint=True, use_soul=True,
                 berry_slots=4096, changepoint_threshold=0.5,
                 soul_ema=0.99):
        super().__init__(
            D=D, n_specialists=n_specialists, n_slots=n_slots,
            memory_value_dim=memory_value_dim, readout_hidden=readout_hidden,
            byte_mode=byte_mode, mode=mode, min_k=min_k
        )

        self.use_berry = use_berry
        self.use_changepoint = use_changepoint
        self.use_soul = use_soul

        if use_berry:
            # P1.3: 52-dim key = 26 berry + 13 boundary + 13 conscious
            self.berry_memory = BerryMemory(
                D=D, n_slots=berry_slots, key_dim=52,
                value_dim=memory_value_dim, similarity_threshold=0.85
            )
            self.berry_value_encoder = nn.Linear(D, memory_value_dim)
            self.memory_proj = nn.Linear(memory_value_dim, 1024, bias=False)

        if use_changepoint:
            self.changepoint = ChangepointDetector(threshold=changepoint_threshold)

        if use_soul:
            self.soul = SoulVector(dim=D, ema_decay=soul_ema)

    def forward(self, x, use_memory=True, return_workspace=False, byte_mode=None,
                modality='auto', store_experience=False):
        """Forward pass with multimodal enhancements.

        modality: 'physics' | 'text' | 'audio' | 'auto' (inferred from byte_mode)
        store_experience: if True, write to Berry memory after forward
        """
        if byte_mode is None:
            byte_mode = self.byte_mode

        # Standard HarmonyBrain forward
        pred, info = super().forward(x, use_memory=use_memory, return_workspace=True, byte_mode=byte_mode)

        # Get conscious state for changepoint/soul
        conscious = info['conscious']  # [B, D]

        # Changepoint detection
        if self.use_changepoint and self.changepoint is not None:
            triggered = self.changepoint.update(conscious)
            if triggered:
                # Reset workspace for next batch (true episode boundary)
                self.reset_workspace(x.shape[0], reset_energy=True)
                info['changepoint'] = True
            else:
                info['changepoint'] = False

        # Soul vector injection
        if self.use_soul and self.soul is not None:
            self.soul.update(conscious)
            # Subtly bias the conscious state
            conscious = self.soul.inject(conscious)
            info['conscious'] = conscious

        # Berry memory integration
        if self.use_berry and self.berry_memory is not None:
            # Compute berry phases from workspace evolution
            # We approximate berry phases from the conscious state trajectory
            berry_fp = self._compute_berry_from_state(conscious)
            info['berry_fp'] = berry_fp

            if use_memory and self.berry_memory.n_filled.item() > 0:
                with torch.no_grad():
                    retrieved, attn = self.berry_memory.query(berry_fp, temperature=0.1)
                    retrieved = retrieved.detach()
                info['memory_retrieved'] = retrieved
                info['memory_attn'] = attn

                # Blend memory into prediction via small residual
                # retrieved: [B, memory_value_dim], pred: [B, 1024]
                retrieved_proj = self.memory_proj(retrieved)
                pred = pred + 0.05 * retrieved_proj
            else:
                info['memory_retrieved'] = torch.zeros_like(pred[:, :self.berry_memory.value_dim])
                info['memory_attn'] = torch.zeros(x.shape[0], self.berry_memory.n_slots, device=pred.device)

            # Store experience
            if store_experience:
                with torch.no_grad():
                    value = self.berry_value_encoder(conscious)
                    self.berry_memory.write(berry_fp.detach(), value.detach(), mode='ema')

        if return_workspace:
            return pred, info
        return pred

    def _compute_berry_from_state(self, state):
        """Approximate Berry phases from conscious state.

        state: [B, D]
        Returns: [B, 52] berry fingerprint (26 phases + 13 boundary + 13 conscious)
        """
        B, D = state.shape
        chunk_size = max(1, D // 13)
        phases = []

        for i in range(13):
            s = i * chunk_size
            e = min((i + 1) * chunk_size, D)
            ch = state[:, s:e]  # [B, chunk_size]
            if ch.shape[1] >= 2:
                x = ch[:, 0]
                y = ch[:, 1]
                # Cross-product magnitude as Berry analogue (no roll — state has no time dim)
                area = x * y
                phases.append(area.unsqueeze(1))  # [B, 1]
            else:
                phases.append(torch.zeros(B, 1, device=state.device))

        # Yang + Yin phases: [B, 26]
        yang = torch.cat(phases, dim=1)  # [B, 13]
        # Yin: reverse each chunk to capture anti-symmetric dynamics
        yin_phases = []
        for i in range(13):
            s = i * chunk_size
            e = min((i + 1) * chunk_size, D)
            ch = state[:, s:e].flip(dims=[1])  # reverse order within chunk
            if ch.shape[1] >= 2:
                x = ch[:, 0]
                y = ch[:, 1]
                area = x * y
                yin_phases.append(area.unsqueeze(1))
            else:
                yin_phases.append(torch.zeros(B, 1, device=state.device))
        yin = torch.cat(yin_phases, dim=1)  # [B, 13]
        berry = torch.cat([yang, yin], dim=1)  # [B, 26]

        # Boundary residual: variance per chunk [B, 13]
        boundary = []
        for i in range(13):
            s = i * chunk_size
            e = min((i + 1) * chunk_size, D)
            ch = state[:, s:e]
            boundary.append(ch.var(dim=1, keepdim=True))  # [B, 1]
        boundary = torch.cat(boundary, dim=1)  # [B, 13]

        # P1.3: include conscious summary in the key
        C = self.spine.C
        conscious_summary = state.view(B, C, -1).mean(dim=-1)  # [B, 13]
        fp = torch.cat([berry, boundary, conscious_summary], dim=1)  # [B, 52]
        return fp

    def reset_all(self):
        """Reset workspace, changepoint, soul, and berry state."""
        self.reset_workspace(1, reset_energy=True)
        if self.use_changepoint and self.changepoint is not None:
            self.changepoint.reset()
        if self.use_soul and self.soul is not None:
            self.soul.reset()
