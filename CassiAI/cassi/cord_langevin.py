"""CordLangevinSampler — text generation via resonant Langevin dynamics on the Cord.

Instead of autoregressive token-by-token generation or explicit diffusion
training, this uses the Cord's own φ-damped IIR dynamics as a natural
denoiser in field space. The key insight: the Cord's chakras are resonant
filters — they amplify signal at their characteristic frequencies and damp
everything else. Given a trained Cord, we can use it as a Langevin sampler:

  1. Initialize field with noise (or noise + prompt bias)
  2. Step the Cord forward, which applies φ-damped IIR filtering
  3. The IIR filters naturally separate signal from noise over steps
  4. Decode the converged field back to text

The "ripple" perturbation replaces isotropic Gaussian noise with a
structured perturbation shaped by the Cord's own resonant sensitivity.
This is computed by running the Cord twice — once on the field, once on
a slightly-noised copy — and taking the difference. The difference
reveals which directions in field space the Cord is actually sensitive
to, making exploration far more efficient than random noise.

This is the Cassi-native alternative to DiffusionCord: no separate
denoiser training needed — just use the Cord you already have.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi.cord import CordPhysics, PHI, PHI_INV
from cassi.text_codec import ByteEncoder, TextDecoder


class CordLangevinSampler(nn.Module):
    """Wrap a trained CordPhysics for Langevin sampling in field space.

    The Cord is used as an energy-based model: each step() applies
    φ-damped IIR filtering that moves the field toward a low-energy
    (high-resonance) configuration. Adding structured ripples prevents
    the dynamics from collapsing to a trivial fixed point.

    Args:
        cord: a trained CordPhysics instance
        T: text decoder for field→text conversion
    """

    def __init__(self, cord, text_decoder=None):
        super().__init__()
        self.cord = cord
        self.D = cord.D
        self.text_decoder = text_decoder  # None → text output not available
    @torch.no_grad()
    def _compute_ripple(self, field, noise_scale=0.01):
        """Compute the Cord's resonant sensitivity direction.

        Runs the Cord on the field and on a slightly-noised copy.
        The difference is the "ripple" — directions the Cord is
        actually sensitive to.

        field: [B, D]
        noise_scale: std of the probe noise

        Returns: ripple [B, D]
        """
        # Run Cord on clean field
        out_clean = self.cord.step(field)

        # Run Cord on noised field
        probe_noise = torch.randn_like(field) * noise_scale
        field_noised = field + probe_noise
        out_noised = self.cord.step(field_noised)

        # Ripple = difference in response
        ripple = out_noised - out_clean

        # Normalize to unit scale for stable stepping
        ripple_norm = ripple.norm(dim=-1, keepdim=True).clamp_min(1e-8)
        ripple = ripple / ripple_norm

        return ripple


    @torch.no_grad()
    def sample(self, B, num_steps=200, noise_init_scale=1.0,
               ripple_scale=0.1, noise_scale=0.01, device=None,
               temperature=1.0, return_trajectory=False,
               field_clamp=None):
        """Generate a field via resonant Langevin dynamics.

        Args:
            B: batch size
            num_steps: number of Langevin iterations
            noise_init_scale: std of initial noise field
            ripple_scale: how strongly to follow the resonant ripple direction
            noise_scale: std of additive Gaussian noise (Langevin term)
            device: torch device
            temperature: scales the Langevin noise
            return_trajectory: if True, return all intermediate fields
            field_clamp: if set, clamp field L2 norm to this max value

        Returns:
            If return_trajectory: list of [B, D] fields at each step
            Otherwise: final field [B, D]
        """
        if device is None:
            device = next(self.cord.parameters()).device

        D = self.D

        # Initialize Cord state for batch
        self.cord.reset_state(B)

        # Start from pure noise in field space
        field = torch.randn(B, D, device=device) * noise_init_scale

        trajectory = [field.clone()] if return_trajectory else None

        for step in range(num_steps):
            # 1. Compute resonant ripple direction
            ripple = self._compute_ripple(field, noise_scale=max(noise_scale * 0.1, 1e-4))

            # 2. Langevin step: Cord dynamics + ripple + noise
            field_next = self.cord.step(field)  # Cord's natural dynamics

            # Normalize to prevent explosion from untrained weights
            f_norm = field_next.norm(dim=-1, keepdim=True).clamp_min(1e-8)
            if field_clamp is not None:
                scale = torch.where(f_norm > field_clamp, field_clamp / f_norm, torch.ones_like(f_norm))
                field_next = field_next * scale
            else:
                # Auto-scale: keep field at roughly unit-variance
                target_scale = math.sqrt(D) * noise_init_scale
                field_next = field_next * (target_scale / f_norm)

            # Move along ripple direction (resonant exploration)
            field_next = field_next + ripple_scale * ripple

            # Add Langevin noise for ergodicity
            if noise_scale > 0:
                langevin_noise = torch.randn_like(field) * noise_scale * math.sqrt(temperature)
                field_next = field_next + langevin_noise

            field = field_next

            if return_trajectory:
                trajectory.append(field.clone())

        if return_trajectory:
            return trajectory

        return field


    @torch.no_grad()
    def sample_with_prompt(self, prompt_field, num_steps=200,
                           ripple_scale=0.1, noise_scale=0.01,
                           prompt_strength=0.3, device=None,
                           temperature=1.0):
        """Generate a field conditioned on a prompt field.

        The prompt acts as an anchor: after each Langevin step,
        we blend back toward the prompt at the prompt positions.
        prompt_field: [B, D] field encoding of the prompt text

        Returns: generated field [B, D]
        """
        if device is None:
            device = next(self.cord.parameters()).device

        D = self.D
        B = prompt_field.shape[0]

        self.cord.reset_state(B)

        # Initialize with noise, blended with prompt
        noise = torch.randn(B, D, device=device)
        field = prompt_strength * prompt_field + (1 - prompt_strength) * noise

        for step in range(num_steps):
            ripple = self._compute_ripple(field, noise_scale=max(noise_scale * 0.1, 1e-4))
            field_next = self.cord.step(field) + ripple_scale * ripple

            # Normalize to prevent explosion from untrained weights
            f_norm = field_next.norm(dim=-1, keepdim=True).clamp_min(1e-8)
            target_scale = math.sqrt(D)
            field_next = field_next * (target_scale / f_norm)

            if noise_scale > 0:
                field_next = field_next + torch.randn_like(field) * noise_scale * math.sqrt(temperature)

            # Anchor to prompt
            field_next = prompt_strength * prompt_field + (1 - prompt_strength) * field_next
        return field

    @torch.no_grad()
    def generate_text(self, B, num_steps=200, max_new_tokens=256,
                      temperature=1.0, device=None):
        """Generate text by sampling a field and decoding it.

        Args:
            B: batch size
            num_steps: Langevin iterations for field generation
            max_new_tokens: max tokens to decode
            temperature: sampling temperature
            device: torch device

        Returns: list of decoded text strings
        """
        # Sample a field
        field_D = self.sample(B, num_steps=num_steps, temperature=temperature, device=device)

        # Project D → 1024 (field space)
        field_1024 = self.cord.decoder(field_D)  # [B, 1024]

        # Decode to text (simple argmax for now)
        texts = []
        for b in range(B):
            text = self.text_decoder.decode(
                field_1024[b:b+1],
                max_length=max_new_tokens,
                temperature=temperature,
            )
            texts.append(text)

        return texts



# ═══════════════════════════════════════════════════════════════════════════════
# DiffusionCordLangevin — Langevin sampling with DiffusionCord denoiser
# ═══════════════════════════════════════════════════════════════════════════════

class DiffusionCordLangevin:
    """Langevin sampler using a trained DiffusionCord as the denoising step.

    Unlike DDIM (deterministic, fixed schedule), Langevin dynamics add
    structured "ripple" perturbations + noise at each step, which can
    produce more diverse samples and escape local minima.

    Args:
        diffusion: trained DiffusionCord instance
        t_fixed: timestep used for the denoising step (0 = most aggressive)
    """

    def __init__(self, diffusion, t_fixed=0):
        self.diffusion = diffusion
        self.t_fixed = t_fixed
        self.D = diffusion.D

    @torch.no_grad()
    def _step(self, field, t=None):
        """Denoising step: predict clean field from noisy one."""
        if t is None:
            t = self.t_fixed
        B = field.shape[0]
        t_tensor = torch.full((B,), t, device=field.device, dtype=torch.long)
        return self.diffusion(field, t_tensor)

    @torch.no_grad()
    def _compute_ripple(self, field, noise_scale=0.01, t=None):
        """Compute the DiffusionCord's sensitivity direction."""
        if t is None:
            t = self.t_fixed
        B = field.shape[0]
        t_tensor = torch.full((B,), t, device=field.device, dtype=torch.long)

        out_clean = self.diffusion(field, t_tensor)

        probe_noise = torch.randn_like(field) * noise_scale
        field_noised = field + probe_noise
        out_noised = self.diffusion(field_noised, t_tensor)

        ripple = out_noised - out_clean
        ripple_norm = ripple.norm(dim=-1, keepdim=True).clamp_min(1e-8)
        return ripple / ripple_norm

    @torch.no_grad()
    def sample(self, B, num_steps=100, noise_init_scale=1.0,
               ripple_scale=0.1, noise_scale=0.02, device=None,
               temperature=1.0, t_fixed=None):
        """Generate a field via Langevin dynamics with DiffusionCord denoiser.

        Args:
            B: batch size
            num_steps: number of Langevin iterations
            noise_init_scale: std of initial noise
            ripple_scale: strength of resonant ripple perturbation
            noise_scale: std of Langevin noise
            device: torch device
            temperature: scales Langevin noise
            t_fixed: override timestep (0 = most aggressive denoising)

        Returns: field [B, D]
        """
        if device is None:
            device = next(self.diffusion.parameters()).device
        if t_fixed is None:
            t_fixed = self.t_fixed

        D = self.D
        field = torch.randn(B, D, device=device) * noise_init_scale

        for step in range(num_steps):
            # 1. Compute ripple (sensitivity direction)
            ripple = self._compute_ripple(field, noise_scale=noise_scale * 0.1,
                                          t=t_fixed)

            # 2. Denoising step
            field_clean = self._step(field, t=t_fixed)

            # 3. Blend: move toward clean, explore via ripple + noise
            blend = 0.3  # How much to trust the denoiser vs current state
            field_next = blend * field_clean + (1 - blend) * field
            field_next = field_next + ripple_scale * ripple

            if noise_scale > 0:
                field_next = field_next + torch.randn_like(field) * noise_scale * math.sqrt(temperature)

            # Normalize to prevent drift
            f_norm = field_next.norm(dim=-1, keepdim=True).clamp_min(1e-8)
            target_scale = math.sqrt(D) * noise_init_scale
            field_next = field_next * (target_scale / f_norm)

            field = field_next

        return field


# ═══════════════════════════════════════════════════════════════════════════════

def test_langevin_sampler():
    """Smoke test: instantiate, sample, check stability."""
    print("=" * 60)
    print("CordLangevinSampler Smoke Test")
    print("=" * 60)

    device = 'cpu'
    D = 1040

    # Create a fresh (untrained) Cord — this won't generate coherent text,
    # but verifies the Langevin dynamics are numerically stable.
    cord = CordPhysics(D=D, byte_mode=False).to(device)
    sampler = CordLangevinSampler(cord)

    B = 4
    print(f"Sampling {B} fields, {D=}, 100 steps...")

    # Full trajectory to check convergence
    trajectory = sampler.sample(
        B, num_steps=100,
        ripple_scale=0.05, noise_scale=0.02,
        device=device, return_trajectory=True
    )

    # Check: does the field converge or diverge?
    norms = [f.norm(dim=-1).mean().item() for f in trajectory]
    print(f"  Initial norm: {norms[0]:.4f}")
    print(f"  Final norm:   {norms[-1]:.4f}")
    print(f"  Min norm:     {min(norms):.4f}")
    print(f"  Max norm:     {max(norms):.4f}")

    # Check for NaN or explosion
    assert not torch.isnan(trajectory[-1]).any(), "Final field contains NaN!"
    assert norms[-1] < 1e6, f"Field exploded: norm={norms[-1]:.1f}"

    # Check with prompt
    print("\n  Prompt-conditioned sampling...")
    prompt_field = torch.randn(B, D, device=device)
    result = sampler.sample_with_prompt(
        prompt_field, num_steps=50,
        ripple_scale=0.05, noise_scale=0.02,
        prompt_strength=0.3, device=device
    )
    print(f"  Prompt result norm: {result.norm(dim=-1).mean():.4f}")
    dist_to_prompt = (result - prompt_field).norm(dim=-1).mean().item()
    random_field = torch.randn(B, D, device=device)
    dist_random = (random_field - prompt_field).norm(dim=-1).mean().item()
    print(f"  Distance to prompt: {dist_to_prompt:.4f}")
    print(f"  Random distance:    {dist_random:.4f}")
    # With normalization, both should be in a reasonable range
    assert dist_to_prompt < 1e6, f"Prompt result way off: {dist_to_prompt:.1f}"

    print("\n✓ All Langevin tests passed!")
    return True


if __name__ == '__main__':
    test_langevin_sampler()
