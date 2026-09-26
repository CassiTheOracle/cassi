"""DiffusionCord — φ-scaled diffusion model using Cord chakras as denoising backbone.

Instead of U-Net or transformer denoisers, DiffusionCord uses the Cord's
13 φ-scaled IIR chakras to denoise continuous field vectors. Each chakra
resonates with a specific frequency band, and the timestep embedding modulates
how aggressively each chakra filters.

Inspired by DiffusionGemma's masked discrete diffusion for text, but adapted
for the continuous field representation native to Cassi.

Architecture:
  - 13 φ-scaled chakras (same width allocation as CordPhysics)
  - Sinusoidal timestep embedding with φ-spaced frequencies
  - Per-chakra: learnable IIR parameters modulated by timestep
  - Per-chakra: small bottleneck MLP for nonlinear refinement
  - Fusion: combine chakra outputs + residual → x₀ prediction [B, D]
  - x₀-prediction training (directly predict clean field)
  - DDPM and DDIM sampling

References:
  - Ho et al. "Denoising Diffusion Probabilistic Models" (NeurIPS 2020)
  - Nichol & Dhariwal "Improved Denoising Diffusion Probabilistic Models" (ICML 2021)
  - Song et al. "Denoising Diffusion Implicit Models" (ICLR 2021)
  - Google DeepMind "DiffusionGemma" (June 2026)
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi.cord import PHI, PHI_INV


# ═══════════════════════════════════════════════════════════════════════════════
# Noise Schedule
# ═══════════════════════════════════════════════════════════════════════════════

def cosine_noise_schedule(num_timesteps, s=0.008):
    """Cosine noise schedule (Nichol & Dhariwal 2021).

    Returns (betas, alphas, alphas_cumprod) as 1-D tensors.
    """
    steps = num_timesteps + 1
    x = torch.linspace(0, num_timesteps, steps)
    alphas_cumprod = torch.cos(((x / num_timesteps) + s) / (1 + s) * math.pi * 0.5) ** 2
    alphas_cumprod = alphas_cumprod / alphas_cumprod[0]
    betas = 1 - alphas_cumprod[1:] / alphas_cumprod[:-1]
    betas = torch.clamp(betas, max=0.999)
    alphas = 1.0 - betas
    alphas_cumprod = alphas_cumprod[1:]
    return betas, alphas, alphas_cumprod


def linear_noise_schedule(num_timesteps, beta_start=1e-4, beta_end=0.02):
    """Linear noise schedule (Ho et al. 2020)."""
    betas = torch.linspace(beta_start, beta_end, num_timesteps)
    alphas = 1.0 - betas
    alphas_cumprod = torch.cumprod(alphas, dim=0)
    return betas, alphas, alphas_cumprod


# ═══════════════════════════════════════════════════════════════════════════════
# Timestep Embedding
# ═══════════════════════════════════════════════════════════════════════════════

class PhiTimestepEmbedding(nn.Module):
    """Sinusoidal timestep embedding with φ-spaced frequencies.

    Frequency bands follow φ-progression so the embedding naturally
    separates timescales: early timesteps activate fast bands,
    late timesteps activate slow bands.
    """

    def __init__(self, dim, max_period=10000):
        super().__init__()
        self.dim = dim
        half = dim // 2
        freqs = torch.exp(-torch.linspace(0, math.log(max_period), half) / PHI)
        self.register_buffer('freqs', freqs)

    def forward(self, t):
        """t: [B] integer timesteps in [0, T-1]."""
        t = t.float()
        args = t[:, None] * self.freqs[None, :]  # [B, half]
        emb = torch.cat([torch.sin(args), torch.cos(args)], dim=-1)  # [B, dim]
        if self.dim % 2 == 1:
            emb = F.pad(emb, (0, 1))
        return emb


# ═══════════════════════════════════════════════════════════════════════════════
# DiffusionCord
# ═══════════════════════════════════════════════════════════════════════════════

class DiffusionCord(nn.Module):
    """φ-scaled diffusion denoiser using Cord chakra architecture.

    Predicts the clean field x₀ directly from a noisy field x_t given timestep t.
    Uses x₀-prediction training and DDPM/DDIM sampling.

    Args:
        D: field dimension (default 1040)
        num_timesteps: total diffusion steps (default: φ-scaled ~1618)
        time_emb_dim: timestep embedding dimension
        schedule: 'cosine' or 'linear'
    """

    def __init__(self, D=1040, num_timesteps=None, time_emb_dim=256,
                 schedule='cosine'):
        super().__init__()
        self.D = D

        if num_timesteps is None:
            num_timesteps = round(1000 * PHI)  # ~1618
        self.num_timesteps = num_timesteps

        # ── Noise schedule ──
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

        # ── 13 φ-scaled chakra widths ──
        # ── 13 strided chakras ──
        # Each chakra takes every C-th dimension, so every chakra sees
        # the entire field at a different phase offset. This replaces the
        # old contiguous allocation where 60% of dimensions sat in chakra 12.
        # φ-scaling applies to internal processing (theta, damping), not width.
        self.C = 13
        self.widths = []
        self._offsets = []
        for c in range(self.C):
            indices = list(range(c, D, self.C))
            self.widths.append(len(indices))
            self._offsets.append(indices)
        # ── Timestep embedding ──
        self.time_emb = PhiTimestepEmbedding(time_emb_dim)

        # ── Per-chakra parameters ──
        self.fwd_theta = nn.Parameter(torch.randn(self.C))
        self.fwd_b0 = nn.Parameter(0.1 * torch.randn(self.C))
        self.fwd_b1 = nn.Parameter(-0.5 + 0.1 * torch.randn(self.C))
        self.chakra_gain = nn.Parameter(torch.zeros(self.C))

        # Per-chakra nonlinear projections
        chakra_proj_down = []
        chakra_proj_up = []
        for c in range(self.C):
            w = self.widths[c]
            bneck = max(8, w // 2)
            chakra_proj_down.append(nn.Linear(w, bneck, bias=False))
            chakra_proj_up.append(nn.Linear(bneck, w, bias=False))
            nn.init.normal_(chakra_proj_down[-1].weight, std=0.01)
            nn.init.normal_(chakra_proj_up[-1].weight, std=0.01)
        self.chakra_proj_down = nn.ModuleList(chakra_proj_down)
        self.chakra_proj_up = nn.ModuleList(chakra_proj_up)

        # ── Fusion ──
        self.fusion = nn.Linear(D * 2, D, bias=False)
        nn.init.normal_(self.fusion.weight, std=0.01)

        # ── Timestep → chakra modulation ──
        self.time_modulation = nn.Sequential(
            nn.Linear(time_emb_dim, time_emb_dim),
            nn.GELU(),
            nn.Linear(time_emb_dim, self.C * 3),
        )

        self._init_theta()

    def _init_theta(self):
        """Initialize chakra frequencies with φ-inverse spacing."""
        theta_max = 2.5
        for c in range(self.C):
            theta_c = theta_max * (PHI ** (-c))
            y = theta_c / math.pi
            y = max(0.001, min(0.999, y))
            param = math.log(y / (1.0 - y))
            self.fwd_theta.data[c] = param

    # ── Forward diffusion (noising) ──

    def q_sample(self, x_0, t, noise=None):
        """Forward diffusion: sample x_t ~ q(x_t | x_0).

        x_0: [B, D] clean field
        t: [B] integer timesteps
        noise: optional pre-sampled noise [B, D]
        Returns: x_t [B, D], noise [B, D]
        """
        if noise is None:
            noise = torch.randn_like(x_0)
        sqrt_alpha = self.sqrt_alphas_cumprod[t].view(-1, 1)
        sqrt_one_minus = self.sqrt_one_minus_alphas_cumprod[t].view(-1, 1)
        x_t = sqrt_alpha * x_0 + sqrt_one_minus * noise
        return x_t, noise

    # ── Denoising backbone ──

    def _split_chakras(self, x):
        """Split x [B, D] into strided chakra slices with learned gain."""
        parts = []
        for c in range(self.C):
            indices = self._offsets[c]
            g = torch.sigmoid(self.chakra_gain[c]) * 2.0
            parts.append(x[:, indices] * g)
        return parts
    def _chakra_transform(self, x_c, t_mod, c):
        """Single-chakra transform: predict clean field for this band.

        x_c: [B, w_c] — chakra slice of noisy field
        t_mod: [B, 3*C] — timestep modulation
        c: chakra index

        Returns: [B, w_c] — estimated clean field for this band
        """
        gain_scale = t_mod[:, c * 3 + 0].unsqueeze(-1)
        theta_shift = t_mod[:, c * 3 + 1].unsqueeze(-1)
        damp_scale = t_mod[:, c * 3 + 2].unsqueeze(-1)

        # Frequency: base theta + timestep shift
        theta = torch.sigmoid(self.fwd_theta[c]) * math.pi
        theta = theta + 0.5 * torch.tanh(theta_shift) * math.pi
        theta = theta.clamp(0.001, math.pi - 0.001)

        # Damping: base φ-damping × timestep modulation
        effective_damp = PHI_INV * torch.sigmoid(damp_scale)
        effective_damp = effective_damp.clamp(0.05, 1.0)

        # Feedforward gains
        b0 = torch.sigmoid(self.fwd_b0[c])
        b1 = torch.sigmoid(self.fwd_b1[c])
        sf = b0 + b1 + 1e-8
        b0, b1 = b0 / sf, b1 / sf
        gain_mod = torch.sigmoid(gain_scale) * 2.0
        b0 = b0 * gain_mod
        b1 = b1 * gain_mod

        # Normalized resonant gain (bounded)
        denom = 1.0 - 2.0 * effective_damp * torch.cos(theta) + effective_damp ** 2
        norm_gain = torch.rsqrt(denom + 1e-8)
        ss_gain = (b0 + b1) * norm_gain
        ss_gain = torch.tanh(ss_gain) * 2.0

        # Linear resonant response
        resonant = x_c * ss_gain

        # Per-chakra nonlinear refinement
        refined = self.chakra_proj_down[c](x_c)
        refined = F.gelu(refined)
        refined = self.chakra_proj_up[c](refined)

        return resonant + refined

    def forward(self, x_t, t):
        """Predict the clean field x₀ from noisy field x_t at timestep t.

        x_t: [B, D] — noisy field at timestep t
        t: [B] — integer timesteps

        Returns: x₀_pred [B, D]
        """
        t_emb = self.time_emb(t)
        t_mod = self.time_modulation(t_emb)

        x_parts = self._split_chakras(x_t)

        chakra_outs = []
        for c in range(self.C):
            field_c = self._chakra_transform(x_parts[c], t_mod, c)
            chakra_outs.append(field_c)

        # Scatter chakra outputs back to original dimension order
        all_f = torch.zeros_like(x_t)
        for c in range(self.C):
            all_f[:, self._offsets[c]] = chakra_outs[c]

        x0_pred = self.fusion(torch.cat([x_t, all_f * 0.5], dim=-1)) + x_t
        return x0_pred

    # ── Training ──
    def training_loss(self, x_0, t=None):
        """Compute diffusion training loss (x₀-prediction).

        x_0: [B, D] — clean field vectors
        t: optional [B] timesteps; sampled uniformly if None

        Returns: scalar MSE loss
        """
        B = x_0.shape[0]
        if t is None:
            t = torch.randint(0, self.num_timesteps, (B,), device=x_0.device)

        noise = torch.randn_like(x_0)
        x_t, _ = self.q_sample(x_0, t, noise=noise)
        x0_pred = self.forward(x_t, t)
        loss = F.mse_loss(x0_pred, x_0)
        return loss

    # ── Sampling (DDPM with x₀-prediction) ──

    @torch.no_grad()
    def _sample_loop(self, shape, step_indices, device, progress=False):
        """Shared reverse diffusion loop (x₀-prediction).

        At each step, the model predicts x₀ directly from x_t.
        We blend x₀_pred with x_t via the DDPM posterior to get x_{t-1}.
        """
        B, D = shape
        x_t = torch.randn(B, D, device=device)

        for i, t_idx in enumerate(step_indices):
            t = torch.full((B,), t_idx, device=device, dtype=torch.long)
            t_prev = step_indices[i + 1] if i + 1 < len(step_indices) else -1

            x0_pred = self.forward(x_t, t)

            if t_prev >= 0:
                alpha_cumprod = self.alphas_cumprod[t_idx]
                alpha_cumprod_prev = self.alphas_cumprod[t_prev]
                beta = self.betas[t_idx]
                alpha = self.alphas[t_idx]

                coef_x0 = torch.sqrt(alpha_cumprod_prev) * beta / (1.0 - alpha_cumprod)
                coef_xt = torch.sqrt(alpha) * (1.0 - alpha_cumprod_prev) / (1.0 - alpha_cumprod)
                mean = coef_x0 * x0_pred + coef_xt * x_t

                posterior_variance = self.posterior_variance[t_idx]
                if t_idx > 0:
                    noise = torch.randn_like(x_t)
                    x_t = mean + torch.sqrt(posterior_variance) * noise
                else:
                    x_t = mean
            else:
                x_t = x0_pred

            if progress:
                yield x_t.clone()

        yield x_t

    @torch.no_grad()
    def sample(self, shape, num_steps=None, device=None):
        """Generate a field from pure noise via DDPM reverse process.

        shape: (B, D) tuple
        num_steps: number of diffusion steps (default: all)
        device: torch device

        Returns: x_0 [B, D]
        """
        B, D = shape
        if device is None:
            device = self.betas.device

        if num_steps is None:
            num_steps = self.num_timesteps

        if num_steps < self.num_timesteps:
            step_indices = self._subsample_steps(num_steps)
        else:
            step_indices = list(reversed(range(self.num_timesteps)))

        *_, last = self._sample_loop(shape, step_indices, device, progress=True)
        return last

    @torch.no_grad()
    def sample_iter(self, shape, num_steps=None, device=None):
        """Generate a field progressively, yielding intermediate states.

        Yields x_t at each denoising step, from noise to clean field.
        """
        if device is None:
            device = self.betas.device

        if num_steps is None:
            num_steps = self.num_timesteps

        if num_steps < self.num_timesteps:
            step_indices = self._subsample_steps(num_steps)
        else:
            step_indices = list(reversed(range(self.num_timesteps)))

        yield from self._sample_loop(shape, step_indices, device, progress=True)

    def _subsample_steps(self, num_steps):
        """Create a subsampled sequence of timesteps for faster sampling."""
        step_size = self.num_timesteps // num_steps
        indices = list(range(self.num_timesteps - 1, -1, -step_size))
        return indices[:num_steps]

    # ── DDIM sampling (faster, deterministic) ──

    @torch.no_grad()
    def sample_ddim(self, shape, num_steps=50, eta=0.0, device=None):
        """DDIM sampling (Song et al. 2021).

        eta=0.0 → deterministic (DDIM)
        eta=1.0 → stochastic (DDPM-like)

        Args:
            shape: (B, D)
            num_steps: number of sampling steps (<< num_timesteps)
            eta: stochasticity parameter
            device: torch device

        Returns: x_0 [B, D]
        """
        B, D = shape
        if device is None:
            device = self.betas.device

        step_indices = self._subsample_steps(num_steps)
        x_t = torch.randn(B, D, device=device)

        for i in range(len(step_indices)):
            t_idx = step_indices[i]
            t = torch.full((B,), t_idx, device=device, dtype=torch.long)

            if i < len(step_indices) - 1:
                t_prev = step_indices[i + 1]
            else:
                t_prev = -1

            x0_pred = self.forward(x_t, t)

            alpha_cumprod = self.alphas_cumprod[t_idx]
            alpha_cumprod_prev = self.alphas_cumprod[t_prev] if t_prev >= 0 else torch.tensor(1.0, device=device)

            # DDIM sigma
            sigma_t = eta * torch.sqrt((1.0 - alpha_cumprod_prev) / (1.0 - alpha_cumprod + 1e-8)) * \
                      torch.sqrt(1.0 - alpha_cumprod / (alpha_cumprod_prev + 1e-8))

            # Convert x₀_pred to ε_pred for the direction term
            eps_pred = (x_t - torch.sqrt(alpha_cumprod) * x0_pred) / torch.sqrt(1.0 - alpha_cumprod + 1e-8)
            pred_dir = torch.sqrt(1.0 - alpha_cumprod_prev - sigma_t**2 + 1e-8) * eps_pred

            x_t = torch.sqrt(alpha_cumprod_prev) * x0_pred + pred_dir

            if eta > 0 and t_prev >= 0:
                noise = torch.randn_like(x_t)
                x_t = x_t + sigma_t * noise

        return x_t

    # ── Utility ──

    def filter_info(self):
        """Report per-chakra filter characteristics."""
        info = []
        for c in range(self.C):
            theta = torch.sigmoid(self.fwd_theta[c]).item() * math.pi
            freq = theta / (2 * math.pi)
            info.append({
                'chakra': c,
                'width': self.widths[c],
                'freq': round(freq, 6),
                'period': round(1.0 / max(freq, 1e-8), 1),
            })
        return info


# ═══════════════════════════════════════════════════════════════════════════════
# Field Denoising Autoencoder
# ═══════════════════════════════════════════════════════════════════════════════

class FieldDenoiser(nn.Module):
    """Simpler diffusion denoiser that wraps DiffusionCord for field data.

    Handles the full pipeline: noise → denoise → field reconstruction.
    Includes an optional encoder/decoder for 1024-dim input.
    """

    def __init__(self, D=1040, num_timesteps=None, time_emb_dim=256,
                 schedule='cosine'):
        super().__init__()
        self.D = D
        self.diffusion = DiffusionCord(D=D, num_timesteps=num_timesteps,
                                       time_emb_dim=time_emb_dim, schedule=schedule)

        self.encoder = nn.Sequential(
            nn.Linear(1024, D),
            nn.LayerNorm(D),
        )
        self.decoder = nn.Linear(D, 1024)

    def forward(self, x_t, t):
        """Predict clean field from raw 1024-dim noisy field."""
        z = self.encoder(x_t)
        z0_pred = self.diffusion(z, t)
        return z0_pred

    def training_loss(self, x_0):
        """Training loss on raw 1024-dim field data."""
        z_0 = self.encoder(x_0)
        B = z_0.shape[0]
        t = torch.randint(0, self.diffusion.num_timesteps, (B,), device=z_0.device)
        noise = torch.randn_like(z_0)
        z_t, _ = self.diffusion.q_sample(z_0, t, noise=noise)
        z0_pred = self.diffusion(z_t, t)
        loss = F.mse_loss(z0_pred, z_0)
        return loss

    @torch.no_grad()
    def sample(self, B, num_steps=None, device=None):
        """Generate a 1024-dim field from noise."""
        if device is None:
            device = next(self.parameters()).device
        z_0 = self.diffusion.sample((B, self.D), num_steps=num_steps, device=device)
        return self.decoder(z_0)
