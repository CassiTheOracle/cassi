#!/usr/bin/env python3
"""PhysicsFieldModel — DualFluidField + encoder/decoder for physics frame prediction.

Architecture:
    Physics frames [B, N, 1024] → Linear encoder → [B, N, d] complex source
        → DualFluidField PDE integration (spectral mixing along N)
        → [B, N, d] → Linear decoder → [B, N, 1024] predicted next frames

Training task (next-frame prediction):
    Given N consecutive frames, predict the sequence shifted by 1.
    source = frames[:, :-1]  (first N-1)
    target = frames[:, 1:]   (last N-1, shifted)

Transfer to byte training:
    PhysicsFieldModel.fluid_field.state_dict() contains the PDE coefficients.
    These can be loaded into FluidCord.fluid_field — the parameter names
    match exactly (nu_logit, hbar_logit, g_logit, etc.), and their shapes
    are scalar regardless of N or d.
"""

import math
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from fluid_field import DualFluidField as FluidField


class PhysicsFieldModel(nn.Module):
    """Physics frame prediction via PDE field integration.

    Args:
        field_d: Input physics field dimension (default 1024).
        d: Latent field dimension for the PDE.
        N: Number of spatial positions (frames per window).
        C: Number of chakras (always 13).
        max_batch_size: Max batch for persistent buffers.
        use_phi_qp: Use φ-modified quantum potential.
    """

    def __init__(self,
                 field_d: int = 1024,
                 d: int = 32,
                 N: int = 32,
                 C: int = 13,
                 max_batch_size: int = 64,
                 use_phi_qp: bool = True):
        super().__init__()
        self.field_d = field_d
        self.d = d
        self.N = N
        self.C = C

        # ── Encoder: physics frame → complex field source ──
        # Projects [field_d] → [2*d], split into real/imag for complex source
        self.encoder = nn.Linear(field_d, d * 2)
        nn.init.normal_(self.encoder.weight, std=0.02)
        nn.init.zeros_(self.encoder.bias)

        # ── PDE core (shared coefficients) ──
        self.fluid_field = DualFluidField(
            d=d, C=C, N=N, max_batch_size=max_batch_size,
            use_phi_qp=use_phi_qp,
        )

        # ── Field self-prediction head (field[i] → field[i+1]) ──
        self.field_predictor = nn.Linear(d, d)
        nn.init.normal_(self.field_predictor.weight, std=0.01)
        nn.init.zeros_(self.field_predictor.bias)

        # ── Decoder: field activation → physics frame ──
        self.decoder = nn.Linear(d, field_d)
        nn.init.normal_(self.decoder.weight, std=0.02)
        nn.init.zeros_(self.decoder.bias)

    # ── Forward ──

    def forward(self,
                frames: torch.Tensor,
                T: float = 1.0,
                dt: float = 0.2,
                return_psi: bool = False,
                ) -> torch.Tensor:
        """Predict next frames from source frames.

        For each position i in the source, predicts frame[i+1].
        Source positions beyond N_in (padded) produce no valid prediction.

        Args:
            frames: Source frames [B, N_in, field_d].
            T: PDE integration time.
            dt: PDE time step.
            return_psi: If True, return (pred, psi).

        Returns:
            pred: [B, N_in, field_d] predicted next frames.
            (optionally) psi: [B, N, d] complex field after integration.
        """
        B, N_in, D = frames.shape
        device = frames.device

        # ── Encode each frame to complex source ──
        enc = self.encoder(frames)                      # [B, N_in, d*2]
        real, imag = enc.chunk(2, dim=-1)                # [B, N_in, d] each
        source = torch.complex(real, imag)               # [B, N_in, d] complex

        # ── Pad or truncate to N positions ──
        if N_in < self.N:
            pad = torch.zeros(B, self.N - N_in, self.d,
                              dtype=torch.cfloat, device=device)
            source = torch.cat([source, pad], dim=1)     # [B, N, d]
        elif N_in > self.N:
            source = source[:, :self.N]
            N_in = self.N

        # ── Self-prediction coupling (formalism §2.2: α·P[ψ]) ──
        # Provide predict_fn for per-step re-evaluation within integrate.
        psi_current = self.fluid_field.psi[:B].clone().to(device)

        def _predict_fn(psi):
            psi_hat = self.field_predictor(psi.real).detach()
            return torch.complex(psi_hat, torch.zeros_like(psi_hat))

        initial_psi_hat = _predict_fn(psi_current)

        # ── Integrate PDE with per-step self-prediction + Qi dynamics ──
        psi = self.fluid_field.integrate(source, T=T, dt=dt,
                                         self_pred=initial_psi_hat,
                                         predict_fn=_predict_fn)  # [B, D, d]

        # ── Decode non-padded positions ──
        pred = self.decoder(psi.real[:, :N_in])          # [B, N_in, field_d]

        if return_psi:
            return pred, psi
        return pred

    # ── Training loss ──

    def training_loss(self,
                      frames: torch.Tensor,
                      T: float = 1.0,
                      dt: float = 0.2,
                      mse_weight: float = 1.0,
                      spectral_weight: float = 0.1,
                      ) -> Tuple[torch.Tensor, Dict]:
        """Compute training loss on a physics window.

        Source = frames[:, :-1]  (first N_win-1 frames)
        Target = frames[:, 1:]   (last N_win-1 frames, shifted by 1)

        Losses:
            - MSE between predicted and target frames
            - Spectral MSE (power spectrum match)

        Field self-prediction (field[i] → field[i+1]) is diagnostic only.
        The formalism requires irreducible Qi — training to minimize
        self-prediction kills the system's dynamics.

        Args:
            frames: [B, N_win, field_d] consecutive frames.
            T: PDE integration time.
            dt: PDE time step.
            mse_weight: Weight for MSE loss.
            spectral_weight: Weight for spectral loss.

        Returns:
            (loss, info_dict) where info_dict has scalar items.
        """
        B, N_win, D = frames.shape
        device = frames.device

        # Source = frames[0:N_win-1], target = frames[1:N_win]
        source_frames = frames[:, :-1].contiguous()   # [B, N_in, D]
        target_frames = frames[:, 1:].contiguous()    # [B, N_in, D]
        N_in = source_frames.shape[1]

        pred, psi = self.forward(source_frames, T=T, dt=dt,
                                 return_psi=True)

        # Trim pred to N_in (may be truncated if N_in > N)
        pred = pred[:, :N_in]

        # ── 1. MSE loss ──
        mse_loss = F.mse_loss(pred, target_frames)

        # ── 2. Spectral loss (power spectrum, ortho-normalized FFT) ──
        pred_fft = torch.fft.rfft(pred, dim=-1, norm='ortho')
        tgt_fft = torch.fft.rfft(target_frames, dim=-1, norm='ortho')
        spectral_loss = F.mse_loss(pred_fft.abs(), tgt_fft.abs())

        # ── 3. Field Qi (formalism §3.2: qi = M·q, diagnostic only) ──
        # Compute prediction error ε = ψ - P[ψ] from final field state
        psi_hat_post = self.field_predictor(psi.real[:, :N_in])  # [B, N_in, d]
        eps = psi[:, :N_in].real - psi_hat_post  # prediction error
        eps_sq = eps ** 2
        M = psi[:, :N_in].real ** 2  # field intensity
        phi_inv_sq = 0.618034 ** 2  # φ⁻² ≈ 0.382
        qi = M * M / (M + phi_inv_sq + eps_sq + 1e-12)  # coherent energy
        qi_mean = qi.mean()
        field_self_pred = eps_sq.mean()  # irreducible Qi (diagnostic)

        # ── Combined ──
        loss = (mse_weight * mse_loss
                + spectral_weight * spectral_loss)

        info = {
            "loss": loss.item(),
            "mse": mse_loss.item(),
            "spectral": spectral_loss.item(),
            "qi_mean": qi_mean.item(),
            "field_self_pred": field_self_pred.item(),
        }
        return loss, info


    # ── Rollout (autoregressive generation) ──

    @torch.no_grad()
    def rollout(self,
                seed_frame: torch.Tensor,
                n_steps: int = 50,
                T: float = 1.0,
                dt: float = 0.2,
                ) -> torch.Tensor:
        """Autoregressive rollout from seed frame.

        Each step: predict next frame -> feed predicted frame as new source.

        Args:
            seed_frame: [field_d] initial frame (any device).
            n_steps: Number of rollout steps.
            T: PDE integration time per step.
            dt: PDE time step.

        Returns:
            trajectory: [n_steps + 1, field_d] (seed + generated steps).
        """
        self.fluid_field.reset_state()
        device = seed_frame.device

        traj = [seed_frame]
        current = seed_frame.unsqueeze(0).unsqueeze(0)  # [1, 1, D]

        for _ in range(n_steps):
            pred = self.forward(current, T=T, dt=dt)     # [1, 1, D]
            traj.append(pred[0, 0])                       # [1024] — keep on device
            current = pred                                # feed back

        return torch.stack(traj)                          # [N+1, D]


    # ── State management ──

    def reset_state(self):
        """Clear persistent PDE field state (for rollout continuity)."""
        self.fluid_field.reset_state()

# ── Physics checkpoint → FluidCord transfer ──

def load_physics_to_fluidcord(physics_ckpt: Dict, fluidcord_model: nn.Module,
                              strict: bool = False) -> int:
    """Load PDE coefficients from physics checkpoint into FluidCord.

    Transfers only the scalar PDE coefficient parameters (nu_logit,
    hbar_logit, mass_logit, g_logit, chi_logit, A_B_logit,
    advection_logit, alpha_logit).  Buffers (k_pos_fft, laplacian_eigvals, psi)
    and non-PDE params (encoder, decoder, memories) are NOT loaded.

    Args:
        physics_ckpt: Full checkpoint dict (or model state_dict) from
                      PhysicsFieldModel training.
        fluidcord_model: A FluidCord (or any model containing fluid_field).
        strict: If True, raise on key mismatch.

    Returns:
        Number of parameters successfully loaded.
    """
    pde_param_suffixes = {
        "nu_logit", "hbar_logit", "mass_logit", "g_logit",
        "chi_logit", "A_B_logit", "advection_logit", "alpha_logit",
    }

    if "model" in physics_ckpt:
        src_sd = physics_ckpt["model"]
    else:
        src_sd = physics_ckpt

    # Filter: keep only fluid_field.*logit params
    filtered = {}
    for key, value in src_sd.items():
        # Match keys like "fluid_field.nu_logit" or "fluid_field.advection_logit"
        parts = key.split(".")
        if len(parts) >= 2 and parts[-2] == "fluid_field" and parts[-1] in pde_param_suffixes:
            # Strip leading module prefix if present (e.g., "fluid_field.nu_logit")
            # The FluidCord's fluid_field has keys "fluid_field.nu_logit"
            filtered[key] = value
        # Also match bare keys like "nu_logit" (bare DualFluidField)
        elif key in pde_param_suffixes:
            filtered[f"fluid_field.{key}"] = value

    n_loaded = 0
    for key in filtered:
        if key in fluidcord_model.state_dict():
            tgt_shape = fluidcord_model.state_dict()[key].shape
            src_shape = filtered[key].shape
            if tgt_shape == src_shape:
                fluidcord_model.state_dict()[key].copy_(filtered[key])
                n_loaded += 1
            elif not strict:
                # Scalar mismatch — warn but skip
                print(f"  ⚠ shape mismatch {key}: src={src_shape} vs tgt={tgt_shape}, skipping")
            else:
                raise RuntimeError(
                    f"Shape mismatch {key}: {src_shape} vs {tgt_shape}")
        elif not strict:
            print(f"  ⚠ key {key} not found in target model, skipping")
        else:
            raise RuntimeError(f"Key {key} not found in target model")

    return n_loaded
