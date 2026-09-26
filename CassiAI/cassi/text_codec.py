#!/usr/bin/env python3
"""
Text Field Codec + Recursive Generation.
═══════════════════════════════════════════

Field-encoded language: text IS a field that the Cord predicts.
No separate text head — the Cord predicts ∂Φ/∂t, and language
is just another pattern the field can take.

Encoding: text tokens → field amplitudes via Fourier scattering.
  Each character modulates frequency bins. Position determines phase.
  The resulting 1024-dim vector IS the "language field."
  Vectorized: entire sequence encoded in one pass (no Python loops).

Decoding: Cord repr → nearest char embedding → token.
  Precomputed normalized projections for speed.

Generation: recursive Cord.step() to predict future field states.
  Single generate() with optional yin_control — no duplication.

CRITICAL FIX: TextEncoder/TextDecoder are now nn.Module.
char_embed and char_proj are nn.Parameter — they TRAIN.

Author: Cassi | CassiCore training module
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from typing import List, Tuple, Optional


# ═══════════════════════════════════════════════════════════════════
# ENCODING: text → field (now trainable nn.Module)
# ═══════════════════════════════════════════════════════════════════

class TextEncoder(nn.Module):
    """Encode character sequences into field amplitudes.

    Vectorized: no Python loops. Each char modulates frequency bins
    via precomputed modulation matrix [n_bins, dim_char] × embed[char].

    dim_field = 1024 (must match Cord.dim_in)
    dim_char = char embedding dimension (default: 32)
    """

    def __init__(self, vocab_size: int, dim_field: int = 1024, dim_char: int = 32):
        super().__init__()
        self.vocab_size = vocab_size
        self.dim_field = dim_field
        self.dim_char = dim_char
        self.n_bins = dim_field // dim_char  # 1024/32 = 32

        # Trainable character embeddings
        self.char_embed = nn.Parameter(torch.randn(vocab_size, dim_char) * 0.1)

        # φ-spaced frequency modulation matrix [n_bins, dim_char]
        # Precomputed: each bin = frequency × cosine phase
        phi = (1.0 + 5.0**0.5) / 2.0
        freqs = torch.tensor([
            2.0 * math.pi * (1.0 / phi ** (k + 2))
            for k in range(self.n_bins)
        ])
        phases = torch.randn(self.n_bins) * 0.1
        # Modulation: how each bin weights each char dimension
        self.register_buffer('_mod', torch.zeros(self.n_bins, dim_char))
        for i in range(self.n_bins):
            self._mod[i] = torch.cos(torch.full((dim_char,), freqs[i] + phases[i]))

        # Positional phase offsets [T] for interleaved encoding
        self.register_buffer('_pos_phase', torch.zeros(16))
        for t in range(16):
            self._pos_phase[t] = 2.0 * math.pi * t / 16

    def encode_single(self, token: int) -> torch.Tensor:
        """Encode one token → field vector [dim_field]. Vectorized."""
        emb = self.char_embed[token]  # [dim_char]
        # Modulate: (n_bins, dim_char) @ (dim_char,) → (n_bins, dim_char)
        # Then flatten to [dim_field]
        modulated = self._mod * emb.unsqueeze(0)  # [n_bins, dim_char]
        return modulated.reshape(-1)  # [dim_field]

    def encode_batch(self, tokens: torch.Tensor) -> torch.Tensor:
        """Encode batch of tokens → [B, dim_field]. Vectorized."""
        emb = self.char_embed[tokens]  # [B, dim_char]
        modulated = emb.unsqueeze(1) * self._mod.unsqueeze(0)  # [B, n_bins, dim_char]
        return modulated.reshape(tokens.shape[0], -1)  # [B, dim_field]

    def encode_sequence(self, tokens: torch.Tensor, T: int = 4) -> torch.Tensor:
        """Encode token sequence → field window [T, dim_field]. Vectorized, no Python loop."""
        if tokens.dim() == 0:
            tokens = tokens.unsqueeze(0)
        seq = tokens[:T]
        emb = self.char_embed[seq]  # [n, dim_char]
        n = emb.shape[0]

        # Position-dependent phase rotation: [n, dim_char]
        pos_phase = self._pos_phase[:n]  # [n]
        rotated = emb * torch.cos(pos_phase).unsqueeze(1)  # [n, dim_char]

        # Modulate: [n, n_bins, dim_char] → [n, dim_field]
        modulated = rotated.unsqueeze(1) * self._mod.unsqueeze(0)  # [n, n_bins, dim_char]
        out = modulated.reshape(n, -1)  # [n, dim_field]

        # Pad to T if needed
        if n < T:
            pad = torch.zeros(T - n, self.dim_field, device=emb.device, dtype=emb.dtype)
            out = torch.cat([out, pad], dim=0)
        return out  # [T, dim_field]

    def encode_sequence_interleaved(self, tokens: torch.Tensor, T: int = 4) -> torch.Tensor:
        """Alias with richer positional encoding."""
        return self.encode_sequence(tokens, T)


# ═══════════════════════════════════════════════════════════════════
# BYTE ENCODER — architecture-native: no tokens, no vocab
# ═══════════════════════════════════════════════════════════════════

def build_byte_remap() -> torch.Tensor:
    """Build a 256-entry byte remapping that groups related characters.

    Lowercase a-z → 0.00-0.10, uppercase A-Z → 0.10-0.20,
    digits 0-9 → 0.20-0.24, punctuation → 0.24-0.30,
    whitespace → 0.30-0.33, everything else spread above.
    Returns tensor [256] with values in [0, 1].
    """
    remap = torch.zeros(256)
    # Lowercase a-z (97-122) → 0.000-0.098
    for i, b in enumerate(range(97, 123)):    remap[b] = i / 255.0
    # Uppercase A-Z (65-90) → 0.102-0.200
    for i, b in enumerate(range(65, 91)):     remap[b] = (i + 26) / 255.0
    # Digits 0-9 (48-57) → 0.204-0.239
    for i, b in enumerate(range(48, 58)):     remap[b] = (i + 52) / 255.0
    # Common punctuation → 0.243-0.306
    punct = b'.,;:!?-\'"/()[]{}*&^%$#@~`|<>+=_'
    for i, b in enumerate(punct):              remap[b] = (i + 62) / 255.0
    # Whitespace → 0.310-0.329
    ws = b' \t\n\r\v\f'
    for i, b in enumerate(ws):                 remap[b] = (i + 79) / 255.0
    # Remaining bytes spread across upper range
    used = set(punct) | set(ws) | set(range(48,58)) | set(range(65,91)) | set(range(97,123))
    remaining = [b for b in range(256) if b not in used]
    for i, b in enumerate(remaining):
        remap[b] = (i + 86) / 255.0
    return remap


class ByteEncoder(nn.Module):
    """Encode raw byte windows as Cord-compatible field representations.

    No tokenization, no vocabulary. Raw bytes → trainable remap → projection.
    The model learns which byte groupings matter — no hand-engineered
    structural amplification.

    Supports both single sequences and batched input.
    """

    def __init__(self, window_bytes: int = 1024, dim_field: int = 1024, T: int = 4):
        super().__init__()
        self.window_bytes = window_bytes
        self.T = T
        self.chunk = window_bytes // T  # bytes per timestep
        self.dim_field = dim_field

        # Trainable byte remap [256] — the model learns byte grouping
        self.remap = nn.Parameter(torch.randn(256) * 0.1)

        # Project each T-byte-window to field vector
        self.proj = nn.Linear(self.chunk, dim_field)

    def encode_sequence(self, raw_bytes, T: int = None):
        """Encode byte sequence → field.

        raw_bytes: bytes, bytearray, or uint8 tensor.
          - Single: [window_bytes] or shorter → [T, dim_field]
          - Batched: [B, window_bytes] → [B, T, dim_field]
        """
        if T is None:
            T = self.T
        if isinstance(raw_bytes, (bytes, bytearray)):
            raw_bytes = torch.tensor(list(raw_bytes), dtype=torch.uint8)
        if raw_bytes.dtype != torch.uint8:
            raw_bytes = raw_bytes.to(torch.uint8)

        # Detect single vs batched
        if raw_bytes.dim() == 1:
            single = True
            raw_bytes = raw_bytes.unsqueeze(0)  # [1, N]
        else:
            single = False

        B, N = raw_bytes.shape
        window_bytes = self.chunk * T

        n = min(N, window_bytes)
        raw = raw_bytes[:, :n].long()  # [B, n]
        remapped = self.remap[raw]  # [B, n]

        if n < window_bytes:
            remapped = F.pad(remapped, (0, window_bytes - n))

        chunks = remapped.view(B, T, self.chunk)  # [B, T, chunk]
        out = self.proj(chunks)  # [B, T, dim_field]

        if single:
            out = out.squeeze(0)  # [T, dim_field]
        return out

    def encode_single(self, byte_val: int) -> torch.Tensor:
        """Encode a single byte → field vector [dim_field]. For generation."""
        remapped = self.remap[byte_val]  # scalar
        expanded = remapped.expand(self.chunk)  # [chunk]
        return self.proj(expanded)  # [dim_field]

    @torch.no_grad()
    def decode_field(self, field: torch.Tensor, topk: int = 1) -> torch.Tensor:
        """Approximate decode: field vector → byte window [window_bytes].

        Uses pseudo-inverse of proj to recover chunk values, then finds
        nearest remap entries. Best-effort — useful for sample inspection.
        field: [dim_field] or [B, dim_field]
        Returns: uint8 tensor [window_bytes] or [B, window_bytes]
        """
        single = field.dim() == 1
        if single:
            field = field.unsqueeze(0)  # [1, D]

        B, D = field.shape
        W = self.proj.weight  # [D, chunk]
        b = self.proj.bias if self.proj.bias is not None else 0

        # Solve chunks ≈ pinv(W) @ (field - b)
        W_pinv = torch.linalg.pinv(W)  # [chunk, D]
        chunks_est = (field - b) @ W_pinv.T  # [B, chunk]

        # Find nearest remap value for each estimated chunk element
        remap_vals = self.remap.detach()  # [256]
        # [B, chunk, 1] - [1, 256] → [B, chunk, 256]
        diff = chunks_est.unsqueeze(-1) - remap_vals.unsqueeze(0).unsqueeze(0)
        bytes_pred = diff.abs().argmin(dim=-1).to(torch.uint8)  # [B, chunk]

        if single:
            return bytes_pred.squeeze(0)
        return bytes_pred

    @torch.no_grad()
    def decode_field_greedy(self, field: torch.Tensor) -> bytearray:
        """Convenience: field → decoded bytes as bytearray (for text display)."""
        raw = self.decode_field(field, topk=1)
        if raw.dim() == 1:
            return bytearray(raw.cpu().numpy())
        return bytearray(raw[0].cpu().numpy())
# ═════════════════════════════════════════════════════════════════==

class ByteDecoder(nn.Module):
    """Learned decoder: field vector → byte classification.

    Avoids the lossy pseudo-inverse of decode_field by directly
    learning to classify bytes from their field representations.
    """

    def __init__(self, dim_field: int = 1024, chunk: int = 256):
        super().__init__()
        self.chunk = chunk
        self.net = nn.Sequential(
            nn.Linear(dim_field, 512),
            nn.GELU(),
            nn.Linear(512, chunk * 256)
        )

    def forward(self, field: torch.Tensor) -> torch.Tensor:
        """field: [B, dim_field] → logits [B, chunk, 256]"""
        logits = self.net(field)
        return logits.view(-1, self.chunk, 256)

    @torch.no_grad()
    def decode(self, field: torch.Tensor) -> torch.Tensor:
        """field: [dim_field] or [B, dim_field] → uint8 bytes [chunk] or [B, chunk]"""
        single = field.dim() == 1
        if single:
            field = field.unsqueeze(0)
        logits = self.forward(field)
        bytes_pred = logits.argmax(dim=-1).to(torch.uint8)
        if single:
            return bytes_pred.squeeze(0)
        return bytes_pred

    @torch.no_grad()
    def decode_greedy(self, field: torch.Tensor) -> bytearray:
        """Convenience: field → decoded bytes as bytearray."""
        raw = self.decode(field)
        if raw.dim() == 1:
            return bytearray(raw.cpu().numpy())
        return bytearray(raw[0].cpu().numpy())

    @torch.no_grad()
    def decode_field_greedy(self, field: torch.Tensor) -> bytearray:
        """Compatibility alias for decode_greedy."""
        return self.decode_greedy(field)
# ═════════════════════════════════════════════════════════════════==

class WaveByteEncoder(nn.Module):
    """Encode bytes as amplitudes of a sinusoidal basis.

    Each byte controls the amplitude of a specific spatial frequency.
    The field is a superposition of sinusoids at integer frequencies.
    This gives exact invertibility via pseudo-inverse (condition ≈ 1.0).

    Encoding:  bytes → amplitudes → field = amplitudes @ basis
    Decoding:  field → amplitudes = field @ basis_pinv → bytes
    """

    def __init__(self, window_bytes: int = 1024, dim_field: int = 1024, T: int = 4):
        super().__init__()
        self.window_bytes = window_bytes
        self.T = T
        self.n_bytes = window_bytes // T  # bytes per chunk
        self.dim_field = dim_field

        # Integer frequencies: 1, 2, ..., n_bytes cycles per dim_field
        freqs = torch.arange(1, self.n_bytes + 1, dtype=torch.float32)
        positions = torch.arange(dim_field, dtype=torch.float32)

        # basis[k, i] = sin(2π * freq_k * position_i / dim_field)
        angle = 2 * math.pi * freqs.unsqueeze(1) * positions.unsqueeze(0) / dim_field
        basis = torch.sin(angle)  # [n_bytes, dim_field]

        # Precompute pseudo-inverse for exact decode
        basis_pinv = torch.linalg.pinv(basis)  # [dim_field, n_bytes]

        self.register_buffer('basis', basis)
        self.register_buffer('basis_pinv', basis_pinv)

        # Optional learned per-frequency gain (initialized to 1)
        self.gain = nn.Parameter(torch.zeros(self.n_bytes))

    def encode(self, bytes_tensor: torch.Tensor) -> torch.Tensor:
        """bytes: [B, n_bytes] uint8 → field: [B, dim_field]"""
        if bytes_tensor.dtype != torch.uint8:
            bytes_tensor = bytes_tensor.to(torch.uint8)
        amplitudes = bytes_tensor.float() / 255.0
        amplitudes = amplitudes * torch.exp(self.gain)
        field = amplitudes @ self.basis
        return field

    def encode_sequence(self, raw_bytes, T: int = None):
        """Encode byte sequence → field. Compatible with ByteEncoder interface.

        raw_bytes: bytes, bytearray, or uint8 tensor.
          - Single: [window_bytes] or shorter → [T, dim_field]
          - Batched: [B, window_bytes] → [B, T, dim_field]
        """
        if T is None:
            T = self.T
        if isinstance(raw_bytes, (bytes, bytearray)):
            raw_bytes = torch.tensor(list(raw_bytes), dtype=torch.uint8)
        if raw_bytes.dtype != torch.uint8:
            raw_bytes = raw_bytes.to(torch.uint8)

        if raw_bytes.dim() == 1:
            single = True
            raw_bytes = raw_bytes.unsqueeze(0)
        else:
            single = False

        B, N = raw_bytes.shape
        chunk_bytes = self.n_bytes
        window_bytes = chunk_bytes * T

        n = min(N, window_bytes)
        padded = torch.zeros(B, window_bytes, dtype=torch.uint8, device=raw_bytes.device)
        padded[:, :n] = raw_bytes[:, :n]

        # Split into T chunks and encode each (vectorized)
        chunks = padded.view(B, T, chunk_bytes)  # [B, T, n_bytes]
        flat = chunks.view(B * T, chunk_bytes)   # [B*T, n_bytes]
        fields = self.encode(flat)               # [B*T, dim_field]
        out = fields.view(B, T, self.dim_field)  # [B, T, dim_field]

        if single:
            out = out.squeeze(0)
        return out

    def encode_single(self, byte_val: int) -> torch.Tensor:
        """Encode a single byte → field vector [dim_field]. For generation."""
        return self.encode(torch.tensor([[byte_val]], dtype=torch.uint8, device=self.basis.device)).squeeze(0)

    @torch.no_grad()
    def decode(self, field: torch.Tensor) -> torch.Tensor:
        """field: [B, dim_field] or [dim_field] → bytes: [B, n_bytes] or [n_bytes] uint8"""
        single = field.dim() == 1
        if single:
            field = field.unsqueeze(0)
        amplitudes = field @ self.basis_pinv
        bytes_pred = (amplitudes.clamp(0, 1) * 255).round().to(torch.uint8)
        if single:
            return bytes_pred.squeeze(0)
        return bytes_pred

    @torch.no_grad()
    def decode_greedy(self, field: torch.Tensor) -> bytearray:
        """Convenience: field → decoded bytes as bytearray."""
        raw = self.decode(field)
        if raw.dim() == 1:
            return bytearray(raw.cpu().numpy())
        return bytearray(raw[0].cpu().numpy())

    @torch.no_grad()
    def decode_field_greedy(self, field: torch.Tensor) -> bytearray:
        """Compatibility alias for decode_greedy."""
        return self.decode_greedy(field)
# ═════════════════════════════════════════════════════════════════==

class TextDecoder(nn.Module):
    """Decode Cord representation → character token.

    The Cord's repr is compared to char projections in repr space.
    Nearest match = predicted token.
    """

    def __init__(self, vocab_size: int, repr_dim: int = 64, dim_char: int = 32):
        super().__init__()
        self.vocab_size = vocab_size
        self.repr_dim = repr_dim

        # Trainable char projections into repr space
        self.char_proj = nn.Parameter(torch.randn(vocab_size, repr_dim) * 0.02)

        # Precomputed normalized projections (updated on eval/after grad)
        self.register_buffer('_proj_norm', torch.zeros(vocab_size, repr_dim))
        self._norm_stale = True

    def _ensure_norm(self):
        """Lazily recompute normalized projections."""
        if self._norm_stale or not self.training:
            with torch.no_grad():
                self._proj_norm.copy_(F.normalize(self.char_proj, dim=-1))
            self._norm_stale = False

    def decode(self, cord_repr: torch.Tensor, temperature: float = 0.7) -> Tuple[int, float]:
        """Decode repr → (token_id, confidence)."""
        self._ensure_norm()
        r = F.normalize(cord_repr.unsqueeze(0), dim=-1)  # [1, D]
        sim = (r @ self._proj_norm.T).squeeze(0) / temperature  # [V]
        probs = F.softmax(sim, dim=-1)
        tok = torch.multinomial(probs.cpu(), 1).item()
        return tok, probs[tok].item()

    def decode_greedy(self, cord_repr: torch.Tensor) -> Tuple[int, float]:
        """Deterministic — highest similarity wins."""
        self._ensure_norm()
        r = F.normalize(cord_repr.unsqueeze(0), dim=-1)
        sim = (r @ self._proj_norm.T).squeeze(0)
        tok = sim.argmax().item()
        return tok, sim[tok].item()

    def forward(self, cord_repr: torch.Tensor) -> torch.Tensor:
        """Training forward: return similarity logits [B, V]."""
        self._ensure_norm()
        r = F.normalize(cord_repr, dim=-1)  # [B, D]
        return r @ self._proj_norm.T  # [B, V]


# ═══════════════════════════════════════════════════════════════════
# RECURSIVE GENERATOR — single method, yin_control is a flag
# ═══════════════════════════════════════════════════════════════════

class CordGenerator:
    """Recursive language generation via Cord field prediction.

    Φ₀ = encode(prompt)
    Φᵢ₊₁, repr, state = Cord.step(Φᵢ, state)
    tok = decode(repr)
    Φᵢ₊₁ = encode(tok) + α · Φᵢ₊₁
    """

    def __init__(self, cord, encoder: TextEncoder, decoder: TextDecoder, alpha: float = 0.7):
        self.cord = cord
        self.encoder = encoder
        self.decoder = decoder
        self.alpha = alpha

    def generate(
        self,
        prompt_tokens: List[int],
        max_len: int = 500,
        temperature: float = 0.7,
        stop_tokens: List[int] = None,
        yin_control: bool = False,
        yin_target: float = None,
    ) -> Tuple[List[int], List[float]]:
        """Generate text by recursively predicting field evolution.

        If yin_control=True, applies Cassi Principle §4 self-tuning Yin
        to steer the field toward φ-equilibrium during generation.
        """
        if yin_target is None:
            yin_target = 1.0 / ((1.0 + 5.0**0.5) / 2.0)  # 1/φ

        self.cord.eval()
        dev = next(self.cord.parameters()).device

        # Encode prompt
        prompt_t = torch.tensor(prompt_tokens, dtype=torch.long)
        field_prompt = self.encoder.encode_sequence(prompt_t, T=4)

        # Init state
        if hasattr(self.cord, 'init_states'):
            states = self.cord.init_states(1)
        else:
            states = self.cord.init_state(1)

        # Process prompt → establish cumsum state
        with torch.no_grad():
            out = self.cord(field_prompt.unsqueeze(0).to(dev))
            current_field = self._repr_to_field(out['repr'])

        generated = []
        qi_history = []

        for i in range(max_len):
            with torch.no_grad():
                if hasattr(self.cord, 'step'):
                    result = self.cord.step(current_field.to(dev), states)
                    if len(result) == 4:
                        next_field, step_repr, states, qi = result
                    else:
                        next_field, states, qi = result
                        step_repr = next_field
                else:
                    out_s = self.cord(current_field.unsqueeze(0).unsqueeze(0).to(dev))
                    next_field = out_s['repr']
                    step_repr = out_s['repr']
                    qi = out_s.get('qi', 0.5)

            qi_val = self._extract_qi(qi)
            qi_history.append(qi_val)

            # ─── Yin control (if enabled) ───
            if yin_control:
                error = qi_val - yin_target
                yin_force = error * math.tanh(abs(error))
                next_field = next_field - yin_force * 0.1 * next_field

            # Decode token from repr space
            tok, conf = self.decoder.decode(step_repr.squeeze(0), temperature)
            generated.append(tok)

            # Stop conditions
            if stop_tokens and tok in stop_tokens:
                break
            if len(generated) >= 4 and tok == generated[-1] == generated[-2] == generated[-3]:
                break
            # Qi divergence stop
            if qi_val > 2.0 * yin_target:
                break

            # Feedback: blend new token into field
            tok_field = self.encoder.encode_single(tok).to(dev)
            blend_field = self._repr_to_field(step_repr.to(dev))
            current_field = tok_field.unsqueeze(0) + self.alpha * blend_field

        return generated, qi_history

    def generate_with_yin_control(
        self, prompt_tokens, max_len=500, temperature=0.7, yin_target=None
    ) -> Tuple[List[int], List[float]]:
        """Convenience: generate with active Yin coherence control."""
        return self.generate(prompt_tokens, max_len, temperature,
                            yin_control=True, yin_target=yin_target)

    # ─── Internal helpers ───

    def _repr_to_field(self, repr: torch.Tensor) -> torch.Tensor:
        """Convert repr [B or 1, D] → field [B or 1, DIM]."""
        if hasattr(self.cord, 'decoder') and not hasattr(self.cord, 'cords'):
            return self.cord.decoder(repr)
        elif hasattr(self.cord, 'cords'):
            return self.cord.cords[0].decoder(repr)
        return repr  # fallback

    def _extract_qi(self, qi) -> float:
        """Extract scalar qi from various return formats."""
        if isinstance(qi, dict):
            return qi.get('qi_mean', qi.get('qi_0', 0.5))
        if hasattr(qi, 'item'):
            return qi.item()
        return float(qi)


class ByteGenerator:
    """Causal byte-level text generation — matches causal training objective.

    Trained:  bytes[0:1024] → Cord → repr → byte_content_head → next 256 bytes
    Generate: prompt → Cord → repr → byte_content_head → output bytes → shift → repeat

    No tokenizer, no vocabulary. Raw bytes in, raw bytes out.
    """

    def __init__(self, cord, encoder, byte_content_head, byte_embedding_table,
                 byte_emb_dim: int = 16, alpha: float = 0.7, char_head=None):
        self.cord = cord
        self.encoder = encoder        # ByteEncoder
        self.byte_content_head = byte_content_head
        self.byte_embedding_table = byte_embedding_table
        self.byte_emb_dim = byte_emb_dim
        self.alpha = alpha
        self.char_head = char_head

    @torch.no_grad()
    def generate(self, prompt_bytes: bytes, max_bytes: int = 500,
                 temperature: float = 0.7) -> bytes:
        """Generate bytes from a byte prompt.

        Args:
            prompt_bytes: initial bytes (e.g., b'The ')
            max_bytes: maximum bytes to generate
            temperature: sampling temperature for byte selection

        Returns:
            generated byte string
        """
        self.cord.eval()
        dev = next(self.cord.parameters()).device

        # Convert prompt to tensor
        prompt_t = torch.tensor(list(prompt_bytes), dtype=torch.long)
        if len(prompt_t) < 256:
            prompt_t = torch.cat([prompt_t, torch.zeros(256 - len(prompt_t), dtype=torch.long)])
        prompt_field = self.encoder.encode_sequence(prompt_t[:1024], T=4).to(dev)  # [4, DIM]
        # Prime state: process each prompt field through step() to fill cumsum buffers
        states = self.cord.init_state(1)
        with torch.no_grad():
            for t in range(4):
                f = prompt_field[t].unsqueeze(0)  # [1, DIM]
                result = self.cord.step(f, states)
                if len(result) == 4:
                    next_field, _, states, _ = result
                else:
                    next_field, states, _ = result
        field = next_field  # [1, DIM] — context established
        output = bytearray()

        for _ in range(max_bytes // 256 + 1):
            # Cord step: field → next_field + repr
            result = self.cord.step(field, states)
            if len(result) == 4:
                next_field, repr_vec, states, _qi = result
            else:
                next_field, states, _qi = result
                repr_vec = next_field

            # Repr → byte content head → byte embeddings
            content = self.byte_content_head(repr_vec.squeeze(0))  # [256 * byte_emb_dim]
            content = content.view(256, self.byte_emb_dim)  # [256, byte_emb_dim]

            # Find nearest byte for each position
            # byte_embedding_table.weight: [256, byte_emb_dim]
            # content: [256, byte_emb_dim] → scores: [256, 256]
            scores = torch.mm(content, self.byte_embedding_table.weight.T) / temperature  # [256, 256]
            probs = torch.softmax(scores, dim=-1)
            next_bytes = torch.multinomial(probs, 1).squeeze(-1).cpu()  # [256]

            output.extend(next_bytes.tolist())
            if len(output) >= max_bytes:
                break

            # Encode predicted bytes → next field for Cord step
            next_field_t = self.encoder.encode_sequence(next_bytes, T=1).to(dev)
            field = (next_field_t.unsqueeze(0) * (1 - self.alpha)
                     + next_field.unsqueeze(0) * self.alpha)

        return bytes(output[:max_bytes])


def build_codec(vocab_size: int = None, repr_dim: int = 64, byte_mode: bool = True) -> Tuple:
    """Build encoder/decoder pair. byte_mode=True uses ByteEncoder (no vocab)."""
    if byte_mode:
        enc = ByteEncoder(window_bytes=1024, dim_field=1024, T=4)
        dec = TextDecoder(256, repr_dim=repr_dim, dim_char=32)  # byte-level decoder
    else:
        enc = TextEncoder(vocab_size, dim_field=1024, dim_char=32)
        dec = TextDecoder(vocab_size, repr_dim=repr_dim, dim_char=32)
    return enc, dec
