"""ByteLogitTreeDiffusion — tree denoiser with cross-entropy byte prediction.

Instead of MSE on continuous embeddings, this outputs byte logits [B, 1024, 256]
and trains with cross-entropy loss. The model must learn the discrete byte
distribution at each position, which is the right objective for text.

Architecture:
  - Token embeddings encode bytes → [B, 1024, 4] field
  - Add positional encoding (sinusoidal, φ-spaced)
  - TreeDiffusionCord denoises → [B, 4096]
  - Reshape to [B, 1024, 4]
  - Linear head → [B, 1024, 256] logits
  - Cross-entropy loss against ground-truth bytes

This replaces the "predict continuous embedding" objective with "predict
byte distribution" — the model can't collapse to the mean anymore.
"""

import math, torch, torch.nn as nn, torch.nn.functional as F
from cassi.tree_diffusion_cord import TreeDiffusionCord
from cassi.berry_brain import BerryMemory
from cassi.cord import PHI, PHI_INV


class ByteLogitTreeDiffusion(nn.Module):
    """Tree denoiser with byte-level cross-entropy loss and Taijitu Berry memory.

    Memory: 4-level φ-hierarchical Taijitu Berry memory (L0 11-byte → L1 7-byte
    → L2 4-byte → L3 2-byte). Each level stores PAIRED (self, next) patterns
    in a single 16-dim holographic slot. Two decompress heads per level:
    yin reads self-verification, yang reads forward-projection. Blending is
    φ-weighted: Yang leads by φ ≈ 1.618 (~62%), Yin grounds (~38%) — the same
    asymmetric equilibrium as the two-fluid bridge.

    All levels: compressed value_dim=16 (holographic bound, boundary area 2 edges),
    φ-damped EMA (PHI_INV ≈ 0.618) for plasticity. Coarse-to-fine retrieval order.
    Per-level learned weight (init 0.2–0.3) replaces dead gate networks.

    Args:
        emb_dim: embedding dimension per position (default 4)
        seq_len: sequence length (default 1024)
        num_timesteps: diffusion steps
        vocab_size: number of byte values (256)
    """
    def __init__(self, emb_dim=8, seq_len=1024, num_timesteps=1000, vocab_size=256):
        super().__init__()
        self.emb_dim = emb_dim
        self.seq_len = seq_len
        self.vocab_size = vocab_size
        self.D = seq_len * emb_dim

        # Byte encoding: φ-scaled sinusoidal manifold (Cassi-native).
        # Instead of learned embeddings that reify bytes as discrete tokens,
        # each byte value (0-255) is encoded as a point on a smooth, continuous
        # curve in ℝ^emb_dim using φ-spaced frequencies. Neighboring byte values
        # (e.g., 'A'=65, 'B'=66) map to nearby points — the model inherits a
        # natural inductive bias for byte-level continuity.
        #
        # For emb_dim=4: freqs = [π, φπ], dims = [sin(·), cos(·)] × 2 = 4
        byte_vals = torch.arange(0, vocab_size, dtype=torch.float32) / 255.0
        freqs = PHI ** torch.arange(0, emb_dim // 2, dtype=torch.float32) * math.pi
        angles = byte_vals.unsqueeze(1) * freqs.unsqueeze(0)           # [vocab, emb_dim//2]
        token_emb = torch.cat([angles.sin(), angles.cos()], dim=1)     # [vocab, emb_dim]
        self.register_buffer('token_emb', token_emb)

        # Byte salience (amplifies structural bytes)
        self.byte_salience = nn.Parameter(torch.zeros(vocab_size))
        for b in [32, 10, 13, 46, 44, 33, 63, 59, 58, 39, 34, 40, 41, 91, 93]:
            if b < vocab_size:
                self.byte_salience.data[b] = 1.0


        # Tree denoiser
        self.spine = TreeDiffusionCord(D=self.D, num_timesteps=num_timesteps)

        # Output head: embedding → logits
        self.head = nn.Sequential(
            nn.Linear(emb_dim, emb_dim * 4),
            nn.GELU(),
            nn.Linear(emb_dim * 4, vocab_size),
        )

        # Per-level output heads with learned blending (Spine3D harmony pattern)
        # Each level produces its own byte logits, softmax-blended at each position
        self.n_levels = 6  # matches compute_tree_levels(13)
        self.level_heads = nn.ModuleList([
            nn.Sequential(
                nn.Linear(emb_dim, emb_dim * 4),
                nn.GELU(),
                nn.Linear(emb_dim * 4, vocab_size),
            ) for _ in range(self.n_levels)
        ])
        # Per-level learned log-confidence (harmony) — includes root + 6 tree levels
        self.level_harmony = nn.Parameter(torch.zeros(self.n_levels + 1))
        # Per-level learned weight for Taijitu memory blend (replaces frozen scalars)
        self.level_alpha = nn.Parameter(torch.full((self.n_levels,), 0.25))



        # ── Taijitu φ-Hierarchical Berry Memory (4 levels, φ-scaled chunk sizes) ──
        # Each level stores PAIRED patterns (self, next) in a single 16-dim slot.
        # Two decompress heads per level: yin reads self-verification, yang reads
        # forward-projection. Blending is φ-weighted: Yang leads by φ ≈ 1.618.
        # No per-chunk gate networks — dead weight. Single learned weight per level.
        # All levels: compressed value_dim=16 (holographic bound), φ-damped EMA.
        # Coarse-to-fine retrieval order.

        # Reusable boundary bytes for write filtering
        self.register_buffer('_boundary_bytes',
            torch.tensor([32, 10, 13, 46, 44, 33, 63, 59, 58, 39, 34, 40, 41, 45, 95],
                         dtype=torch.uint8), persistent=False)

        # L0: Coarsest (11-byte, φ^5.0) — common phrases, collocations
        self.mem_l0_chunk = 11
        _l0_raw = self.emb_dim * 11
        self.memory_l0 = BerryMemory(
            key_dim=26, value_dim=16,
            n_slots=16384, similarity_threshold=0.85, ema_decay=PHI_INV
        )
        self.mem_l0_key = nn.Sequential(
            nn.Linear(_l0_raw, 48), nn.GELU(), nn.Linear(48, 26)
        )
        self.mem_l0_yin = nn.Linear(16, _l0_raw)            # decompress: self pattern
        self.mem_l0_ctx = nn.Linear(26 + 13, 26)   # composite: content + field_energy
        self.mem_l0_compress = nn.Linear(_l0_raw * 2, 16)   # paired (self,next) → 16
        self.mem_l0_yang = nn.Linear(16, _l0_raw)           # decompress: next pattern

        # L1: Mid (7-byte, φ^3.5) — short words, stems
        self.mem_l1_chunk = 7
        _l1_raw = self.emb_dim * 7
        self.memory_l1 = BerryMemory(
            key_dim=26, value_dim=16,
            n_slots=16384, similarity_threshold=0.90, ema_decay=PHI_INV
        )
        self.mem_l1_key = nn.Sequential(
            nn.Linear(_l1_raw, 32), nn.GELU(), nn.Linear(32, 26)
        )
        self.mem_l1_compress = nn.Linear(_l1_raw * 2, 16)
        self.mem_l1_ctx = nn.Linear(26 + 13, 26)
        self.mem_l1_yin = nn.Linear(16, _l1_raw)
        self.mem_l1_yang = nn.Linear(16, _l1_raw)

        # L2: Fine (4-byte, φ^2.1) — character trigrams, morphemes
        self.mem_l2_chunk = 4
        _l2_raw = self.emb_dim * 4
        self.memory_l2 = BerryMemory(
            key_dim=26, value_dim=16,
            n_slots=16384, similarity_threshold=0.93, ema_decay=PHI_INV
        )
        self.mem_l2_key = nn.Sequential(
            nn.Linear(_l2_raw, 16), nn.GELU(), nn.Linear(16, 26)
        )
        self.mem_l2_ctx = nn.Linear(26 + 13, 26)
        self.mem_l2_compress = nn.Linear(_l2_raw * 2, 16)
        self.mem_l2_yin = nn.Linear(16, _l2_raw)
        self.mem_l2_yang = nn.Linear(16, _l2_raw)

        # L3: Finest (2-byte, φ^1.0) — bigram transitions: "th"→"e", "qu"→"i"
        self.mem_l3_chunk = 2
        _l3_raw = self.emb_dim * 2
        self.memory_l3 = BerryMemory(
            key_dim=26, value_dim=16,
            n_slots=16384, similarity_threshold=0.96, ema_decay=PHI_INV
        )
        self.mem_l3_key = nn.Sequential(
            nn.Linear(_l3_raw, 8), nn.GELU(), nn.Linear(8, 26)
        )
        self.mem_l3_ctx = nn.Linear(26 + 13, 26)
        self.mem_l3_compress = nn.Linear(_l3_raw * 2, 16)
        self.mem_l3_yin = nn.Linear(16, _l3_raw)
        self.mem_l3_yang = nn.Linear(16, _l3_raw)

        # Ordered levels for coarse-to-fine iteration (coarsest first)
        self._mem_levels = [
            ('l0', self.mem_l0_chunk, self.memory_l0, self.mem_l0_key, self.mem_l0_ctx,
             self.mem_l0_compress, self.mem_l0_yin, self.mem_l0_yang),
            ('l1', self.mem_l1_chunk, self.memory_l1, self.mem_l1_key, self.mem_l1_ctx,
             self.mem_l1_compress, self.mem_l1_yin, self.mem_l1_yang),
            ('l2', self.mem_l2_chunk, self.memory_l2, self.mem_l2_key, self.mem_l2_ctx,
             self.mem_l2_compress, self.mem_l2_yin, self.mem_l2_yang),
            ('l3', self.mem_l3_chunk, self.memory_l3, self.mem_l3_key, self.mem_l3_ctx,
             self.mem_l3_compress, self.mem_l3_yin, self.mem_l3_yang),
        ]

    def _extract_chunks(self, emb_field, chunk_size):
        """Extract overlapping chunks with stride 4. [B*n_chunks, chunk_size*emb_dim]."""
        unfolded = emb_field.unfold(1, chunk_size, 4)  # [B, n_chunks, emb_dim, chunk_size]
        B, n_chunks = unfolded.shape[0], unfolded.shape[1]
        return unfolded.permute(0, 1, 3, 2).reshape(B * n_chunks, chunk_size * self.emb_dim), n_chunks

    def _extract_byte_chunks(self, x_bytes, chunk_size):
        """Extract overlapping byte chunks with stride 4. [B*n_chunks, chunk_size]."""
        unfolded = x_bytes.unfold(1, chunk_size, 4)  # [B, n_chunks, chunk_size]
        return unfolded.reshape(-1, chunk_size), unfolded.shape[1]

    def _positional_encoding(self, B, device):
        """Sinusoidal positional encoding with φ-escalating frequencies [1, seq_len, emb_dim].

        freq_k = φ^k · π / seq_len  for k = 0..half-1

        Slowest (k=0):     π radians over the full sequence — one global half-cycle.
        Fastest (k=half-1): φ^{half-1}·π radians — a few cycles for local structure.
        φ (~1.618) separates the scales so each frequency band captures a distinct
        level of positional granularity.
        """
        pos = torch.arange(self.seq_len, device=device).float()  # [seq_len]
        half = self.emb_dim // 2
        freqs = PHI ** torch.arange(0, half, device=device, dtype=torch.float32) * math.pi / self.seq_len
        phase = pos[:, None] * freqs[None, :]  # [seq_len, half]
        pe = torch.cat([torch.sin(phase), torch.cos(phase)], dim=-1)
        if self.emb_dim % 2 == 1:
            pe = F.pad(pe, (0, 1))
        return pe.unsqueeze(0)  # [1, seq_len, emb_dim]

    def bytes_to_field(self, x):
        """Bytes → embedding field with positional encoding."""
        B = x.shape[0]
        x = x.long().clamp(0, self.vocab_size - 1)
        embs = self.token_emb[x]  # [B, seq_len, emb_dim]
        # Apply byte salience
        salience = torch.sigmoid(self.byte_salience[x]) * 2.0
        embs = embs * salience.unsqueeze(-1)
        # Add positional encoding
        pe = self._positional_encoding(B, x.device)
        embs = embs + pe
        # Breath modulation: rhythmic amplitude envelope across positions
        # Periods φ-spaced: 29 (slow, global attention) and 7 (fast, local attention)
        pos = torch.arange(self.seq_len, device=x.device).float()
        breath = 1.0 + 0.03 * torch.sin(2 * math.pi * pos / 29.0) \
                      + 0.02 * torch.sin(2 * math.pi * pos / 7.0)
        embs = embs * breath.view(1, -1, 1)
        return embs.reshape(B, self.D)

    def field_to_logits(self, field):
        """Denoised field → byte logits per position."""
        B = field.shape[0]
        embs = field.reshape(B, self.seq_len, self.emb_dim)
        return self.head(embs)  # [B, seq_len, vocab_size]

    def forward(self, x_t, t):
        """Denoise field → byte logits with Spine3D harmony per-level blending."""
        field, level_outs = self.spine.forward_with_levels(x_t, t)  # field: [B,D], level_outs: list of 6 × [B,D]
        B = field.shape[0]
        # Learned harmony blending: softmax over levels
        harmony = F.softmax(self.level_harmony, dim=0)  # [n_levels+1]
        # Root level via existing head, weighted by harmony[0]
        logits = harmony[0] * self.field_to_logits(field)
        # Per-level heads, weighted by harmony[1:], summed iteratively
        for i, lo in enumerate(level_outs):
            lo_embs = lo.reshape(B, self.seq_len, self.emb_dim)
            logits = logits + harmony[i + 1] * self.level_heads[i](lo_embs)
        return logits

    def training_loss(self, x_bytes):
        """Cross-entropy loss: predict clean bytes from noisy embeddings.

        x_bytes: [B, seq_len] uint8
        """
        B = x_bytes.shape[0]
        # Encode clean bytes to field
        field_clean = self.bytes_to_field(x_bytes)

        # Add noise
        t = torch.randint(0, self.spine.num_timesteps, (B,), device=x_bytes.device)
        noise = torch.randn_like(field_clean)
        x_t, _ = self.spine.q_sample(field_clean, t, noise=noise)

        # Denoise and predict logits
        logits = self.forward(x_t, t)  # [B, seq_len, vocab_size]

        # --- Taijitu memory write (training only, every batch) ---
        # Store PAIRED (self, next) patterns. Yin head reads self-verification,
        # Yang head reads forward-projection. Compressed into single 16-dim slot.
        if self.training:
            with torch.no_grad():
                field_clean_est = self.spine.field_state  # [B, D]
                emb_field = field_clean_est.reshape(B, self.seq_len, self.emb_dim)
                field_energy = self.spine.field_energy[:B]  # [B, 13]
                boundary_bytes = self._boundary_bytes

                for _name, chunk_size, memory, key_proj, ctx_proj, compress, _yin, _yang in self._mem_levels:
                    # Extract self chunks with stride=4
                    chunks_self, n_chunks = self._extract_chunks(emb_field, chunk_size)
                    byte_chunks, _ = self._extract_byte_chunks(x_bytes, chunk_size)
                    # is_boundary is flat [B*n_chunks]; reshape to [B, n_chunks]
                    is_boundary = torch.isin(byte_chunks, boundary_bytes).any(dim=-1).reshape(B, n_chunks)

                    if n_chunks < 2 or not is_boundary.any():
                        continue

                    # Reshape to [B, n_chunks, raw] for positional indexing
                    raw_dim = chunk_size * self.emb_dim
                    self_2d = chunks_self.reshape(B, n_chunks, raw_dim)

                    # Next chunks: offset by 1 in chunk index
                    next_2d = self_2d[:, 1:, :]  # [B, n_chunks-1, raw]

                    # Only self chunks that have a valid successor
                    bound_self = is_boundary.clone()
                    bound_self[:, -1] = False     # last chunk has no successor

                    if not bound_self.any():
                        continue

                    b_self = self_2d[bound_self]                  # [N, raw]
                    b_next = next_2d[bound_self[:, :-1]]           # [N, raw]

                    # Composite key from self content + field_energy context
                    content_key = key_proj(b_self)                 # [N, 26]
                    fe_expanded = field_energy.unsqueeze(1).expand(-1, n_chunks, -1).reshape(B * n_chunks, 13)
                    fe_boundary = fe_expanded[bound_self.reshape(-1)]  # [N, 13]
                    keys = ctx_proj(torch.cat([content_key, fe_boundary], dim=-1))  # [N, 26]

                    # Compress paired (self, next) into single 16-dim holographic slot
                    values = compress(torch.cat([b_self.detach(), b_next.detach()], dim=-1))  # [N, 16]
                    memory.write(keys, values, mode='ema')

        # Cross-entropy against ground truth bytes
        targets = x_bytes.long().clamp(0, self.vocab_size - 1)
        logits_flat = logits.reshape(-1, self.vocab_size)
        ce = F.cross_entropy(logits_flat, targets.reshape(-1), label_smoothing=0.1)

        # Entropy bonus: reward uncertainty to prevent mode collapse.
        # λ=0.05 makes the bonus ~10% of total loss — strong enough gradient
        # pressure to resist the repeating-pattern attractor at all loss levels.
        probs = logits_flat.softmax(dim=-1)
        H = -(probs * (probs + 1e-8).log()).sum(dim=-1).mean()
        loss = ce - 0.05 * H

        return loss

    def _denoise_step(self, x_t, temperature=1.0):
        """One pass: noisy field → logits → softmax → memory → clean field prediction.

        Uses t=0 for most aggressive denoising at every Langevin step — the model
        was trained at all noise levels and learns the noisy→clean mapping.
        Memory retrieval (Taijitu, φ-blend) refines the softmax embedding.

        Returns: field [B, D]"""
        B = x_t.shape[0]
        device = x_t.device
        logits = self.forward(x_t, torch.zeros(B, device=device, dtype=torch.long))
        probs = (logits / temperature).softmax(dim=-1)
        emb_pred = probs @ self.token_emb  # [B, seq_len, emb_dim]

        # Taijitu memory retrieval: dual-headed decompress (yin/yang) +
        # φ-weighted blend. Coarser levels blend first, refining embeddings
        # that finer levels query on. Composite keys + temperature 0.1.
        field_energy = self.spine.field_energy[:B]  # [B, 13]
        for i, (_name, chunk_size, memory, key_proj, ctx_proj, _compress, yin, yang) in enumerate(self._mem_levels):
            if memory._n_filled == 0:
                continue
            chunks, n_chunks = self._extract_chunks(emb_pred, chunk_size)   # [B*n_chunks, raw]
            # Composite key: content + field_energy context
            content_key = key_proj(chunks)                                   # [B*n_chunks, 26]
            fe_expanded = field_energy.unsqueeze(1).expand(-1, n_chunks, -1).reshape(B * n_chunks, 13)
            keys = ctx_proj(torch.cat([content_key, fe_expanded], dim=-1))  # [B*n_chunks, 26]

            # Retrieve paired (self, next) from single holographic slot
            compressed, _attn = memory.query(keys, temperature=0.1, topk=64)  # [B*n_chunks, 16]

            # Dual-headed decompress: yin → self-verification, yang → forward-projection
            yin_raw = yin(compressed)     # [B*n_chunks, raw_dim] — "what I am"
            yang_raw = yang(compressed)   # [B*n_chunks, raw_dim] — "what follows"

            # Taijitu blend: Yang leads by φ ≈ 1.618 (expansive bias)
            # Yin provides grounding seed within the blend
            yin_delta = yin_raw - chunks
            yang_delta = yang_raw - chunks
            total = (PHI * yang_delta + yin_delta) / (PHI + 1.0)  # ~62% Yang, ~38% Yin
            blended = chunks + self.level_alpha[i] * total

            # Scatter overlapping chunks back into emb_pred (averaging)
            blended_rs = blended.reshape(B, n_chunks, chunk_size, self.emb_dim)
            emb_acc = torch.zeros_like(emb_pred)
            emb_cnt = torch.zeros(B, self.seq_len, 1, device=device)
            for c in range(n_chunks):
                start = c * 4
                end = start + chunk_size
                w = end - start
                emb_acc[:, start:end, :] += blended_rs[:, c, :w, :]
            emb_pred = emb_acc / emb_cnt.clamp(min=1)

        return emb_pred.reshape(B, self.D)


    @torch.no_grad()
    def sample(self, B=1, num_steps=100, temperature=1.0, noise_scale=0.02,
               ripple_scale=0.1, blend=0.3, device=None):
        """Generate bytes via Langevin dynamics (predict + refine + noise).

        Unlike DDIM (deterministic, entropy collapses to zero), Langevin dynamics
        add Gaussian noise at every step and only partially trust the denoiser,
        maintaining diversity throughout the sampling trajectory. Ripple
        perturbation explores the denoiser's own sensitivity directions.

        The blend parameter controls the predict/refine balance:
          0.0 = pure random walk (independent of denoiser)
          0.3 = default (lightly guided toward denoiser prediction)
          0.5 = strongly guided (mildly stochastic DDIM)
          1.0 = deterministic DDIM (same as before, collapse path)

        Args:
            B: batch size
            num_steps: Langevin iterations (more = cleaner but slower convergence)
            temperature: softmax temperature for the denoising step
            noise_scale: std of Langevin Gaussian noise added per step
            ripple_scale: strength of denoiser-sensitivity exploration
            blend: how much to trust the denoiser's prediction (0-1)
            device: torch device
        """
        if device is None:
            device = next(self.parameters()).device

        D = self.D
        field = torch.randn(B, D, device=device)

        for step in range(num_steps):
            # 1. Denoise: noisy field → logits → softmax → memory → clean field
            field_pred = self._denoise_step(field, temperature)

            # 2. Ripple: probe denoiser sensitivity by running it on slightly
            #    perturbed input, then taking the directional difference. This
            #    reveals which directions the denoiser is actually sensitive to
            #    — far more efficient exploration than isotropic noise.
            probe_noise = torch.randn_like(field) * (noise_scale * 0.05)
            field_probe = self._denoise_step(field + probe_noise, temperature)
            ripple = field_probe - field_pred
            ripple_norm = ripple.norm(dim=-1, keepdim=True).clamp_min(1e-8)
            ripple = ripple / ripple_norm

            # 3. Blend: move toward clean prediction while retaining current state
            field = blend * field_pred + (1.0 - blend) * field

            # 4. Explore: ripple + Langevin noise
            field = field + ripple_scale * ripple
            if noise_scale > 0.0:
                field = field + torch.randn_like(field) * noise_scale

            # 5. Normalize to prevent magnitude drift from accumulated noise
            f_norm = field.norm(dim=-1, keepdim=True).clamp_min(1e-8)
            target_scale = math.sqrt(D)  # unit variance per element → ‖field‖ ≈ √D
            field = field * (target_scale / f_norm)

        # Final decode: argmax on clean field
        final_logits = self.forward(
            field, torch.zeros(B, device=device, dtype=torch.long))
        bytes_pred = final_logits.argmax(dim=-1).to(torch.uint8)
        return bytes_pred


    @torch.no_grad()
    def generate_text(self, B=1, num_steps=100, temperature=1.0, noise_scale=0.02,
                      ripple_scale=0.1, blend=0.3, device=None):
        """Sample and decode to printable ASCII string."""
        bt = self.sample(B, num_steps=num_steps, temperature=temperature,
                         noise_scale=noise_scale, ripple_scale=ripple_scale,
                         blend=blend, device=device)
        texts = []
        for b in range(B):
            raw = bt[b].cpu().numpy()
            text = bytes([x for x in raw if 32 <= x < 127]).decode('ascii', errors='replace')
            texts.append(text)
        return texts


# ═══════════════════════════════════════════════════════════════════════════════
# Overnight training script
# ═══════════════════════════════════════════════════════════════════════════════

def train_overnight():
    import os, time, argparse
    from torch.optim.lr_scheduler import CosineAnnealingLR
    from experiments.train_langevin_text import (
        build_text_loader, sample_train_batch, sample_val_batch
    )

    # Auto-detect real GPU: skip CPU iGPU (has "Ryzen" in name) in favor of discrete GPU
    if torch.cuda.is_available():
        best_dev = 0
        best_mem = 0
        for i in range(torch.cuda.device_count()):
            name = torch.cuda.get_device_name(i)
            mem = torch.cuda.get_device_properties(i).total_memory
            if 'Ryzen' not in name and mem > best_mem:
                best_mem = mem
                best_dev = i
        DEV = f'cuda:{best_dev}'
        print(f"Auto GPU: device {best_dev} ({torch.cuda.get_device_name(best_dev)}, {best_mem/1e9:.1f}GB)")
    else:
        DEV = 'cpu'

    p = argparse.ArgumentParser()
    p.add_argument('--epochs', type=int, default=10000)
    p.add_argument('--bs', type=int, default=32)
    p.add_argument('--lr', type=float, default=3e-4)
    p.add_argument('--steps-per-epoch', type=int, default=300)
    p.add_argument('--text-dir', default='datasets/active')
    p.add_argument('--save-dir', default='checkpoints')
    p.add_argument('--resume', default=None)
    p.add_argument('--gen-every', type=int, default=50)
    p.add_argument('--patience', type=int, default=20, help='val checks without improvement before stopping (×5 epochs)')
    p.add_argument('--min-delta', type=float, default=0.001, help='minimum val loss improvement to reset patience')
    args = p.parse_args()

    os.makedirs(args.save_dir, exist_ok=True)

    model = ByteLogitTreeDiffusion(emb_dim=4, seq_len=1024, num_timesteps=100).to(DEV)
    n_p = sum(p.numel() for p in model.parameters())
    print(f"Device: {DEV}, params: {n_p:,}")
    print(f"Epochs: {args.epochs}, bs: {args.bs}, lr: {args.lr}, patience: {args.patience} val-checks, min-delta: {args.min_delta}")

    # Data
    sampler, total, n_train, n_val, val_off, tr_rng, val_rng = \
        build_text_loader(args.text_dir)
    print(f"Data: {total:,} bytes ({total/1e9:.1f} GB)")

    # Optimizer
    other_params = [p for n, p in model.named_parameters()]
    pg = [{'params': other_params, 'lr': args.lr}]
    opt = torch.optim.AdamW(pg, weight_decay=0.01)
    print(f"Optim groups: {len(other_params)} params lr={args.lr}")
    sched = CosineAnnealingLR(opt, T_max=args.epochs, eta_min=args.lr * 0.01)

    # Resume
    start_epoch = 0
    best_loss = float('inf')
    if args.resume:
        ckpt = torch.load(args.resume, map_location=DEV, weights_only=False)
        ms, cs = model.state_dict(), ckpt['model']
        for k in list(cs.keys()):
            if k in ms and cs[k].shape == ms[k].shape:
                ms[k] = cs[k]
        model.load_state_dict(ms)
        start_epoch = ckpt.get('epoch', 0)
        best_loss = ckpt.get('best_loss', float('inf'))
        best_val_loss = ckpt.get('best_val_loss', float('inf'))
        print(f"Resumed from epoch {start_epoch}, best_loss={best_loss:.4f}, best_val_loss={best_val_loss:.4f}")
    else:
        best_val_loss = float('inf')


    t_start = time.time()
    patience_counter = 0
    for ep in range(start_epoch, start_epoch + args.epochs):
        t_ep = time.time()
        tr_rng.seed(42 + ep)  # shuffle data each epoch — prevents memorization
        model.train()
        total_loss = 0.0

        for step in range(args.steps_per_epoch):
            x_bytes, _ = sample_train_batch(sampler, args.bs, tr_rng)
            x_bytes = x_bytes.to(DEV)

            opt.zero_grad()
            loss = model.training_loss(x_bytes)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            total_loss += loss.item()

        sched.step()
        avg_loss = total_loss / args.steps_per_epoch
        dt = time.time() - t_ep

        # Validation
        val_loss = None
        if ep % 5 == 0 or ep < 5:
            model.eval()
            val_total = 0.0
            with torch.no_grad():
                for _ in range(10):
                    xv, _ = sample_val_batch(sampler, args.bs, val_off, val_rng)
                    val_total += model.training_loss(xv.to(DEV)).item()
            val_loss = val_total / 10

            # Patience: track val loss improvement
            if val_loss < best_val_loss - args.min_delta:
                best_val_loss = val_loss
                patience_counter = 0
                # Save best checkpoint on val improvement (more meaningful than train)
                torch.save({'model': model.state_dict(), 'epoch': ep+1,
                           'best_loss': best_loss, 'best_val_loss': best_val_loss},
                           f"{args.save_dir}/logit_tree_best.pt")
            else:
                patience_counter += 1

        status = f"Epoch {ep+1:4d}: loss={avg_loss:.4f}"
        if val_loss is not None:
            status += f" val={val_loss:.4f} best_val={best_val_loss:.4f} p={patience_counter}/{args.patience}"
        status += f" time={dt:.0f}s"
        elapsed = time.time() - t_start
        if ep > start_epoch:
            eta = elapsed / (ep - start_epoch) * (args.epochs - ep + start_epoch)
            status += f" elapsed={elapsed/3600:.1f}h eta={eta/3600:.1f}h"
        print(status)
        for lname, lmem in [('l0', model.memory_l0), ('l1', model.memory_l1), ('l2', model.memory_l2), ('l3', model.memory_l3)]:
            if lmem._n_filled > 0:
                avg_count = lmem.counts[lmem.mask].mean().item()
                print(f"  mem_{lname}: filled={lmem._n_filled}/{lmem.n_slots} avg_count={avg_count:.1f}")

        # Log learned harmony scores and alpha weights
        if ep % 5 == 0:
            harmony_str = ' '.join(f'l{i}={v:.3f}' for i,v in enumerate(
                F.softmax(model.level_harmony, dim=0).detach().cpu().tolist()))
            alpha_str = ' '.join(f'l{i}={v:.3f}' for i,v in enumerate(
                model.level_alpha.detach().cpu().tolist()))
            print(f"  harmony: {harmony_str}")
            print(f"  alpha: {alpha_str}")

        if avg_loss < best_loss:
            best_loss = avg_loss  # still track best train loss for display

        if (ep + 1) % args.gen_every == 0:
            model.eval()
            texts = model.generate_text(B=1, device=DEV)
            t = texts[0]
            n_unique = len(set(t))
            n_printable = len(t)
            print(f"  sample [{n_unique} unique / {n_printable} chars]: {t[:150]!r}")

        # Early stopping: break if patience exceeded
        if args.patience > 0 and patience_counter >= args.patience:
            print(f"\nEarly stopping: no val improvement for {args.patience} checks")
            break

    print(f"\nDone! Best loss={best_loss:.4f} best_val={best_val_loss:.4f}")
if __name__ == '__main__':
    train_overnight()
