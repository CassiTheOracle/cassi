"""MultiScaleByteEncoder — Phase 7 universal byte ingestion at multiple scales.

Humans process language at multiple granularities: letters, words, phrases,
paragraphs. A universal dynamics engine should do the same with bytes.

This encoder produces a multi-scale field representation:
  - fine:   individual bytes   (local structure, character-level)
  - medium: byte n-grams       (word-like patterns)
  - coarse: large byte windows (context, paragraph-level)

The scales are concatenated into a single field vector. During training, the
model learns which scales to attend to via a learned gating network.
"""

import torch
import torch.nn as nn
from typing import Tuple

from cassi.text_codec import WaveByteEncoder


class MultiScaleByteEncoder(nn.Module):
    """Encode raw bytes at multiple scales into a single field representation.

    Args:
        dim_field: target field dimension (e.g. 1024 for CordPhysics)
        fine_window: byte window for fine scale (default 256)
        medium_window: byte window for medium scale (default 512)
        coarse_window: byte window for coarse scale (default 1024)
        T: number of time steps to emit (default 4)
    """

    def __init__(self, dim_field: int = 1024,
                 fine_window: int = 256,
                 medium_window: int = 512,
                 coarse_window: int = 1024,
                 T: int = 4):
        super().__init__()
        if dim_field % 4 != 0:
            raise ValueError(f"dim_field must be divisible by 4, got {dim_field}")
        if any(w % T != 0 for w in (fine_window, medium_window, coarse_window)):
            raise ValueError(
                f"All window sizes must be divisible by T={T}, got "
                f"fine={fine_window}, medium={medium_window}, coarse={coarse_window}"
            )
        if not (fine_window <= medium_window <= coarse_window):
            raise ValueError(
                f"Window sizes must be non-decreasing: fine<=medium<=coarse, got "
                f"{fine_window}, {medium_window}, {coarse_window}"
            )

        self.dim_field = dim_field
        self.fine_window = fine_window
        self.medium_window = medium_window
        self.coarse_window = coarse_window
        self.T = T

        dim_f = dim_field // 4
        dim_m = dim_field // 4
        dim_c = dim_field // 2

        # Per-scale wave encoders
        self.fine_encoder = WaveByteEncoder(window_bytes=fine_window, dim_field=dim_f, T=T)
        self.medium_encoder = WaveByteEncoder(window_bytes=medium_window, dim_field=dim_m, T=T)
        self.coarse_encoder = WaveByteEncoder(window_bytes=coarse_window, dim_field=dim_c, T=T)

        # Learnable scale gating: model learns how much to trust each scale
        self.scale_gate = nn.Sequential(
            nn.Linear(dim_field, 3),
            nn.Softmax(dim=-1),
        )

    def encode_sequence(self, raw_bytes, T: int = None):
        """Encode byte sequence at multiple scales.

        raw_bytes: bytes, bytearray, or uint8 tensor [B, N]
        Returns: field [B, T, dim_field]
        """
        if T is None:
            T = self.T
        if T != self.T:
            raise NotImplementedError(
                f"MultiScaleByteEncoder only supports T={self.T}, got T={T}"
            )

        if isinstance(raw_bytes, (bytes, bytearray)):
            raw_bytes = torch.tensor(list(raw_bytes), dtype=torch.uint8)
        if raw_bytes.dtype != torch.uint8:
            raw_bytes = raw_bytes.to(torch.uint8)
        if raw_bytes.dim() == 1:
            raw_bytes = raw_bytes.unsqueeze(0)
        if raw_bytes.dim() != 2:
            raise ValueError(f"raw_bytes must be 1D or 2D, got shape {raw_bytes.shape}")

        # Pad / truncate to coarse window (largest scale)
        B, N = raw_bytes.shape
        device = raw_bytes.device
        padded = torch.zeros(B, self.coarse_window, dtype=torch.uint8, device=device)
        n = min(N, self.coarse_window)
        if n > 0:
            padded[:, :n] = raw_bytes[:, :n]

        # Extract windows for each scale
        fine_in = padded[:, :self.fine_window]
        medium_in = padded[:, :self.medium_window]
        coarse_in = padded

        # Encode each scale
        fine_field = self.fine_encoder.encode_sequence(fine_in, T=T)        # [B, T, dim/4]
        medium_field = self.medium_encoder.encode_sequence(medium_in, T=T)  # [B, T, dim/4]
        coarse_field = self.coarse_encoder.encode_sequence(coarse_in, T=T)  # [B, T, dim/2]

        # Concatenate scales
        multi_scale = torch.cat([fine_field, medium_field, coarse_field], dim=-1)  # [B, T, dim]

        # Dynamic scale gating based on concatenated scale statistics
        scale_stats = torch.cat([
            fine_field.mean(dim=1),
            medium_field.mean(dim=1),
            coarse_field.mean(dim=1),
        ], dim=-1)  # [B, dim]
        gate = self.scale_gate(scale_stats)  # [B, 3]

        # Broadcast gate to [B, T, dim] via per-scale reweighting
        gate_f = gate[:, 0:1].unsqueeze(1)   # [B, 1, 1]
        gate_m = gate[:, 1:2].unsqueeze(1)
        gate_c = gate[:, 2:3].unsqueeze(1)

        dim_f = self.dim_field // 4
        dim_m = self.dim_field // 4
        scaled = torch.cat([
            gate_f * multi_scale[:, :, :dim_f],
            gate_m * multi_scale[:, :, dim_f:dim_f + dim_m],
            gate_c * multi_scale[:, :, dim_f + dim_m:],
        ], dim=-1)

        return scaled

    def encode(self, bytes_tensor: torch.Tensor) -> torch.Tensor:
        """Encode a single chunk [B, n_bytes] → field [B, dim_field]."""
        out = self.encode_sequence(bytes_tensor)  # [B, T, dim_field]
        return out[:, -1, :]  # [B, dim_field]

    @torch.no_grad()
    def decode(self, field: torch.Tensor) -> torch.Tensor:
        """Best-effort decode using coarse scale only.

        Multi-scale decoding is inherently ambiguous; we return the coarse
        reconstruction which carries the most semantic content.
        """
        if field.dim() not in (2, 3):
            raise ValueError(f"field must be 2D or 3D, got shape {field.shape}")
        dim_c = self.dim_field // 2
        coarse_field = field[..., dim_c:]
        return self.coarse_encoder.decode(coarse_field)

class MultiScaleByteEmbedder(nn.Module):
    """Per-position φ-scaled multi-scale byte embedder.

    Encodes a byte sequence at multiple n-gram resolutions using 1D convolutions
    over learned byte embeddings, applies a per-position learned scale gate, and
    projects the fused representation to a target dimension.

    Args:
        d_out: output feature dimension per position.
        scales: kernel sizes for the 1D convolutions. Defaults to Fibonacci/φ
            n-gram scales (1, 2, 3, 5, 8, 13).
        byte_embed_dim: dimension of the byte embedding table.
        norm_before: apply LayerNorm to concatenated scale features before gating.
        norm_after: apply LayerNorm to the final fused output.
    """

    def __init__(
        self,
        d_out: int,
        scales: Tuple[int, ...] = (1, 2, 3, 5, 8, 13),
        byte_embed_dim: int = 64,
        norm_before: bool = True,
        norm_after: bool = True,
    ):
        super().__init__()
        if d_out <= 0:
            raise ValueError(f"d_out must be positive, got {d_out}")
        if not scales:
            raise ValueError("scales must be non-empty")
        if any(k < 1 for k in scales):
            raise ValueError(f"all scales must be >= 1, got {scales}")
        if byte_embed_dim <= 0:
            raise ValueError(f"byte_embed_dim must be positive, got {byte_embed_dim}")

        self.d_out = d_out
        self.scales = tuple(scales)
        self.byte_embed_dim = byte_embed_dim
        self.num_scales = len(scales)

        # Learned byte embeddings: 256 possible byte values.
        self.byte_embed = nn.Embedding(256, byte_embed_dim)

        # Divide d_out across scales as evenly as possible.
        base_d = d_out // self.num_scales
        remainder = d_out % self.num_scales
        self.d_k_list = [
            base_d + (1 if i < remainder else 0) for i in range(self.num_scales)
        ]

        # Cumulative indices for slicing the concatenated scale features.
        self.cum_dims = [0]
        for d_k in self.d_k_list:
            self.cum_dims.append(self.cum_dims[-1] + d_k)

        # φ-scaled 1D convolutions over byte embeddings.
        self.convs = nn.ModuleList([
            nn.Conv1d(byte_embed_dim, d_k, kernel_size=k, padding="same")
            for k, d_k in zip(self.scales, self.d_k_list)
        ])
        self.activation = nn.GELU()

        total_hidden = sum(self.d_k_list)

        # Optional layer normalization before and after scale fusion.
        self.norm_before = nn.LayerNorm(total_hidden) if norm_before else None
        self.norm_after = nn.LayerNorm(d_out) if norm_after else None

        # Per-position scale gate: learns how much to weight each scale.
        self.gate_linear = nn.Linear(total_hidden, self.num_scales)

        # Final projection to the output dimension.
        self.fusion_proj = nn.Linear(total_hidden, d_out)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Encode a byte sequence into per-position features.

        Args:
            x: byte ids of shape [B, N], dtype torch.long or torch.uint8.

        Returns:
            Tensor of shape [B, N, d_out].
        """
        if x.dtype == torch.uint8:
            x = x.long()
        if x.dtype != torch.long:
            raise ValueError(f"x must be long or uint8, got {x.dtype}")

        # [B, N, byte_embed_dim]
        z = self.byte_embed(x)

        # Compute per-scale convolutional features.
        scale_features = []
        for conv in self.convs:
            h = conv(z.transpose(1, 2))           # [B, d_k, N]
            h = h.transpose(1, 2).contiguous()    # [B, N, d_k]
            h = self.activation(h)
            scale_features.append(h)

        # [B, N, total_hidden]
        fused = torch.cat(scale_features, dim=-1)

        if self.norm_before is not None:
            fused = self.norm_before(fused)

        # [B, N, num_scales] gate over scales.
        gate = torch.softmax(self.gate_linear(fused), dim=-1)

        # Reweight each scale's feature block by its gate weight.
        reweighted = []
        for i, d_k in enumerate(self.d_k_list):
            start = self.cum_dims[i]
            end = self.cum_dims[i + 1]
            block = fused[:, :, start:end]          # [B, N, d_k]
            weight = gate[:, :, i:i + 1]            # [B, N, 1]
            reweighted.append(weight * block)

        fused = torch.cat(reweighted, dim=-1)       # [B, N, total_hidden]

        # [B, N, d_out]
        out = self.fusion_proj(fused)

        if self.norm_after is not None:
            out = self.norm_after(out)

        return out


