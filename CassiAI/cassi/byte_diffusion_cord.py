"""ByteDiffusionCord — text generation by diffusing in byte-remap space.

Uses the trained ByteEncoder's remap table to convert bytes ↔ continuous values,
then applies DiffusionCord for denoising in the 1024-dim remap space.

Architecture:
  - ByteEncoder.remap: [256] learned byte→scalar mapping
  - Bytes → remap → [B, 1024] continuous field
  - DiffusionCord (D=1024): denoises the remap field
  - Decode: argmin |field[i] - remap[b]| → byte b

Training:
  - Sample bytes, remap to continuous values
  - Add Gaussian noise → noisy remap field
  - DiffusionCord predicts clean remap field (x₀-prediction)
  - Loss: MSE in remap space
  - The ByteEncoder's remap table is frozen (pre-trained) or trainable

Generation:
  - DDIM sample from DiffusionCord → clean remap field
  - Argmin distance to remap values → bytes
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math
import numpy as np

from cassi.diffusion_cord import DiffusionCord


class ByteDiffusionCord(nn.Module):
    """Diffusion model for byte-level text generation.

    Diffuses in the ByteEncoder's remap space (1024-dim continuous).
    The remap table maps each byte (0-255) to a learned scalar value,
    creating a continuous representation that the DiffusionCord can denoise.

    Args:
        byte_encoder: pre-trained ByteEncoder (provides remap table)
        num_timesteps: diffusion steps (default: 1000)
        time_emb_dim: timestep embedding dimension
        train_remap: if True, fine-tune the remap table during diffusion training
    """

    def __init__(self, byte_encoder, num_timesteps=1000, time_emb_dim=256,
                 train_remap=True):
        super().__init__()
        self.byte_encoder = byte_encoder
        self.train_remap = train_remap

        # DiffusionCord operates in 1024-dim remap space
        self.diffusion = DiffusionCord(D=1024, num_timesteps=num_timesteps,
                                       time_emb_dim=time_emb_dim, schedule='cosine')

        # Freeze byte_encoder except remap table
        if not train_remap:
            for p in byte_encoder.parameters():
                p.requires_grad = False

    @property
    def remap(self):
        return self.byte_encoder.remap

    def bytes_to_remap(self, x):
        """Convert uint8 bytes [B, 1024] to remap values [B, 1024]."""
        return self.remap[x.long()]

    def remap_to_bytes(self, field, temperature=1.0):
        """Convert remap field [B, 1024] back to uint8 bytes.

        For each position, finds the byte whose remap value is closest
        to the field value. Uses temperature for stochastic sampling.
        """
        remap_vals = self.remap.detach()  # [256]
        B, D = field.shape

        # Distance from each field element to each byte's remap value
        # field: [B, D] → [B, D, 1]; remap_vals: [256] → [1, 1, 256]
        diff = field.unsqueeze(-1) - remap_vals.view(1, 1, -1)  # [B, D, 256]
        dist = diff.abs()  # [B, D, 256]

        if temperature > 0 and temperature != 1.0:
            # Softmin with temperature
            weights = (-dist / temperature).softmax(dim=-1)  # [B, D, 256]
            # Weighted sample
            probs = weights
            bytes_pred = torch.multinomial(probs.view(-1, 256), 1).view(B, D)
        else:
            bytes_pred = dist.argmin(dim=-1)  # [B, D]

        return bytes_pred.to(torch.uint8)

    def forward(self, x_t, t):
        """Predict clean remap field from noisy one.

        x_t: [B, 1024] noisy remap field
        t: [B] timesteps
        Returns: x0_pred [B, 1024]
        """
        return self.diffusion(x_t, t)

    def training_loss(self, x_bytes, noise_level=None):
        """Training loss on a batch of byte windows.

        x_bytes: [B, 1024] uint8 byte windows
        noise_level: optional override for the noise schedule
        Returns: scalar MSE loss
        """
        # Convert bytes to remap field
        x_remap = self.bytes_to_remap(x_bytes)  # [B, 1024]
        return self.diffusion.training_loss(x_remap)

    @torch.no_grad()
    def sample_bytes(self, B, num_steps=100, temperature=1.0, device=None):
        """Generate a byte window [B, 1024] via DDIM sampling.

        Args:
            B: batch size
            num_steps: DDIM steps
            temperature: decoding temperature (1.0 = argmax, >1 = more random)
            device: torch device

        Returns: uint8 tensor [B, 1024]
        """
        if device is None:
            device = next(self.parameters()).device

        # Sample clean remap field
        field = self.diffusion.sample_ddim(
            (B, 1024), num_steps=num_steps, eta=0.0, device=device
        )

        # Decode to bytes
        return self.remap_to_bytes(field, temperature=temperature)

    @torch.no_grad()
    def generate_text(self, B=1, num_steps=100, temperature=0.8, device=None,
                      method='ddim'):
        """Generate text. method: 'ddim' (fast) or 'langevin' (diverse).

        Returns: list of strings
        """
        if method == 'langevin':
            from cassi.cord_langevin import DiffusionCordLangevin
            sampler = DiffusionCordLangevin(self.diffusion, t_fixed=0)
            field = sampler.sample(B, num_steps=num_steps,
                                   ripple_scale=0.1, noise_scale=0.05,
                                   device=device, temperature=temperature)
            bytes_tensor = self.remap_to_bytes(field, temperature=temperature)
        else:
            bytes_tensor = self.sample_bytes(B, num_steps=num_steps,
                                             temperature=temperature, device=device)
        texts = []
        for b in range(B):
            raw = bytes_tensor[b].cpu().numpy()
            text = bytes([x for x in raw if 32 <= x < 127]).decode('ascii', errors='replace')
            texts.append(text)
        return texts
    @torch.no_grad()
    def continue_text(self, prompt_bytes, num_steps=100, temperature=0.8,
                      prompt_strength=0.7, device=None):
        """Continue a text prompt via diffusion inpainting.

        The prompt bytes are fixed; the model denoises only the unprompted
        portion, then blends back toward the prompt.

        prompt_bytes: bytes or uint8 tensor [1024]
        Returns: uint8 tensor [1, 1024]
        """
        if device is None:
            device = next(self.parameters()).device

        if isinstance(prompt_bytes, bytes):
            prompt_bytes = torch.tensor(list(prompt_bytes), dtype=torch.uint8)
        prompt_bytes = prompt_bytes.to(device)
        if prompt_bytes.dim() == 1:
            prompt_bytes = prompt_bytes.unsqueeze(0)
        B, L = prompt_bytes.shape
        if L < 1024:
            prompt_bytes = F.pad(prompt_bytes, (0, 1024 - L), value=32)  # pad with space
        prompt_bytes = prompt_bytes[:, :1024]

        # Encode prompt to remap space
        prompt_remap = self.bytes_to_remap(prompt_bytes)

        # Sample from diffusion, anchored to prompt
        step_indices = self.diffusion._subsample_steps(num_steps)
        x_t = torch.randn(B, 1024, device=device)

        for i, t_idx in enumerate(step_indices):
            t = torch.full((B,), t_idx, device=device, dtype=torch.long)
            t_prev = step_indices[i + 1] if i + 1 < len(step_indices) else -1

            x0_pred = self.diffusion(x_t, t)

            # Blend prediction with prompt
            x0_pred = prompt_strength * prompt_remap + (1 - prompt_strength) * x0_pred

            if t_prev >= 0:
                alpha_cumprod = self.diffusion.alphas_cumprod[t_idx]
                alpha_cumprod_prev = self.diffusion.alphas_cumprod[t_prev]

                # DDIM step from x0_pred
                eps_pred = (x_t - torch.sqrt(alpha_cumprod) * x0_pred) / \
                           torch.sqrt(1.0 - alpha_cumprod + 1e-8)
                sigma_t = 0.0  # deterministic DDIM
                pred_dir = torch.sqrt(1.0 - alpha_cumprod_prev - sigma_t**2 + 1e-8) * eps_pred
                x_t = torch.sqrt(alpha_cumprod_prev) * x0_pred + pred_dir
            else:
                x_t = x0_pred

        return self.remap_to_bytes(x_t, temperature=temperature)


# ═══════════════════════════════════════════════════════════════════════════════
# Training helper
# ═══════════════════════════════════════════════════════════════════════════════

def train_byte_diffusion(model, loader, optimizer, args, epoch):
    """Train ByteDiffusionCord for one epoch."""
    model.train()
    total_loss = 0.0
    n_batches = 0

    for step in range(args.steps_per_epoch):
        x, y = loader.sample_train_batch(args.bs)
        x = x.to(next(model.parameters()).device)
        loss = model.training_loss(x)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        total_loss += loss.item()
        n_batches += 1

        if step % 50 == 0:
            print(f"  [{epoch+1}/{args.epochs}] step {step:4d}/{args.steps_per_epoch}  "
                  f"loss={loss.item():.4f}")

    return total_loss / max(1, n_batches)
