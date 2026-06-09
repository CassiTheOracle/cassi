"""CordPhysics — φ-Temporal Chakras v8.1.

Each of the 13 chakras has its own φ-damped IIR with a learned frequency.
Spatial widths are φ-scaled. Temporal frequencies are inversely φ-scaled.

v8.1 adds:
  - _compute_repr(): factored core computation
  - forward_field(): operate directly on D-dimensional field history
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math

from cassi.text_codec import ByteEncoder

PHI = (1 + 5 ** 0.5) / 2
PHI_INV = 1 / PHI


class CordPhysics(nn.Module):
    """Physics cord with per-chakra φ-damped IIRs.

    Input modes:
      - forward(x):     x is [B, 4, 1024] → pred [B, 1024]
      - forward_field(h): h is [B, 4, D]   → repr [B, D]

    Each chakra c has:
      - spatial width  ∝ PHI^c
      - temporal freq  ∝ PHI^{-c}  (via learned theta, phi-spaced init)
      - damping        ρ = 1/PHI   (fixed, prevents mode-locking)
    """
    T_IN = 4

    def __init__(self, D=1040, byte_mode=False):
        super().__init__()
        self.D = D
        self.byte_mode = byte_mode

        # Optional byte encoder for raw byte input
        if byte_mode:
            self.byte_encoder = ByteEncoder(window_bytes=1024, dim_field=1024, T=4)

        # 13 φ-scaled chakra widths (normalized so sum = D)
        raw = [PHI ** c for c in range(13)]
        total_raw = sum(raw)
        self.widths = [max(1, round(D * r / total_raw)) for r in raw]
        self.widths[-1] += D - sum(self.widths)
        self.C = len(self.widths)

        # Input projection
        self.in_proj = nn.Sequential(
            nn.Linear(1024, D),
            nn.LayerNorm(D),
        )

        # Per-chakra gains
        self.chakra_gain = nn.Parameter(torch.zeros(self.C))

        # Per-chakra IIR frequencies (learned, φ-spaced init)
        self.fwd_theta = nn.Parameter(torch.randn(self.C))
        self.rev_theta = nn.Parameter(torch.randn(self.C))

        # Per-chakra IIR gains
        self.fwd_b0 = nn.Parameter(0.1 * torch.randn(self.C))
        self.fwd_b1 = nn.Parameter(-0.5 + 0.1 * torch.randn(self.C))
        self.rev_b0 = nn.Parameter(0.1 * torch.randn(self.C))
        self.rev_b1 = nn.Parameter(-0.5 + 0.1 * torch.randn(self.C))

        # Fusion: psi_last + chakra_diffs → repr
        # CRITICAL: bias=False ensures linearity for IIR aggregation
        self.fusion = nn.Linear(D * 2, D, bias=False)
        self.decoder = nn.Linear(D, 1024)

        # Precompute chakra offsets for fast slicing
        self._offsets = []
        offset = 0
        for w in self.widths:
            self._offsets.append((offset, offset + w))
            offset += w

        # ── Persistent resonant field state (Phase 1) ──
        # IIR state
        self.register_buffer('h1', torch.zeros(1, D))
        self.register_buffer('h2', torch.zeros(1, D))
        self.register_buffer('x1', torch.zeros(1, D))
        # Dual workspace
        self.register_buffer('yang', torch.zeros(1, D))
        self.register_buffer('yin', torch.zeros(1, D))
        self.register_buffer('field_state', torch.zeros(1, D))
        # Energy & Qi
        self.register_buffer('field_energy', torch.zeros(1, self.C))
        self.register_buffer('qi_fluid', torch.zeros(1, D))
        # Fast weights (Phase 2 — disabled in Phase 1)
        self.register_buffer('theta_fast_fwd', torch.zeros(self.C))
        self.register_buffer('theta_fast_rev', torch.zeros(self.C))
        self.register_buffer('gain_fast', torch.zeros(self.C))
        # Internal error/activity filter state (Phase 2)
        self.register_buffer('err_h1', torch.zeros(self.C))
        self.register_buffer('err_h2', torch.zeros(self.C))
        self.register_buffer('act_h1', torch.zeros(self.C))
        self.register_buffer('act_h2', torch.zeros(self.C))

        # Rolling frame buffer for reverse IIR (4 frames)
        self.register_buffer('_frame_buffer', torch.zeros(1, 4, D))
        self._frame_idx = 0

        self._init_theta()

    def _init_theta(self):
        """Initialize theta with inversely φ-spaced frequencies."""
        theta_max = 2.5  # rad/frame for fastest chakra
        for c in range(self.C):
            theta_c = theta_max * (PHI ** (-c))
            y = theta_c / math.pi
            y = max(0.001, min(0.999, y))
            param = math.log(y / (1.0 - y))
            self.fwd_theta.data[c] = param
            self.rev_theta.data[c] = param

    def _iir(self, x, a1, a2, b0, b1, return_trajectory=False):
        """Second-order IIR over 4 time steps.

        x: [B, 4, W] — 4 frames of width W
        a1, a2, b0, b1: scalar params
        Returns: [B, W] or ([B, W], [4, B, W]) if return_trajectory
        """
        h0 = x[:, 0] * b0
        h1 = x[:, 1] * b0 + x[:, 0] * b1 + a1 * h0
        h  = x[:, 2] * b0 + x[:, 1] * b1 + a1 * h1 + a2 * h0
        out = x[:, 3] * b0 + x[:, 2] * b1 + a1 * h + a2 * h1
        if return_trajectory:
            return out, torch.stack([h0, h1, h, out])
        return out

    def _split_chakras(self, psi):
        """Split psi [B, 4, D] into chakra tensors with gains applied."""
        psi_c = []
        offset = 0
        for c in range(self.C):
            w = self.widths[c]
            g = torch.sigmoid(self.chakra_gain[c]) * 2.0
            psi_c.append(psi[:, :, offset:offset + w] * g)
            offset += w
        return psi_c

    def _iir_analytic_predict(self, ch, h, a1, a2, b0, b1):
        """Predict chakra output h steps ahead using analytic IIR resonance.

        Assumes constant input (zero-order hold) = last frame of ch.
        For smooth data this is exact; for discrete data use rollout().

        ch: [B, 4, W_c] — input history for this chakra
        h: int — prediction horizon (h ≥ 1)
        a1, a2, b0, b1: scalar IIR parameters (float or 0-dim tensor)
        Returns: [B, W_c] — predicted output at horizon h
        """
        # Ensure scalar params are tensors on the right device
        device = ch.device
        a1 = torch.tensor(a1, device=device, dtype=ch.dtype) if not isinstance(a1, torch.Tensor) else a1.to(device, ch.dtype)
        a2 = torch.tensor(a2, device=device, dtype=ch.dtype) if not isinstance(a2, torch.Tensor) else a2.to(device, ch.dtype)
        b0 = torch.tensor(b0, device=device, dtype=ch.dtype) if not isinstance(b0, torch.Tensor) else b0.to(device, ch.dtype)
        b1 = torch.tensor(b1, device=device, dtype=ch.dtype) if not isinstance(b1, torch.Tensor) else b1.to(device, ch.dtype)

        # Current IIR state after 4 frames
        h0 = ch[:, 0] * b0
        h1 = ch[:, 1] * b0 + ch[:, 0] * b1 + a1 * h0
        h2 = ch[:, 2] * b0 + ch[:, 1] * b1 + a1 * h1 + a2 * h0
        h3 = ch[:, 3] * b0 + ch[:, 2] * b1 + a1 * h2 + a2 * h1

        # Steady-state for constant input = last frame
        x_const = ch[:, -1]
        sf = b0 + b1 + 1e-8
        h_ss = x_const * sf / (1 - a1 - a2 + 1e-8)

        # Discriminant of characteristic equation r² - a1·r - a2 = 0
        discriminant = a1 * a1 + 4 * a2

        if discriminant.item() < -1e-8:
            # Complex conjugate poles: r = ρ·e^(±iθ)
            rho = torch.sqrt(torch.clamp(-a2, min=1e-8))
            theta = torch.acos(torch.clamp(a1 / (2 * rho + 1e-8), -1.0, 1.0))

            A = h3 - h_ss
            sin_theta = torch.sin(theta)
            B = torch.where(
                sin_theta.abs() > 1e-6,
                (h2 - h_ss - rho * A * torch.cos(theta)) / (rho * sin_theta + 1e-8),
                torch.zeros_like(A)
            )

            # Evaluate at horizon h
            rho_h = rho ** h
            return h_ss + rho_h * (A * torch.cos(h * theta) + B * torch.sin(h * theta))
        else:
            # Real poles: r1, r2 = (a1 ± √D) / 2
            sqrt_d = torch.sqrt(discriminant + 1e-8)
            r1 = (a1 + sqrt_d) / 2
            r2 = (a1 - sqrt_d) / 2

            denom = r1 * r1 - r1 * r2 + 1e-8
            C1 = (h2 - h_ss - r2 * (h3 - h_ss)) / denom
            C2 = (h3 - h_ss - r1 * C1) / (r2 + 1e-8)

            return h_ss + C1 * (r1 ** h) + C2 * (r2 ** h)

    def _compute_repr(self, psi, return_qi=False, return_trajectories=False):
        """Core computation: psi [B, 4, D] → (repr [B, D], extras).

        This is the heart of the cord. It splits psi into chakras,
        applies per-chakra φ-damped IIRs, and fuses the results.

        Returns:
          repr: [B, D]
          qi: [B, D] (if return_qi)
          trajectories: dict (if return_trajectories)
        """
        B = psi.shape[0]

        psi_c = self._split_chakras(psi)

        # Per-chakra IIRs (φ-damped)
        outs = []
        qi_parts = [] if return_qi else None
        traj_fwd = [] if return_trajectories else None
        traj_rev = [] if return_trajectories else None

        for c in range(self.C):
            ch = psi_c[c]  # [B, 4, W_c]

            # Forward IIR
            theta = torch.sigmoid(self.fwd_theta[c]) * math.pi
            a1 = 2.0 * PHI_INV * torch.cos(theta)
            a2 = -(PHI_INV) ** 2
            b0 = torch.sigmoid(self.fwd_b0[c])
            b1 = torch.sigmoid(self.fwd_b1[c])
            sf = b0 + b1 + 1e-8
            b0, b1 = b0 / sf, b1 / sf

            if return_trajectories:
                h_fwd, t_fwd = self._iir(ch, a1, a2, b0, b1, return_trajectory=True)
                traj_fwd.append(t_fwd)
            else:
                h_fwd = self._iir(ch, a1, a2, b0, b1)

            # Reverse IIR
            theta_r = torch.sigmoid(self.rev_theta[c]) * math.pi
            a1r = 2.0 * PHI_INV * torch.cos(theta_r)
            a2r = -(PHI_INV) ** 2
            b0r = torch.sigmoid(self.rev_b0[c])
            b1r = torch.sigmoid(self.rev_b1[c])
            sr = b0r + b1r + 1e-8
            b0r, b1r = b0r / sr, b1r / sr

            if return_trajectories:
                h_rev, t_rev = self._iir(
                    torch.flip(ch, [1]), a1r, a2r, b0r, b1r, return_trajectory=True
                )
                traj_rev.append(t_rev)
            else:
                h_rev = self._iir(torch.flip(ch, [1]), a1r, a2r, b0r, b1r)

            outs.append(h_fwd - h_rev)

            if return_qi:
                diff = (h_fwd - h_rev).abs()
                mag = h_fwd.abs() + h_rev.abs() + 1e-8
                qi_parts.append(1.0 - diff / mag)

        all_f = torch.cat(outs, -1)  # [B, D]
        qi = torch.cat(qi_parts, -1) if return_qi else None  # [B, D]

        # Fusion
        repr_vec = self.fusion(torch.cat([psi[:, -1, :], all_f * 0.5], -1)) + psi[:, -1, :]

        trajectories = None
        if return_trajectories:
            trajectories = {
                'fwd': traj_fwd,
                'rev': traj_rev,
                'psi': psi,
                'repr': repr_vec,
            }

        return repr_vec, qi, trajectories, all_f

    def forward(self, x, byte_mode=None, return_qi=False, return_trajectories=False):
        """Predict next frame from physics input.

        x: [B, 4, 1024] (field mode) or [B, 1024] uint8 (byte mode)
        byte_mode: override self.byte_mode. If True, x is raw bytes.
        Returns:
          - default: [B, 1024]
          - return_qi=True: ([B, 1024], [B, D])
          - return_trajectories=True: ([B, 1024], dict)
          - both: ([B, 1024], [B, D], dict)
        """
        if byte_mode is None:
            byte_mode = self.byte_mode

        if byte_mode:
            field = self.byte_encoder.encode_sequence(x, T=4)  # [B, 4, 1024]
        else:
            field = x

        psi = self.in_proj(field)  # [B, 4, D]
        repr_vec, qi, trajectories, _ = self._compute_repr(
            psi, return_qi=return_qi, return_trajectories=return_trajectories
        )
        pred = field[:, -1, :] + self.decoder(repr_vec)

        if return_qi and return_trajectories:
            return pred, qi, trajectories
        if return_qi:
            return pred, qi
        if return_trajectories:
            return pred, trajectories
        return pred

    def forward_field(self, field_history, return_qi=False, return_trajectories=False):
        """Process field history directly (bypass in_proj).

        field_history: [B, 4, D] — 4 frames of D-dimensional field state
        Returns:
          - default: repr [B, D]
          - return_qi=True: (repr [B, D], qi [B, D])
          - return_trajectories=True: (repr [B, D], dict)
          - both: (repr [B, D], qi [B, D], dict)
        """
        psi = field_history  # bypass in_proj
        repr_vec, qi, trajectories, _ = self._compute_repr(
            psi, return_qi=return_qi, return_trajectories=return_trajectories
        )

        if return_qi and return_trajectories:
            return repr_vec, qi, trajectories
        if return_qi:
            return repr_vec, qi
        if return_trajectories:
            return repr_vec, trajectories
        return repr_vec

    def compute_all_f_stack(self, psi):
        """Compute per-specialist IIR outputs as stacked tensor.

        psi: [B, 4, D]
        Returns: [C, B, D] — each specialist's output padded to D
        """
        psi_c = self._split_chakras(psi)
        outs = []
        for c in range(self.C):
            ch = psi_c[c]
            theta = torch.sigmoid(self.fwd_theta[c]) * math.pi
            a1 = 2.0 * PHI_INV * torch.cos(theta)
            a2 = -(PHI_INV) ** 2
            b0 = torch.sigmoid(self.fwd_b0[c])
            b1 = torch.sigmoid(self.fwd_b1[c])
            sf = b0 + b1 + 1e-8
            b0, b1 = b0 / sf, b1 / sf
            h_fwd = self._iir(ch, a1, a2, b0, b1)
            theta_r = torch.sigmoid(self.rev_theta[c]) * math.pi
            a1r = 2.0 * PHI_INV * torch.cos(theta_r)
            a2r = -(PHI_INV) ** 2
            b0r = torch.sigmoid(self.rev_b0[c])
            b1r = torch.sigmoid(self.rev_b1[c])
            sr = b0r + b1r + 1e-8
            b0r, b1r = b0r / sr, b1r / sr
            h_rev = self._iir(torch.flip(ch, [1]), a1r, a2r, b0r, b1r)
            out = h_fwd - h_rev  # [B, w_c]
            # Pad to D
            if out.shape[-1] < self.D:
                pad = torch.zeros(out.shape[0], self.D - out.shape[-1], device=out.device, dtype=out.dtype)
                out = torch.cat([out, pad], dim=-1)
            outs.append(out)
        return torch.stack(outs, dim=0)  # [C, B, D]

    def compute_all_f(self, psi):
        """Compute only the IIR outputs (all_f) without fusion.

        psi: [B, 4, D]
        Returns: all_f [B, D]

        This is used by specialists in the φ-Garden to aggregate
        IIR outputs before applying shared fusion.
        """
        psi_c = self._split_chakras(psi)

        outs = []
        for c in range(self.C):
            ch = psi_c[c]

            # Forward IIR
            theta = torch.sigmoid(self.fwd_theta[c]) * math.pi
            a1 = 2.0 * PHI_INV * torch.cos(theta)
            a2 = -(PHI_INV) ** 2
            b0 = torch.sigmoid(self.fwd_b0[c])
            b1 = torch.sigmoid(self.fwd_b1[c])
            sf = b0 + b1 + 1e-8
            b0, b1 = b0 / sf, b1 / sf
            h_fwd = self._iir(ch, a1, a2, b0, b1)

            # Reverse IIR
            theta_r = torch.sigmoid(self.rev_theta[c]) * math.pi
            a1r = 2.0 * PHI_INV * torch.cos(theta_r)
            a2r = -(PHI_INV) ** 2
            b0r = torch.sigmoid(self.rev_b0[c])
            b1r = torch.sigmoid(self.rev_b1[c])
            sr = b0r + b1r + 1e-8
            b0r, b1r = b0r / sr, b1r / sr
            h_rev = self._iir(torch.flip(ch, [1]), a1r, a2r, b0r, b1r)

            outs.append(h_fwd - h_rev)

        return torch.cat(outs, -1)  # [B, D]

    # ------------------------------------------------------------------
    # Multi-horizon prediction
    # ------------------------------------------------------------------

    def local_smoothness(self, x):
        """Measure field smoothness: 1.0 = perfectly smooth, ~0 = discontinuous.

        x: [B, T, D] or [B, T, 1024]
        Returns: [B] smoothness scores in [0, 1]
        """
        if x.dim() == 2:
            x = x.unsqueeze(0)
        diffs = torch.abs(x[:, 1:, :] - x[:, :-1, :]).mean(dim=(1, 2))
        return torch.exp(-diffs * 10)

    def forward_multi_horizon(self, x, horizons=[1, 2, 4, 8, 16], byte_mode=None):
        """Predict at multiple horizons using analytic IIR resonance.

        For smooth data, uses analytic extrapolation (fast, O(1) per horizon).
        For discrete data, falls back to iterative rollout.

        x: [B, 4, 1024] (field) or [B, 1024] uint8 (bytes)
        Returns: dict {'t+h': pred [B, 1024], ...}
        """
        if byte_mode is None:
            byte_mode = self.byte_mode

        if byte_mode:
            field = self.byte_encoder.encode_sequence(x, T=4)  # [B, 4, 1024]
        else:
            field = x

        # Decide regime per batch element
        smooth = self.local_smoothness(field)  # [B]

        predictions = {}
        psi = self.in_proj(field)  # [B, 4, D]

        psi_c = self._split_chakras(psi)

        # Precompute IIR params per chakra
        iir_params = []
        for c in range(self.C):
            theta = torch.sigmoid(self.fwd_theta[c]) * math.pi
            a1 = 2.0 * PHI_INV * torch.cos(theta)
            a2 = -(PHI_INV) ** 2
            b0 = torch.sigmoid(self.fwd_b0[c])
            b1 = torch.sigmoid(self.fwd_b1[c])
            sf = b0 + b1 + 1e-8
            b0, b1 = b0 / sf, b1 / sf
            iir_params.append((a1, a2, b0, b1))

        for h in horizons:
            outs = []
            for c in range(self.C):
                ch = psi_c[c]
                a1, a2, b0, b1 = iir_params[c]
                h_pred = self._iir_analytic_predict(ch, h, a1, a2, b0, b1)
                outs.append(h_pred)

            all_f = torch.cat(outs, -1)  # [B, D]
            repr_vec = self.fusion(torch.cat([psi[:, -1, :], all_f * 0.5], -1)) + psi[:, -1, :]
            pred = field[:, -1, :] + self.decoder(repr_vec)
            predictions[f't+{h}'] = pred

        return predictions

    def rollout(self, x, steps, byte_mode=None):
        """Iterative rollout: chain the cord's own predictions.

        x: [B, 4, 1024] or [B, 1024] uint8
        steps: int
        Returns: list of [B, 1024] predictions (length = steps)
        """
        if byte_mode is None:
            byte_mode = self.byte_mode

        if byte_mode:
            field = self.byte_encoder.encode_sequence(x, T=4)
        else:
            field = x

        history = field.clone()
        preds = []
        for _ in range(steps):
            pred = self.forward(history, byte_mode=False)  # already encoded
            preds.append(pred)
            history = torch.cat([history[:, 1:, :], pred.unsqueeze(1)], dim=1)
        return preds

    def predict_far_future(self, x, target_horizon, byte_mode=None):
        """Direct recall: jump to target_horizon in a single evaluation.

        Uses the slowest chakras' natural resonance for long-range prediction.
        Best for smooth data with clear trends.
        """
        if byte_mode is None:
            byte_mode = self.byte_mode

        if byte_mode:
            field = self.byte_encoder.encode_sequence(x, T=4)
        else:
            field = x

        psi = self.in_proj(field)

        psi_c = self._split_chakras(psi)

        # Precompute IIR params per chakra
        iir_params = []
        for c in range(self.C):
            theta = torch.sigmoid(self.fwd_theta[c]) * math.pi
            a1 = 2.0 * PHI_INV * torch.cos(theta)
            a2 = -(PHI_INV) ** 2
            b0 = torch.sigmoid(self.fwd_b0[c])
            b1 = torch.sigmoid(self.fwd_b1[c])
            sf = b0 + b1 + 1e-8
            b0, b1 = b0 / sf, b1 / sf
            iir_params.append((a1, a2, b0, b1))

        outs = []
        for c in range(self.C):
            ch = psi_c[c]
            a1, a2, b0, b1 = iir_params[c]
            h_pred = self._iir_analytic_predict(ch, target_horizon, a1, a2, b0, b1)
            outs.append(h_pred)

        all_f = torch.cat(outs, -1)
        repr_vec = self.fusion(torch.cat([psi[:, -1, :], all_f * 0.5], -1)) + psi[:, -1, :]
        return field[:, -1, :] + self.decoder(repr_vec)

    # ------------------------------------------------------------------
    # Stateful resonant field (Phase 1)
    # ------------------------------------------------------------------

    def reset_state(self, batch_size):
        """Reset all persistent field buffers for a new batch/sequence.

        Call this at the start of each training batch or inference sequence.
        """
        device = self.h1.device
        self.h1 = torch.zeros(batch_size, self.D, device=device)
        self.h2 = torch.zeros(batch_size, self.D, device=device)
        self.x1 = torch.zeros(batch_size, self.D, device=device)
        self.yang = torch.zeros(batch_size, self.D, device=device)
        self.yin = torch.zeros(batch_size, self.D, device=device)
        self.field_state = torch.zeros(batch_size, self.D, device=device)
        self.field_energy = torch.zeros(batch_size, self.C, device=device)
        self.qi_fluid = torch.zeros(batch_size, self.D, device=device)
        self.theta_fast_fwd.zero_()
        self.theta_fast_rev.zero_()
        self.gain_fast.zero_()
        self.err_h1.zero_()
        self.err_h2.zero_()
        self.act_h1.zero_()
        self.act_h2.zero_()
        self._frame_buffer = torch.zeros(batch_size, 4, self.D, device=device)
        self._frame_idx = 0

    def step(self, x_new, theta_shift=0.0, damp_scale=1.0,
             yang_gain=1.0, yin_gain=1.0, brainstem_gate=False):
        """Single IIR step with persistent state.

        x_new: [B, D] — one frame already projected to D-space
        theta_shift: frequency offset from brainstem attention
        damp_scale: damping modifier from brainstem homeostasis
        yang_gain, yin_gain: workspace gain modifiers
        brainstem_gate: if True, allows fast weight update (Phase 2)

        Returns: field_state [B, D]
        """
        B = x_new.shape[0]

        # ── 1. Per-chakra forward IIR with fast weights ──
        h_new_parts = []
        for c in range(self.C):
            start, end = self._offsets[c]
            w = end - start
            x_c = x_new[:, start:end]  # [B, w]

            # Active frequency = slow weight + fast weight
            theta = torch.sigmoid(self.fwd_theta[c] + self.theta_fast_fwd[c]) * math.pi
            a1 = 2.0 * PHI_INV * damp_scale * torch.cos(theta + theta_shift)
            a2 = -(PHI_INV * damp_scale) ** 2
            b0 = torch.sigmoid(self.fwd_b0[c])
            b1 = torch.sigmoid(self.fwd_b1[c])
            sf = b0 + b1 + 1e-8
            b0, b1 = b0 / sf, b1 / sf

            # Clone to avoid in-place modification corrupting autograd graph
            # when step() is called multiple times within a single forward()
            h1_c = self.h1[:, start:end].clone()
            h2_c = self.h2[:, start:end].clone()
            x1_c = self.x1[:, start:end].clone()

            h_new_c = b0 * x_c + b1 * x1_c + a1 * h1_c + a2 * h2_c
            h_new_c = h_new_c * (1.0 + self.gain_fast[c])

            # Update IIR state (reconstruct full tensor to avoid in-place)
            new_h1 = self.h1.clone()
            new_h2 = self.h2.clone()
            new_x1 = self.x1.clone()
            new_h2[:, start:end] = h1_c
            new_h1[:, start:end] = h_new_c
            new_x1[:, start:end] = x_c
            self.h2 = new_h2
            self.h1 = new_h1
            self.x1 = new_x1

            h_new_parts.append(h_new_c)

        # Update per-chakra energy (out-of-place to avoid autograd corruption)
        new_field_energy = self.field_energy.clone()
        for c in range(self.C):
            new_field_energy[:, c] = h_new_parts[c].pow(2).mean(dim=-1)
        self.field_energy = new_field_energy

        h_new = torch.cat(h_new_parts, dim=-1)  # [B, D]

        # ── 1b. Rolling buffer for reverse IIR ──
        self._frame_buffer[:, self._frame_idx % 4, :] = x_new.detach()
        self._frame_idx += 1
        if self._frame_idx >= 4:
            # Reverse IIR over full buffer (flipped)
            h_rev_parts = []
            for c in range(self.C):
                start, end = self._offsets[c]
                buf_c = self._frame_buffer[:, :, start:end]  # [B, 4, w]
                theta_r = torch.sigmoid(self.rev_theta[c]) * math.pi
                a1r = 2.0 * PHI_INV * torch.cos(theta_r)
                a2r = -(PHI_INV) ** 2
                b0r = torch.sigmoid(self.rev_b0[c])
                b1r = torch.sigmoid(self.rev_b1[c])
                sr = b0r + b1r + 1e-8
                b0r, b1r = b0r / sr, b1r / sr
                h_rev_c = self._iir(torch.flip(buf_c, [1]), a1r, a2r, b0r, b1r)
                h_rev_parts.append(h_rev_c)
            h_new = h_new - torch.cat(h_rev_parts, dim=-1)

        # ── 2. Fusion (same formula as _compute_repr) ──
        field_state = self.fusion(torch.cat([x_new, h_new * 0.5], dim=-1)) + x_new

        # ── 3. Dual workspace evolution ──
        self.yang = PHI_INV ** 2 * self.yang + PHI_INV * yang_gain * field_state
        self.yin = PHI_INV * self.yin + PHI_INV ** 2 * yin_gain * self.yang

        # ── 4. Qi-fluid = overlap + resonance ──
        qi_overlap = self.yang * self.yin
        self.qi_fluid = PHI_INV * self.qi_fluid + PHI_INV ** 2 * qi_overlap

        # ── 5. Conscious field state = harmonious cooperation ──
        self.field_state = PHI_INV * self.yang + PHI_INV ** 2 * self.yin

        # ── 6. Fast weight update (Phase 2: online learning) ──
        if brainstem_gate:
            self._update_fast_weights(h_new, self.field_state)

        return self.field_state

    def _update_fast_weights(self, h_new, field_state):
        """Update fast weights via local gradient descent on prediction error.

        Updates theta_fast and gain_fast in no_grad context.
        Called internally by step() when brainstem_gate=True.
        """
        with torch.no_grad():
            # Self-supervised error: prediction vs actual next frame
            pred = self.decoder(field_state)
            # We don't have the actual next frame here, so we use
            # the field state's own consistency as a proxy
            # (lower energy = more consistent = better prediction)
            error_signal = -self.field_energy.mean(dim=0)  # [C]

            for c in range(self.C):
                # IIR-smooth error and activity
                self.err_h1[c] = PHI_INV * self.err_h1[c] + (1 - PHI_INV) * error_signal[c]
                self.act_h1[c] = PHI_INV * self.act_h1[c] + (1 - PHI_INV) * h_new[:, self._offsets[c][0]:self._offsets[c][1]].abs().mean()

                # Local gradient: shift theta toward frequencies that reduce error
                theta = torch.sigmoid(self.fwd_theta[c]) * math.pi
                dh_dtheta = -2 * PHI_INV * math.sin(theta) * self.h1[:, self._offsets[c][0]:self._offsets[c][1]]
                # Approximate gradient: correlation between error and sensitivity
                grad_theta = (error_signal[c] * dh_dtheta).mean()

                # Update fast weights
                self.theta_fast_fwd[c] = PHI_INV * self.theta_fast_fwd[c] - 0.01 * grad_theta
                self.gain_fast[c] = PHI_INV * self.gain_fast[c] + 0.01 * (-self.err_h1[c]) * self.act_h1[c]

            # Normalize across chakras (prevent domination)
            self.theta_fast_fwd = self.theta_fast_fwd / (self.theta_fast_fwd.norm() + 1e-8) * 0.5
            self.theta_fast_rev = self.theta_fast_rev / (self.theta_fast_rev.norm() + 1e-8) * 0.5
            self.gain_fast = self.gain_fast / (self.gain_fast.norm() + 1e-8) * 1.0

    def step_sequence(self, psi, theta_shift=0.0, damp_scale=1.0,
                      yang_gain=1.0, yin_gain=1.0, brainstem_gate=False):
        """Process a sequence of D-space frames via repeated step() calls.

        psi: [B, T, D] — T frames of D-dimensional field state
        Returns: list of T field_state tensors [B, D]
        """
        B, T, D = psi.shape
        assert D == self.D
        states = []
        for t in range(T):
            state = self.step(
                psi[:, t, :],
                theta_shift=theta_shift,
                damp_scale=damp_scale,
                yang_gain=yang_gain,
                yin_gain=yin_gain,
                brainstem_gate=brainstem_gate,
            )
            states.append(state)
        return states

    def filter_info(self):
        """Report per-chakra filter characteristics."""
        info = []
        for c in range(self.C):
            theta = torch.sigmoid(self.fwd_theta[c]).item() * math.pi
            theta_r = torch.sigmoid(self.rev_theta[c]).item() * math.pi
            freq = theta / (2 * math.pi)
            freq_r = theta_r / (2 * math.pi)
            info.append({
                'chakra': c,
                'width': self.widths[c],
                'fwd_freq': freq,
                'rev_freq': freq_r,
                'period': 1.0 / max(freq, 1e-8),
            })
        return info
