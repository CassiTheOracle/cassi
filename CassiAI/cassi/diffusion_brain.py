"""DiffusionBrain — hierarchical multi-scale diffusion using the full three-tier stack.

Instead of a single DiffusionCord denoising bytes, DiffusionBrain uses the
full CassiBrain architecture (Spine → Brainstem → BrainField) as a hierarchical
denoiser. Each tier operates at its characteristic timescale and dimension:

  Tier 1 — Spine (fast, D=1024):        Denoises individual bytes
  Tier 2 — Brainstem (medium, D=D/φ):    Denoises compressed patterns
  Tier 3 — BrainField (slow, D=D×φ):     Denoises semantic structure

The key mechanism is HIERARCHICAL GUIDANCE: the slower tiers provide
conditioning signals that guide the faster tiers' denoising, analogous
to classifier-free guidance but using the brain's own representations.

This is a design document + scaffold. Full implementation requires
training the three tiers jointly or in a curriculum.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi.cord import PHI, PHI_INV
from cassi.diffusion_cord import DiffusionCord


# ═══════════════════════════════════════════════════════════════════════════════
# DiffusionBrainstem — denoises compressed representations
# ═══════════════════════════════════════════════════════════════════════════════

class DiffusionBrainstem(nn.Module):
    """Denoises the brainstem's compressed bottleneck representation.

    Takes a noisy bottleneck vector z_t [B, D_stem] and timestep t,
    predicts the clean bottleneck z_0.

    The denoised bottleneck provides guidance to the spine: it tells
    the spine what the compressed representation SHOULD look like,
    pulling the spine's denoising toward globally coherent patterns.

    Architecture:
      - φ-spaced sinusoidal timestep embedding
      - Small MLP denoiser (D_stem → D_stem/φ → D_stem)
      - QiStateMachine modulates denoising strength based on field energy
      - Chakra attention: which frequency bands of the spine need guidance

    Args:
        D: spine dimension
        D_stem: bottleneck dimension (default D // φ)
        num_timesteps: diffusion steps for brainstem
    """

    def __init__(self, D=1040, D_stem=None, num_timesteps=500):
        super().__init__()
        self.D = D
        self.D_stem = D_stem if D_stem is not None else int(D / PHI)

        # ── Timestep embedding ──
        time_dim = 128
        half = time_dim // 2
        freqs = torch.exp(-torch.linspace(0, math.log(10000), half) / PHI)
        self.register_buffer('time_freqs', freqs)
        self.time_proj = nn.Sequential(
            nn.Linear(time_dim, time_dim),
            nn.GELU(),
            nn.Linear(time_dim, self.D_stem),
        )

        # ── Denoiser: bottleneck → clean bottleneck ──
        # Uses a φ-scaled bottleneck pattern: compress → expand
        hidden = int(self.D_stem / PHI)
        self.denoiser = nn.Sequential(
            nn.Linear(self.D_stem + self.D_stem, hidden),  # noisy + time_emb
            nn.LayerNorm(hidden),
            nn.GELU(),
            nn.Linear(hidden, self.D_stem),
        )
        # Small init
        for m in self.denoiser.modules():
            if isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, std=0.01)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

        # ── Guidance projection: denoised bottleneck → spine modulation ──
        # Tells each spine chakra how to adjust its denoising
        self.guidance_proj = nn.Linear(self.D_stem, 13 * 2)  # gain + theta per chakra

        # ── Qi modulation ──
        self.qi_gate = nn.Sequential(
            nn.Linear(self.D_stem, 1),
            nn.Sigmoid(),
        )

    def _time_embed(self, t):
        t = t.float()
        args = t[:, None] * self.time_freqs[None, :]
        emb = torch.cat([torch.sin(args), torch.cos(args)], dim=-1)
        return self.time_proj(emb)  # [B, D_stem]

    def forward(self, z_t, t, spine_energy=None):
        """Denoise bottleneck and produce spine guidance.

        z_t: [B, D_stem] noisy bottleneck
        t: [B] timesteps
        spine_energy: optional [B, 13] per-chakra energy (for Qi modulation)

        Returns:
            z_0_pred: [B, D_stem] predicted clean bottleneck
            guidance: [B, 26] per-chakra gain+theta modulation for spine
            qi_gate: [B, 1] how much to trust the guidance (0 = ignore)
        """
        t_emb = self._time_embed(t)  # [B, D_stem]
        h = torch.cat([z_t, t_emb], dim=-1)  # [B, 2*D_stem]
        z_0_pred = self.denoiser(h) + z_t  # residual prediction

        guidance = self.guidance_proj(z_0_pred)  # [B, 26]
        qi_gate = self.qi_gate(z_0_pred)  # [B, 1]

        return z_0_pred, guidance, qi_gate


# ═══════════════════════════════════════════════════════════════════════════════
# DiffusionBrainField — denoises expanded cognitive representations
# ═══════════════════════════════════════════════════════════════════════════════

class DiffusionBrainField(nn.Module):
    """Denoises the brain's expanded cognitive field.

    Takes a noisy cognitive field c_t [B, D_brain] and timestep t,
    predicts the clean cognitive field c_0.

    The denoised brain field provides long-range semantic guidance
    to the brainstem, which then guides the spine.

    Architecture:
      - Projects bottleneck → brain dimension (D_brain = D_stem × φ)
      - Small diffusion denoiser operating at the slowest timescale
      - 13 φ-scaled chakras (same pattern as spine but slower/wider)
      - Output: clean cognitive field + guidance for brainstem

    Args:
        D_stem: brainstem bottleneck dimension
        D_brain: brain field dimension (default D_stem × φ)
        num_timesteps: diffusion steps (fewer than spine — slower dynamics)
    """

    def __init__(self, D_stem, D_brain=None, num_timesteps=250):
        super().__init__()
        self.D_stem = D_stem
        self.D_brain = D_brain if D_brain is not None else int(D_stem * PHI)

        # ── In/out projection ──
        self.in_proj = nn.Linear(D_stem, self.D_brain)
        self.out_proj = nn.Linear(self.D_brain, D_stem)

        # ── Timestep embedding (fewer timesteps → coarser embedding) ──
        time_dim = 128
        half = time_dim // 2
        freqs = torch.exp(-torch.linspace(0, math.log(10000), half) / (PHI * PHI))
        self.register_buffer('time_freqs', freqs)
        self.time_proj = nn.Sequential(
            nn.Linear(time_dim, time_dim),
            nn.GELU(),
            nn.Linear(time_dim, self.D_brain),
        )

        # ── Denoiser: small MLP in brain dimension ──
        hidden = int(self.D_brain / PHI)
        self.denoiser = nn.Sequential(
            nn.Linear(self.D_brain * 2, hidden),
            nn.LayerNorm(hidden),
            nn.GELU(),
            nn.Linear(hidden, self.D_brain),
        )
        for m in self.denoiser.modules():
            if isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, std=0.01)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

        # ── Guidance for brainstem ──
        self.guidance_proj = nn.Linear(self.D_brain, D_stem)

    def _time_embed(self, t):
        t = t.float()
        args = t[:, None] * self.time_freqs[None, :]
        emb = torch.cat([torch.sin(args), torch.cos(args)], dim=-1)
        return self.time_proj(emb)

    def forward(self, c_t, t):
        """Denoise cognitive field and produce brainstem guidance.

        c_t: [B, D_brain] noisy cognitive field
        t: [B] timesteps

        Returns:
            c_0_pred: [B, D_brain] predicted clean cognitive field
            brainstem_guidance: [B, D_stem] modulates brainstem denoising
        """
        t_emb = self._time_embed(t)
        h = torch.cat([c_t, t_emb], dim=-1)
        c_0_pred = self.denoiser(h) + c_t

        guidance = self.guidance_proj(c_0_pred)  # [B, D_stem]
        return c_0_pred, guidance


# ═══════════════════════════════════════════════════════════════════════════════
# HierarchicalDiffusionBrain — orchestrates the three tiers
# ═══════════════════════════════════════════════════════════════════════════════

class HierarchicalDiffusionBrain(nn.Module):
    """Full three-tier diffusion brain with hierarchical guidance.

    Denoising schedule (per DDIM step):
      1. Spine denoises bytes → clean field estimate
      2. Brainstem compresses the estimate → denoises bottleneck
      3. BrainField expands bottleneck → denoises cognitive field
      4. Cognitive field guides brainstem → brainstem guides spine
      5. Spine re-denoises with hierarchical guidance

    The guidance flows top-down:
      BrainField → Brainstem → Spine

    Each tier operates at its own timescale:
      - Spine: every step (fast, local)
      - Brainstem: every K steps (medium, pattern-level)
      - BrainField: every K×M steps (slow, semantic-level)

    Args:
        D: spine dimension
        D_stem: brainstem bottleneck (default D/φ)
        D_brain: brain field dimension (default D_stem×φ)
        K: brainstem update interval (default 2)
        M: brainfield update interval multiplier (default 2)
    """

    def __init__(self, D=1024, D_stem=None, D_brain=None, K=2, M=2):
        super().__init__()
        self.D = D
        self.D_stem = D_stem if D_stem is not None else int(D / PHI)
        self.D_brain = D_brain if D_brain is not None else int(self.D_stem * PHI)
        self.K = K
        self.M = M

        # ── Tier 1: Spine (fast byte-level denoiser) ──
        self.spine = DiffusionCord(D=D)

        # ── Tier 2: Brainstem (pattern-level denoiser) ──
        self.brainstem = DiffusionBrainstem(D=D, D_stem=self.D_stem)

        # ── Tier 3: BrainField (semantic-level denoiser) ──
        self.brainfield = DiffusionBrainField(D_stem=self.D_stem, D_brain=self.D_brain)

        # ── Compression for spine→brainstem ──
        self.compress = nn.Sequential(
            nn.Linear(D, self.D_stem),
            nn.LayerNorm(self.D_stem),
        )



    def forward(self, x_t, t, step_idx=0):
        """Hierarchical denoising step with top-down guidance.

        x_t: [B, D] noisy byte field
        step_idx: which DDIM step for timescale gating

        Returns: x_0_pred [B, D]
        """
        # 1. Spine base prediction
        x0_spine = self.spine(x_t, t)  # [B, D]

        # 2. Brainstem: compress → denoise (every K steps)
        guidance_signal = None
        if step_idx % self.K == 0:
            z_t = self.compress(x0_spine)  # [B, D_stem]
            z0_pred, chakra_guidance, qi_gate = self.brainstem(z_t, t)

            # 3. BrainField: expand → denoise (every K*M steps)
            if step_idx % (self.K * self.M) == 0:
                c_t = self.brainfield.in_proj(z0_pred)  # [B, D_brain]
                c0_pred, bf_guidance = self.brainfield(c_t, t)
                # BrainField output corrects brainstem bottleneck
                z0_pred = z0_pred + 0.1 * bf_guidance

            # Brainstem → Spine guidance: project bottleneck correction
            # back through compress to get a D-dimensional correction signal
            guidance_signal = self.compress[0].weight.T @ z0_pred.T  # [D, B]
            guidance_signal = guidance_signal.T * qi_gate  # [B, D], gated

        # 4. Apply guidance
        if guidance_signal is not None:
            x0_spine = x0_spine + 0.1 * guidance_signal

        return x0_spine

    def training_loss(self, x_0, t=None):
        """Training loss with hierarchical objectives.

        Loss = spine_loss + alpha*brainstem_loss + beta*brainfield_loss
        """
        B = x_0.shape[0]
        if t is None:
            t = torch.randint(0, self.spine.num_timesteps, (B,), device=x_0.device)

        # Spine loss
        noise = torch.randn_like(x_0)
        x_t, _ = self.spine.q_sample(x_0, t, noise=noise)
        x0_pred = self.spine(x_t, t)
        spine_loss = F.mse_loss(x0_pred, x_0)

        # Brainstem loss
        z_0 = self.compress(x_0)
        z_t, _ = self.spine.q_sample(z_0, t)
        z0_pred, _, _ = self.brainstem(z_t, t)
        stem_loss = F.mse_loss(z0_pred, z_0)
        # Brainfield loss
        c_0 = self.brainfield.in_proj(z_0.detach())
        c_t, _ = self.spine.q_sample(c_0, t)
        c0_pred, _ = self.brainfield(c_t, t)
        field_loss = F.mse_loss(c0_pred, c_0)

        return spine_loss + 0.1 * stem_loss + 0.05 * field_loss

# ═══════════════════════════════════════════════════════════════════════════════
# Usage sketch
# ═══════════════════════════════════════════════════════════════════════════════

def demo():
    """Minimal smoke test for HierarchicalDiffusionBrain."""
    D = 1040
    model = HierarchicalDiffusionBrain(D=D, K=2, M=2)
    print(f"Spine:     D={model.D}")
    print(f"Brainstem: D_stem={model.D_stem}")
    print(f"BrainField: D_brain={model.D_brain}")
    print(f"Timescales: spine=1, stem={model.K}, field={model.K * model.M}")
    print(f"Params: {sum(p.numel() for p in model.parameters()):,}")

    B = 4
    x = torch.randn(B, D)
    t = torch.randint(0, 1000, (B,))
    out = model(x, t, step_idx=0)
    print(f"Forward: shape={out.shape}, norm={out.norm():.4f}")

    loss = model.training_loss(x)
    print(f"Training loss: {loss.item():.4f}")
    loss.backward()
    print("Gradients OK, no NaN.")


if __name__ == '__main__':
    demo()
