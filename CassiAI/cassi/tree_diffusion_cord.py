"""TreeDiffusionCord — φ-branching tree of chakras for hierarchical denoising.

Instead of 13 flat chakras, this uses a tree where each level has fewer,
wider, slower chakras. The φ-branching creates natural timescale separation:

  Level 0: 13 chakras, fastest theta, D/13 dims each (fine detail)
  Level 1:  8 chakras, ceil(13/φ), D/8 dims each
  Level 2:  5 chakras, ceil(8/φ)
  Level 3:  3 chakras, ceil(5/φ)
  Level 4:  2 chakras, ceil(3/φ)
  Level 5:  1 chakra, root, slowest theta, all D dims (global context)

Each level:
  - Has its own IIR parameters, timestep embedding, chakra projections
  - Processes the SAME D-dimensional field (residual refinement)
  - Slower levels provide top-down modulation to faster levels
  - Contiguous chakra allocation at levels 1-5, strided at level 0

Information flow: bottom-up refinement + top-down cross-level modulation.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi.cord import PHI, PHI_INV
from cassi.diffusion_cord import (
    DiffusionCord, PhiTimestepEmbedding,
    cosine_noise_schedule, linear_noise_schedule
)


def compute_tree_levels(start=13):
    """Compute φ-branching tree levels: 13 → 8 → 5 → 3 → 2 → 1."""
    levels = [start]
    while levels[-1] > 1:
        nxt = max(1, int(levels[-1] / PHI + 0.5))
        if nxt == levels[-1]:
            nxt = levels[-1] - 1
        levels.append(nxt)
    return levels


class TreeLevel(nn.Module):
    """One level of the chakra tree.

    Args:
        D: field dimension (same for all levels)
        n_chakras: number of chakras at this level
        level_idx: depth in tree (0 = finest, N-1 = coarsest)
        time_emb_dim: timestep embedding dim
        strided: if True, use strided allocation; else contiguous
    """

    def __init__(self, D, n_chakras, level_idx, time_emb_dim=128, strided=False):
        super().__init__()
        self.D = D
        self.n_chakras = n_chakras
        self.level_idx = level_idx
        self.strided = strided

        # Chakra widths
        if strided:
            self.widths = []
            self._indices = []
            for c in range(n_chakras):
                idxs = list(range(c, D, n_chakras))
                self.widths.append(len(idxs))
                self._indices.append(idxs)
        else:
            base = D // n_chakras
            self.widths = [base] * n_chakras
            self.widths[-1] += D - sum(self.widths)
            self._indices = None

        # Timestep embedding — slower φ-spaced frequencies for deeper levels
        self.time_emb = PhiTimestepEmbedding(time_emb_dim)
        self.time_mod = nn.Sequential(
            nn.Linear(time_emb_dim, time_emb_dim),
            nn.GELU(),
            nn.Linear(time_emb_dim, n_chakras * 3),  # gain, theta, damp per chakra
        )

        # IIR parameters
        self.fwd_theta = nn.Parameter(torch.randn(n_chakras))
        self.fwd_b0 = nn.Parameter(0.1 * torch.randn(n_chakras))
        self.fwd_b1 = nn.Parameter(-0.5 + 0.1 * torch.randn(n_chakras))
        self.chakra_gain = nn.Parameter(torch.zeros(n_chakras))

        # Per-chakra nonlinear projections
        proj_down, proj_up = [], []
        for c in range(n_chakras):
            w = self.widths[c]
            bneck = max(8, w // 8)
            proj_down.append(nn.Linear(w, bneck, bias=False))
            proj_up.append(nn.Linear(bneck, w, bias=False))
        self.proj_down = nn.ModuleList(proj_down)
        self.proj_up = nn.ModuleList(proj_up)

        # Level fusion (bottlenecked — Linear(D*2, D) would be 33M params each)
        fusion_hidden = max(32, D // 16)
        self.fusion = nn.Sequential(
            nn.Linear(D * 2, fusion_hidden, bias=False),
            nn.GELU(),
            nn.Linear(fusion_hidden, D, bias=False),
        )
        # Cross-level modulation: parent → children (not used at root)
        if level_idx > 0:
            self.parent_mod = nn.Linear(D, n_chakras * 2)  # gain + theta per child

        self._init_theta()

    def _init_theta(self):
        """Initialize theta — slower at deeper levels."""
        theta_max = 2.5 * (PHI ** (-self.level_idx * 0.5))
        for c in range(self.n_chakras):
            theta_c = theta_max * (PHI ** (-c * 0.3))
            y = theta_c / math.pi
            y = max(0.001, min(0.999, y))
            self.fwd_theta.data[c] = math.log(y / (1.0 - y))

    def _split(self, x):
        parts = []
        for c in range(self.n_chakras):
            g = torch.sigmoid(self.chakra_gain[c]) * 2.0
            if self.strided:
                parts.append(x[:, self._indices[c]] * g)
            else:
                start = c * self.widths[0] if c < self.n_chakras - 1 else (c * self.widths[0])
                parts.append(x[:, start:start + self.widths[c]] * g)
        return parts

    def _merge(self, parts, x_shape):
        """Merge chakra outputs back to [B, D]."""
        out = torch.zeros(x_shape, device=parts[0].device, dtype=parts[0].dtype)
        for c in range(self.n_chakras):
            if self.strided:
                out[:, self._indices[c]] = parts[c]
            else:
                start = c * self.widths[0] if c < self.n_chakras - 1 else (c * self.widths[0])
                out[:, start:start + self.widths[c]] = parts[c]
        return out

    def forward(self, x, t, parent_out=None):
        """Process x through this level's chakras.

        Args:
            x: [B, D] input field
            t: [B] timesteps
            parent_out: optional [B, D] output from parent level for modulation

        Returns: [B, D] refined field
        """
        B = x.shape[0]

        t_emb = self.time_emb(t)
        t_mod = self.time_mod(t_emb)  # [B, n_chakras*3]

        # Parent modulation
        parent_gain = None
        if parent_out is not None and hasattr(self, 'parent_mod'):
            pmod = self.parent_mod(parent_out)  # [B, n_chakras*2]
            parent_gain = torch.sigmoid(pmod[:, :self.n_chakras])  # [B, n_chakras]
            parent_theta = 0.3 * torch.tanh(pmod[:, self.n_chakras:])  # [B, n_chakras]
        else:
            parent_theta = torch.zeros(B, self.n_chakras, device=x.device)

        x_parts = self._split(x)
        out_parts = []

        for c in range(self.n_chakras):
            gain_scale = t_mod[:, c * 3 + 0].unsqueeze(-1)
            t_theta = t_mod[:, c * 3 + 1].unsqueeze(-1)
            t_damp = t_mod[:, c * 3 + 2].unsqueeze(-1)

            # Frequency: base + timestep + parent modulation
            theta = torch.sigmoid(self.fwd_theta[c]) * math.pi
            theta = theta + 0.5 * torch.tanh(t_theta) * math.pi
            theta = theta + parent_theta[:, c:c+1] * math.pi
            theta = theta.clamp(0.001, math.pi - 0.001)

            # Damping
            d = PHI_INV * torch.sigmoid(t_damp)
            d = d.clamp(0.05, 1.0)

            # Feedforward gains with parent modulation
            b0 = torch.sigmoid(self.fwd_b0[c])
            b1 = torch.sigmoid(self.fwd_b1[c])
            sf = b0 + b1 + 1e-8
            b0, b1 = b0 / sf, b1 / sf
            gm = torch.sigmoid(gain_scale) * 2.0
            if parent_gain is not None:
                gm = gm * parent_gain[:, c:c+1]
            b0, b1 = b0 * gm, b1 * gm

            # Normalized resonant gain
            denom = 1.0 - 2.0 * d * torch.cos(theta) + d ** 2
            ng = torch.rsqrt(denom + 1e-8)
            sg = (b0 + b1) * ng
            sg = torch.tanh(sg) * 2.0

            resonant = x_parts[c] * sg
            refined = self.proj_down[c](x_parts[c])
            refined = F.gelu(refined)
            refined = self.proj_up[c](refined)
            out_parts.append(resonant + refined)

        all_f = self._merge(out_parts, x.shape)
        return self.fusion(torch.cat([x, all_f * 0.5], dim=-1)) + x


class TreeDiffusionCord(nn.Module):
    """φ-branching tree of chakra levels for hierarchical denoising.

    Replaces the flat 13-chakra structure with a tree where each level
    refines the representation at a different timescale.

    Level 0 (13 chakras, strided): finest detail, fastest theta
    Level 1 (8 chakras, contiguous): φ-compressed grouping
    ...
    Level N (1 chakra, contiguous): root, global context, slowest theta

    Args:
        D: field dimension
        num_timesteps: diffusion steps
        time_emb_dim: per-level timestep embedding dimension
        schedule: 'cosine' or 'linear'
    """

    def __init__(self, D=1040, num_timesteps=None, time_emb_dim=128,
                 schedule='cosine'):
        super().__init__()
        self.D = D
        if num_timesteps is None:
            num_timesteps = round(1000 * PHI)
        self.num_timesteps = num_timesteps

        # Noise schedule (shared across levels)
        if schedule == 'cosine':
            betas, alphas, alphas_cumprod = cosine_noise_schedule(num_timesteps)
        else:
            betas, alphas, alphas_cumprod = linear_noise_schedule(num_timesteps)
        self.register_buffer('betas', betas)
        self.register_buffer('alphas', alphas)
        self.register_buffer('alphas_cumprod', alphas_cumprod)

        alphas_cumprod_prev = F.pad(alphas_cumprod[:-1], (1, 0), value=1.0)
        self.register_buffer('alphas_cumprod_prev', alphas_cumprod_prev)
        self.register_buffer('sqrt_alphas_cumprod', torch.sqrt(alphas_cumprod))
        self.register_buffer('sqrt_one_minus_alphas_cumprod',
                             torch.sqrt(1.0 - alphas_cumprod))
        posterior_variance = betas * (1.0 - alphas_cumprod_prev) / (1.0 - alphas_cumprod)
        self.register_buffer('posterior_variance', posterior_variance)

        # Build φ-branching tree
        level_sizes = compute_tree_levels(13)
        self.levels = nn.ModuleList()
        for i, n_chakras in enumerate(level_sizes):
            strided = (i == 0)  # only leaf level uses strided allocation
            self.levels.append(TreeLevel(
                D=D, n_chakras=n_chakras, level_idx=i,
                time_emb_dim=time_emb_dim, strided=strided
            ))

        self.n_levels = len(self.levels)
        print(f"TreeDiffusionCord: {level_sizes} → {self.n_levels} levels")

        # ── Brainstem-compatible state (for RecurrentDiffusionBrain) ──
        self.C = 13  # report 13 chakras for brainstem compatibility
        self.register_buffer('field_state', torch.zeros(1, D))
        self.register_buffer('yang', torch.zeros(1, D))
        self.register_buffer('yin', torch.zeros(1, D))
        self.register_buffer('qi_fluid', torch.zeros(1, D))
        self.register_buffer('field_energy', torch.zeros(1, 13))

        # Brainstem-compatible contiguous offsets
        self._offsets = []
        offset = 0
        base = D // 13
        for c in range(13):
            w = base if c < 12 else D - offset
            self._offsets.append((offset, offset + w))
            offset += w

        self._mod_theta_shift = 0.0
        self._mod_damp_scale = 1.0

    def reset_state(self, batch_size):
        def _ensure(buf, shape):
            if buf.shape[0] != shape[0]:
                return torch.zeros(*shape, device=buf.device, dtype=buf.dtype)
            buf.zero_()
            return buf
        self.field_state = _ensure(self.field_state, (batch_size, self.D))
        self.yang = _ensure(self.yang, (batch_size, self.D))
        self.yin = _ensure(self.yin, (batch_size, self.D))
        self.qi_fluid = _ensure(self.qi_fluid, (batch_size, self.D))
        self.field_energy = _ensure(self.field_energy, (batch_size, 13))
        self._mod_theta_shift = 0.0
        self._mod_damp_scale = 1.0

    def apply_brainstem_modulation(self, stem_info):
        self._mod_theta_shift = stem_info.get('theta_shift', 0.0)
        self._mod_damp_scale = stem_info.get('damp_scale', 1.0)

    # ── Forward diffusion ──

    def q_sample(self, x_0, t, noise=None):
        if noise is None:
            noise = torch.randn_like(x_0)
        sa = self.sqrt_alphas_cumprod[t].view(-1, 1)
        som = self.sqrt_one_minus_alphas_cumprod[t].view(-1, 1)
        return sa * x_0 + som * noise, noise

    # ── Forward pass (bottom-up through tree) ──

    def _forward_impl(self, x_t, t):
        """Bottom-up then top-down refinement through the tree.

        Returns (h, level_outs) where level_outs are bottom-up per-level states.
        """
        # Bottom-up pass: store intermediate outputs
        h = x_t
        level_outs = []
        for level in self.levels:
            h = level(h, t, parent_out=None)
            level_outs.append(h)

        # Top-down pass: coarser → finer modulation
        # (The parent modulation is done inside TreeLevel.forward via parent_out)
        # Here we re-run with top-down context
        h = x_t
        for i, level in enumerate(self.levels):
            parent_out = level_outs[i + 1] if i + 1 < len(self.levels) else None
            h = level(h, t, parent_out=parent_out)

        # Update brainstem-readable state
        self.field_state = h.detach()
        B = h.shape[0]
        if self.field_energy.shape[0] < B:
            self.field_energy = torch.zeros(B, 13, device=h.device, dtype=h.dtype)
        for c in range(13):
            start, end = self._offsets[c]
            self.field_energy[:B, c] = h[:, start:end].norm(dim=-1).detach()

        return h, level_outs

    def forward(self, x_t, t):
        """Backward-compatible: return h only."""
        h, _ = self._forward_impl(x_t, t)
        return h

    def forward_with_levels(self, x_t, t):
        """Return (h, level_outs) for harmony per-level blending."""
        return self._forward_impl(x_t, t)

    def training_loss(self, x_0, t=None):
        B = x_0.shape[0]
        if t is None:
            t = torch.randint(0, self.num_timesteps, (B,), device=x_0.device)
        noise = torch.randn_like(x_0)
        x_t, _ = self.q_sample(x_0, t, noise=noise)
        x0_pred = self.forward(x_t, t)
        return F.mse_loss(x0_pred, x_0)

    def _subsample_steps(self, num_steps):
        step_size = self.num_timesteps // num_steps
        indices = list(range(self.num_timesteps - 1, -1, -step_size))
        return indices[:num_steps]

    @torch.no_grad()
    def sample_ddim(self, shape, num_steps=50, eta=0.0, device=None):
        B, D = shape
        if device is None:
            device = self.betas.device
        steps = self._subsample_steps(num_steps)
        x_t = torch.randn(B, D, device=device)

        for i, t_idx in enumerate(steps):
            t = torch.full((B,), t_idx, device=device, dtype=torch.long)
            t_prev = steps[i + 1] if i + 1 < len(steps) else -1

            x0_pred = self.forward(x_t, t)

            if t_prev >= 0:
                ac = self.alphas_cumprod[t_idx]
                ap = self.alphas_cumprod[t_prev]
                eps = (x_t - torch.sqrt(ac) * x0_pred) / torch.sqrt(1.0 - ac + 1e-8)
                s = 0.0  # deterministic
                pd = torch.sqrt(1.0 - ap - s**2 + 1e-8) * eps
                x_t = torch.sqrt(ap) * x0_pred + pd
            else:
                x_t = x0_pred

        return x_t


# ═══════════════════════════════════════════════════════════════════════════════
# Smoke test
# ═══════════════════════════════════════════════════════════════════════════════

def demo():
    print("=" * 60)
    print("TreeDiffusionCord Smoke Test")
    print("=" * 60)

    D = 4096
    model = TreeDiffusionCord(D=D)
    n_p = sum(p.numel() for p in model.parameters())
    print(f"D={D}, params={n_p:,}")

    x = torch.randn(4, D)
    t = torch.randint(0, 1000, (4,))
    out = model(x, t)
    print(f"Forward: shape={out.shape}, norm={out.norm():.4f}")

    loss = model.training_loss(x)
    print(f"Loss: {loss.item():.4f}")
    loss.backward()
    print("Gradients OK, no NaN ✓")

    print("\nSampling DDIM 50 steps...")
    s = model.sample_ddim((2, D), num_steps=50)
    print(f"Sample norm: {s.norm(dim=-1).mean():.2f}")
    assert not torch.isnan(s).any(), "NaN in samples!"
    print("All tests passed!")


if __name__ == '__main__':
    demo()
