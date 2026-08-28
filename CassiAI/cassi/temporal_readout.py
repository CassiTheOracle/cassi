"""TemporalResonanceReadout — multi-horizon prediction via learned temporal bands.

The brain state is decomposed into bands that resonate at different time scales.
The spacing between scales is learned but initialized to φ (golden ratio),
giving a fractal prior while allowing data-driven adaptation.

To predict horizon h, the readout softly attends to bands whose natural periods
are closest to h. This makes "time" a geometric property of the representation
rather than an explicit output dimension.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi.cord import PHI


class TemporalResonanceReadout(nn.Module):
    """Readout that predicts future states via temporal resonance bands.

    The D_brain-dimensional brain state is split into n_scales bands.
    Each band learns to decode a prediction at its natural temporal scale.
    Band periods are spaced by a learned factor α initialized to φ.

    Args:
        D_brain: dimension of incoming brain state
        n_scales: number of temporal resonance bands
        output_dim: dimension of each prediction (e.g., 1024 for physics fields)
        horizons: target prediction horizons used during training
        tau: temperature for soft horizon-to-band matching
    """

    def __init__(self, D_brain, n_scales=6, output_dim=1024,
                 horizons=(1, 4, 16), tau=0.5):
        super().__init__()
        self.D_brain = D_brain
        self.n_scales = n_scales
        self.output_dim = output_dim
        self.horizons = tuple(horizons)
        self.n_horizons = len(self.horizons)
        self.tau = tau
        # Choose a band width that divides evenly; project if D_brain isn't divisible.
        self.band_width = max(1, D_brain // n_scales)
        self.projected_dim = self.band_width * n_scales

        self.use_projection = (self.projected_dim != D_brain)
        if self.use_projection:
            self.band_proj = nn.Sequential(
                nn.LayerNorm(D_brain),
                nn.Linear(D_brain, self.projected_dim),
            )
            # Small init so bands start near zero.
            for m in self.band_proj.modules():
                if isinstance(m, nn.Linear):
                    nn.init.uniform_(m.weight, -0.01, 0.01)
                    nn.init.zeros_(m.bias)
        else:
            self.band_proj = None

        # Learnable temporal zoom factor α, initialized to φ.
        # Periods are: period[k] = α^k for k = 0..n_scales-1
        self.log_alpha = nn.Parameter(torch.tensor(math.log(PHI), dtype=torch.float32))

        # Optional: small per-band drift around the φ-spaced backbone.
        # This lets individual bands shift without breaking self-similarity.
        self.log_period_drift = nn.Parameter(torch.zeros(n_scales))

        # Each band has its own readout to physical/output space.
        self.band_readouts = nn.ModuleList([
            nn.Sequential(
                nn.LayerNorm(self.band_width),
                nn.Linear(self.band_width, output_dim),
            ) for _ in range(n_scales)
        ])

        # Small init so brain contribution starts near zero.
        for readout in self.band_readouts:
            for m in readout.modules():
                if isinstance(m, nn.Linear):
                    nn.init.uniform_(m.weight, -0.01, 0.01)
                    nn.init.zeros_(m.bias)

        # Register horizon tensor as a buffer so it moves with the model.
        self.register_buffer('_horizons', torch.tensor(self.horizons, dtype=torch.float32))

    def periods(self):
        """Return current temporal periods for all bands."""
        k = torch.arange(self.n_scales, device=self.log_alpha.device, dtype=torch.float32)
        log_periods = self.log_alpha * k + self.log_period_drift
        return torch.exp(log_periods)

    def forward(self, brain_state, spine_pred=None):
        """Decode brain state into horizon-specific predictions.

        Args:
            brain_state: [B, D_brain]
            spine_pred: optional [B, output_dim] — spine prediction at horizon 1,
                        added as residual to the fast band/horizon 1.

        Returns:
            pred: [B, n_horizons, output_dim] predictions for each target horizon
            info: dict with temporal geometry diagnostics
        """
        B = brain_state.shape[0]
        device = brain_state.device

        # Project to divisible dimension if necessary.
        if self.use_projection:
            brain_state = self.band_proj(brain_state)

        # Split brain state into temporal bands.
        bands = brain_state.split(self.band_width, dim=-1)  # n_scales tensors of [B, band_width]

        # Decode each band to output space: [B, n_scales, output_dim]
        band_preds = torch.stack([r(b) for r, b in zip(self.band_readouts, bands)], dim=1)

        # Optionally add spine residual to the fastest band (band 0, period ~1).
        if spine_pred is not None:
            band_preds[:, 0] = band_preds[:, 0] + spine_pred.unsqueeze(1)

        # Soft map from bands to target horizons via period matching.
        periods = self.periods()  # [n_scales]
        log_periods = torch.log(periods)  # [n_scales]
        log_h = torch.log(self._horizons.to(device))  # [n_horizons]

        # diff[h, s] = log(horizon[h]) - log(period[s])
        diff = log_h.unsqueeze(1) - log_periods.unsqueeze(0)  # [n_horizons, n_scales]
        horizon_weights = F.softmax(-(diff ** 2) / self.tau, dim=-1)  # [n_horizons, n_scales]

        # Combine band predictions into horizon predictions.
        pred = torch.einsum('bsd,hs->bhd', band_preds, horizon_weights)  # [B, n_horizons, output_dim]

        info = {
            'temporal_periods': periods.detach().cpu().tolist(),
            'log_alpha': self.log_alpha.item(),
            'alpha': math.exp(self.log_alpha.item()),
            'horizon_weights': horizon_weights.detach().cpu().tolist(),
        }
        return pred, info

    def regularization_loss(self, lambda_alpha=1e-4, lambda_drift=1e-3):
        """Regularization that keeps α near φ and drift small."""
        alpha_loss = lambda_alpha * (self.log_alpha - math.log(PHI)) ** 2
        drift_loss = lambda_drift * (self.log_period_drift ** 2).mean()
        return alpha_loss + drift_loss

    def decode_horizon(self, band_preds, horizon):
        """Inference-only: decode a single arbitrary horizon.

        Args:
            band_preds: [B, n_scales, output_dim] band predictions
            horizon: float, desired prediction horizon

        Returns:
            pred: [B, output_dim]
        """
        device = band_preds.device
        periods = self.periods()
        log_periods = torch.log(periods)
        log_h = torch.log(torch.tensor(horizon, device=device, dtype=torch.float32))
        diff = log_h - log_periods  # [n_scales]
        weights = F.softmax(-(diff ** 2) / self.tau, dim=0)  # [n_scales]
        pred = torch.einsum('bsd,s->bd', band_preds, weights)
        return pred
