"""CordObserver — φ-resonant observer head for transformer hidden states.

Replaces the MLP-based ObserverHead with a Cord-native architecture:
  - Projects transformer hidden states into a φ-scaled field
  - Processes through 13 chakra IIR filter bank (forward + reverse)
  - Fuses resonant outputs into a representation vector
  - Confidence, importance, and logits heads sit on top of the Cord repr

The Cord maintains a 4-frame rolling buffer, so predictions incorporate
temporal resonance from the previous 3 hidden states.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math

PHI = (1 + 5 ** 0.5) / 2
PHI_INV = 1 / PHI


class CordObserver(nn.Module):
    """
    Observer head built on CordPhysics resonance.

    Input:  hidden state from transformer  [..., D_model]
    Output: conf [...], imp [...], logits [..., V]

    During training on sequences, windows are built causally from the
    sequence so the observer sees [h_{t-3}, h_{t-2}, h_{t-1}, h_t]
    when predicting token t+1.

    Optional PEFT-style compression:
      - bottleneck_dim: compress D_model before the field projection
      - low_rank: factor the final D -> V logits projection as D -> r -> V
    """

    T_IN = 4  # IIR window length (same as CordPhysics)

    def __init__(self, d_model, vocab_size, D=1040, n_chakras=13,
                 bottleneck_dim=None, low_rank=None):
        super().__init__()
        self.d_model = d_model
        self.D = D
        self.n_chakras = n_chakras
        self.V = vocab_size
        self.bottleneck_dim = bottleneck_dim or d_model
        self.low_rank = low_rank

        # ── Optional input bottleneck (adapter-style compression) ──
        # Nonlinear MLP bottleneck: d_model -> bn -> GELU -> bn -> LayerNorm.
        # A single linear layer loses too much transformer hidden-state information.
        if self.bottleneck_dim < d_model:
            self.input_bottleneck = nn.Sequential(
                nn.Linear(d_model, self.bottleneck_dim),
                nn.GELU(),
                nn.Linear(self.bottleneck_dim, self.bottleneck_dim),
                nn.LayerNorm(self.bottleneck_dim),
            )
        else:
            self.input_bottleneck = nn.Identity()

        # ── Project (possibly bottlenecked) hidden state into field ──
        self.field_proj = nn.Sequential(
            nn.Linear(self.bottleneck_dim, D),
            nn.LayerNorm(D),
        )

        # ── Chakra widths: φ-scaled, sum to D ──
        raw = [PHI ** c for c in range(n_chakras)]
        total_raw = sum(raw)
        self.widths = [max(1, round(D * r / total_raw)) for r in raw]
        self.widths[-1] += D - sum(self.widths)

        # Per-chakra gains
        self.chakra_gain = nn.Parameter(torch.zeros(n_chakras))

        # Per-chakra IIR frequencies (learned, φ-spaced init)
        self.fwd_theta = nn.Parameter(torch.randn(n_chakras))
        self.rev_theta = nn.Parameter(torch.randn(n_chakras))

        # Per-chakra IIR feedforward gains
        self.fwd_b0 = nn.Parameter(0.1 * torch.randn(n_chakras))
        self.fwd_b1 = nn.Parameter(-0.5 + 0.1 * torch.randn(n_chakras))
        self.rev_b0 = nn.Parameter(0.1 * torch.randn(n_chakras))
        self.rev_b1 = nn.Parameter(-0.5 + 0.1 * torch.randn(n_chakras))

        # Fusion: last_frame + IIR_diffs → repr
        self.fusion = nn.Linear(D * 2, D, bias=False)

        # ── Confidence / Importance heads (on Cord repr) ──
        hid = int(d_model / PHI)
        self.confidence = nn.Sequential(
            nn.Linear(D, hid), nn.LayerNorm(hid), nn.GELU(), nn.Dropout(0.1),
            nn.Linear(hid, 1), nn.Sigmoid()
        )
        self.importance = nn.Sequential(
            nn.Linear(D, hid), nn.LayerNorm(hid), nn.GELU(), nn.Dropout(0.1),
            nn.Linear(hid, 1), nn.Sigmoid()
        )

        # ── Logits projection (Cord repr → vocab) ──
        # Optional low-rank factorization: D -> r -> V, like a LoRA output head.
        if self.low_rank and 0 < self.low_rank < min(D, vocab_size):
            self.logits_u = nn.Linear(D, self.low_rank, bias=False)
            self.logits_v = nn.Linear(self.low_rank, vocab_size, bias=False)
            self.logits_proj = None
        else:
            self.logits_proj = nn.Linear(D, vocab_size, bias=False)
            self.logits_u = None
            self.logits_v = None

        # ── Rolling frame buffer for inference ──
        self.register_buffer('_frame_buffer', torch.zeros(1, self.T_IN, D))
        self._frame_idx = 0
        self._buffer_ready = False

        self._init_theta()

    # ═══════════════════════════════════════════════════════════════════
    # Cord IIR core (adapted from CordPhysics)
    # ═══════════════════════════════════════════════════════════════════

    def _init_theta(self):
        """Initialize theta with inversely φ-spaced frequencies."""
        theta_max = 2.5
        for c in range(self.n_chakras):
            theta_c = theta_max * (PHI ** (-c))
            y = theta_c / math.pi
            y = max(0.001, min(0.999, y))
            param = math.log(y / (1.0 - y))
            self.fwd_theta.data[c] = param
            self.rev_theta.data[c] = param

    def _iir(self, x, a1, a2, b0, b1):
        """Second-order IIR over T_IN time steps.

        x: [..., T_IN, W] — T_IN frames of width W
        Returns: [..., W]
        """
        h0 = x[..., 0, :] * b0
        h1 = x[..., 1, :] * b0 + x[..., 0, :] * b1 + a1 * h0
        h  = x[..., 2, :] * b0 + x[..., 1, :] * b1 + a1 * h1 + a2 * h0
        out = x[..., 3, :] * b0 + x[..., 2, :] * b1 + a1 * h + a2 * h1
        return out

    def _split_chakras(self, psi):
        """Split psi [..., T_IN, D] into chakra tensors with gains applied."""
        psi_c = []
        offset = 0
        for c in range(self.n_chakras):
            w = self.widths[c]
            g = torch.sigmoid(self.chakra_gain[c])
            psi_c.append(psi[..., offset:offset + w] * g)
            offset += w
        return psi_c

    def _compute_repr(self, psi):
        """Core Cord computation: psi [..., T_IN, D] → repr [..., D].

        psi is the field history (already projected).
        """
        # Split into chakras
        psi_c = self._split_chakras(psi)  # list of [..., T_IN, W_c]

        outs = []
        for c in range(self.n_chakras):
            ch = psi_c[c]  # [..., T_IN, W_c]

            # Forward IIR
            theta = torch.sigmoid(self.fwd_theta[c]) * math.pi
            a1 = 2.0 * PHI_INV * torch.cos(theta)
            a2 = -(PHI_INV) ** 2
            # Softmax-normalized feedforward gains: stable, positive, sum to 1
            bf = F.softmax(torch.stack([self.fwd_b0[c], self.fwd_b1[c]]), dim=0)
            b0, b1 = bf[0], bf[1]
            h_fwd = self._iir(ch, a1, a2, b0, b1)

            # Reverse IIR
            theta_r = torch.sigmoid(self.rev_theta[c]) * math.pi
            a1r = 2.0 * PHI_INV * torch.cos(theta_r)
            a2r = -(PHI_INV) ** 2
            br = F.softmax(torch.stack([self.rev_b0[c], self.rev_b1[c]]), dim=0)
            b0r, b1r = br[0], br[1]
            h_rev = self._iir(torch.flip(ch, dims=[-2]), a1r, a2r, b0r, b1r)

            outs.append(h_fwd - h_rev)

        all_f = torch.cat(outs, dim=-1)  # [..., D]

        # Fusion: last frame + resonant difference
        last_frame = psi[..., -1, :]  # [..., D]
        repr_vec = self.fusion(torch.cat([last_frame, all_f * 0.5], dim=-1)) + last_frame
        # Stabilize scale before heads
        repr_vec = F.layer_norm(repr_vec, repr_vec.shape[-1:])

        return repr_vec

    def _project_logits(self, repr_vec):
        """Apply full-rank or low-rank logits projection."""
        if self.logits_proj is not None:
            return self.logits_proj(repr_vec)
        return self.logits_v(self.logits_u(repr_vec))

    # ═══════════════════════════════════════════════════════════════════
    # Sequence windowing for training
    # ═══════════════════════════════════════════════════════════════════

    def _build_causal_windows(self, hidden):
        """Build causal 4-frame windows from a sequence of hidden states.

        hidden: [B, L, D_model]
        Returns: psi [B, L, T_IN, D] where psi[b, l, i] = field of h_{max(0, l-3+i)}
        """
        B, L, _ = hidden.shape
        # Optional bottleneck, then project to field
        bottleneck = self.input_bottleneck(hidden)  # [B, L, bottleneck_dim]
        field = self.field_proj(bottleneck)          # [B, L, D]

        # Build causal windows with zero-padding for early positions
        windows = []
        for t in range(L):
            frames = []
            for i in range(self.T_IN):
                idx = t - (self.T_IN - 1) + i
                if idx < 0:
                    frames.append(torch.zeros(B, self.D, device=hidden.device, dtype=hidden.dtype))
                else:
                    frames.append(field[:, idx, :])
            windows.append(torch.stack(frames, dim=1))  # [B, T_IN, D]

        return torch.stack(windows, dim=1)  # [B, L, T_IN, D]

    # ═══════════════════════════════════════════════════════════════════
    # Forward pass
    # ═══════════════════════════════════════════════════════════════════

    def forward(self, hidden):
        """
        hidden: [..., D_model] — single token or [B, L, D_model] sequence.

        For sequences, builds causal 4-frame windows and vectorizes.
        For single tokens, uses the rolling frame buffer (inference mode).

        Returns: conf [...], imp [...], logits [..., V]
        """
        # Detect mode: sequence or single token
        if hidden.dim() == 2 and hidden.shape[0] == 1:
            # Single token, batch_size=1: [1, D_model]
            return self._forward_single(hidden[0])

        if hidden.dim() == 1:
            # Single token, no batch: [D_model]
            return self._forward_single(hidden)

        # Sequence mode: [B, L, D_model]
        return self._forward_sequence(hidden)

    def _forward_sequence(self, hidden):
        """Process a sequence of hidden states [B, L, D_model]."""
        B, L, _ = hidden.shape

        # Build causal windows [B, L, T_IN, D]
        psi = self._build_causal_windows(hidden)

        # Vectorized Cord computation over all positions
        # Reshape to [B*L, T_IN, D] for batch processing
        psi_flat = psi.reshape(B * L, self.T_IN, self.D)
        repr_flat = self._compute_repr(psi_flat)  # [B*L, D]
        repr_vec = repr_flat.reshape(B, L, self.D)  # [B, L, D]

        # Heads
        conf = self.confidence(repr_vec).squeeze(-1)  # [B, L]
        imp = self.importance(repr_vec).squeeze(-1)   # [B, L]
        logits = self._project_logits(repr_vec)        # [B, L, V]

        return conf, imp, logits

    def _forward_single(self, hidden):
        """Process a single hidden state [D_model] using rolling buffer."""
        # Optional bottleneck, then project to field
        bottleneck = self.input_bottleneck(hidden)  # [bottleneck_dim]
        field = self.field_proj(bottleneck)          # [D]

        # Update rolling buffer
        self._frame_buffer[0, self._frame_idx, :] = field.detach()
        self._frame_idx = (self._frame_idx + 1) % self.T_IN
        if self._frame_idx == 0:
            self._buffer_ready = True

        # If buffer not ready yet, use simple projection as fallback
        if not self._buffer_ready:
            conf = self.confidence(field.unsqueeze(0)).squeeze(-1)
            imp = self.importance(field.unsqueeze(0)).squeeze(-1)
            logits = self._project_logits(field.unsqueeze(0)).squeeze(0)
            return conf, imp, logits

        # Compute Cord repr from buffer [1, T_IN, D]
        repr_vec = self._compute_repr(self._frame_buffer)  # [1, D]

        # Heads
        conf = self.confidence(repr_vec).squeeze(-1)   # scalar
        imp = self.importance(repr_vec).squeeze(-1)    # scalar
        logits = self._project_logits(repr_vec).squeeze(0)  # [V]

        return conf, imp, logits

    def reset_buffer(self):
        """Reset the rolling frame buffer (call between prompts)."""
        self._frame_buffer.zero_()
        self._frame_idx = 0
        self._buffer_ready = False
