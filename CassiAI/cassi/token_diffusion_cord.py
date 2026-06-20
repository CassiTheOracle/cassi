"""TokenDiffusionCord — text generation via diffusion on token embeddings.

Replaces the byte→scalar remap with byte→vector embeddings. Each of the
256 byte values gets a learned embedding vector (e.g. 4-dim), so the
diffusion operates in a 1024×4 = 4096-dimensional space where the model
can learn relationships between bytes (e.g., 'e' ≈ 'E', space ≈ tab).

This is the minimal change from ByteDiffusionCord that gives the biggest
quality improvement: same architecture, same training, but vector
embeddings instead of independent scalars.

Architecture:
  - token_emb: [256, emb_dim] learned byte→vector mapping
  - Bytes → embeddings → [B, 1024 * emb_dim] continuous field
  - DiffusionCord (D=1024*emb_dim): denoises the embedding field
  - Decode: per position, max cosine similarity to token embeddings → byte
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

from cassi.diffusion_cord import DiffusionCord


class TokenDiffusionCord(nn.Module):
    """Diffusion model using learned token embeddings instead of byte scalars.

    Args:
        vocab_size: number of byte values (256)
        emb_dim: embedding dimension per position (4 = 4096 total for 1024 positions)
        num_timesteps: diffusion steps
        time_emb_dim: timestep embedding dimension
    """

    def __init__(self, vocab_size=256, emb_dim=4, seq_len=1024,
                 num_timesteps=1000, time_emb_dim=256):
        super().__init__()
        self.vocab_size = vocab_size
        self.emb_dim = emb_dim
        self.seq_len = seq_len
        self.D = seq_len * emb_dim  # total field dimension

        # Learned byte embeddings [vocab_size, emb_dim]
        self.token_emb = nn.Parameter(torch.randn(vocab_size, emb_dim) * 0.1)

        # Learned per-byte salience: amplifies structural bytes
        # so chakras can use them as natural grouping boundaries
        self.byte_salience = nn.Parameter(torch.zeros(vocab_size))
        # Bias spaces and punctuation to start amplified
        for b in [32, 10, 13, 46, 44, 33, 63, 59, 58, 39, 34, 40, 41, 91, 93]:
            if b < vocab_size:
                self.byte_salience.data[b] = 1.0

        # DiffusionCord operates on the flattened embedding field
    def bytes_to_field(self, x):
        """Convert uint8 bytes [B, seq_len] to embedding field [B, D].

        Each byte maps to its embedding vector; all positions are concatenated.
        """
        B = x.shape[0]
        x = x.long().clamp(0, self.vocab_size - 1)
        embs = self.token_emb[x]  # [B, seq_len, emb_dim]
        # Boost structural bytes (space, punct) so chakras can use them as boundaries
        salience = torch.sigmoid(self.byte_salience[x.long()]) * 2.0  # [B, seq_len]
        embs = embs * salience.unsqueeze(-1)
        return embs.reshape(B, self.D)

    def field_to_bytes(self, field, temperature=1.0):
        """Convert embedding field [B, D] back to uint8 bytes.

        For each position, compute cosine similarity between the field slice
        and each token's embedding. Higher temperature = more random sampling.
        """
        B = field.shape[0]
        # Reshape to [B, seq_len, emb_dim]
        embs = field.reshape(B, self.seq_len, self.emb_dim)

        # Normalize for cosine similarity
        embs_norm = F.normalize(embs, dim=-1)  # [B, seq_len, emb_dim]
        tok_norm = F.normalize(self.token_emb, dim=-1)  # [vocab_size, emb_dim]

        # Cosine similarity: [B, seq_len, vocab_size]
        sim = torch.einsum('bse,ve->bsv', embs_norm, tok_norm)

        if temperature > 0 and temperature != 1.0:
            probs = (sim / temperature).softmax(dim=-1)
            bytes_pred = torch.multinomial(probs.reshape(-1, self.vocab_size), 1)
            bytes_pred = bytes_pred.reshape(B, self.seq_len)
        else:
            bytes_pred = sim.argmax(dim=-1)

        return bytes_pred.to(torch.uint8)

    def forward(self, x_t, t):
        """Predict clean field from noisy one."""
        return self.diffusion(x_t, t)

    def training_loss(self, x_bytes):
        """Training loss on byte windows."""
        field = self.bytes_to_field(x_bytes)
        return self.diffusion.training_loss(field)

    @torch.no_grad()
    def sample_bytes(self, B, num_steps=100, temperature=1.0, device=None):
        """Generate byte window via DDIM."""
        if device is None:
            device = next(self.parameters()).device
        field = self.diffusion.sample_ddim(
            (B, self.D), num_steps=num_steps, eta=0.0, device=device
        )
        return self.field_to_bytes(field, temperature=temperature)

    @torch.no_grad()
    def generate_text(self, B=1, num_steps=100, temperature=0.8, device=None,
                      method='ddim'):
        """Generate text. method: 'ddim' or 'langevin'."""
        if method == 'langevin':
            from cassi.cord_langevin import DiffusionCordLangevin
            sampler = DiffusionCordLangevin(self.diffusion, t_fixed=0)
            field = sampler.sample(B, num_steps=num_steps,
                                   ripple_scale=0.1, noise_scale=0.05,
                                   device=device, temperature=temperature)
            bytes_tensor = self.field_to_bytes(field, temperature=temperature)
        else:
            bytes_tensor = self.sample_bytes(B, num_steps=num_steps,
                                             temperature=temperature, device=device)
        texts = []
        for b in range(B):
            raw = bytes_tensor[b].cpu().numpy()
            text = bytes([x for x in raw if 32 <= x < 127]).decode('ascii', errors='replace')
            texts.append(text)
        return texts


# ═══════════════════════════════════════════════════════════════════════════════
# Training script integration
# ═══════════════════════════════════════════════════════════════════════════════

def train_token_diffusion(model, loader, optimizer, args, epoch):
    """Train TokenDiffusionCord for one epoch."""
    model.train()
    total_loss = 0.0

    for step in range(args.steps_per_epoch):
        x, y = loader.sample_train_batch(args.bs)
        x = x.to(next(model.parameters()).device)

        optimizer.zero_grad()
        loss = model.training_loss(x)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        total_loss += loss.item()

        if step % 50 == 0:
            print(f"  [{epoch+1}/{args.epochs}] step {step:4d}/{args.steps_per_epoch}  "
                  f"loss={loss.item():.4f}")

    return total_loss / max(1, args.steps_per_epoch)
