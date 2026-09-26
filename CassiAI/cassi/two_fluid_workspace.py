"""TwoFluidWorkspace — Yin/Yang workspace dynamics as coupled fluids.

Maps the cosmology two-fluid equations (Yang density ey, Yin density ei,
information potential phi, polarity pi, velocity u) onto Cassi's dual
workspace.  Operates in feature space, not physical space.

State (persistent across forward steps):
  Y  — Yang workspace density   [B, D]
  N  — Yin workspace density    [B, D]
  u  — information-flow current [B, D]

Inputs per step:
  yang_drive — external drive into Yang (e.g. Yang hemisphere conscious state)
  yin_drive  — external drive into Yin  (e.g. Yin hemisphere conscious state)

Dynamics (learned, with structural biases):
  rho  = Y + N
  pi   = Y - N
  phi  = potential_net(rho)                # information potential
  grad_phi = phi - rho                       # feature-space gradient
  du   = velocity_net([pi, grad_phi, u]) - nu * u
  dY   = tanh(yang_dynamics([Y, N, u, grad_phi, yang_drive]))
  dN   = tanh(yin_dynamics([Y, N, u, grad_phi, yin_drive]))
  Y    = layer_norm(Y + dt * (dY + gain * (-lam)*(Y - phi*N)))
  N    = layer_norm(N + dt * (dN - gain * (-lam)*(Y - phi*N)))

The conversion term -lambda*(Y - phi*N) is applied explicitly; the
learned fluxes see the structural variables (polarity, potential gradient,
velocity) so the inductive bias is present. Outputs are layer-normalized
to prevent runaway growth.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi.cord import PHI


class TwoFluidWorkspace(nn.Module):
    """Learned Yin/Yang two-fluid workspace for DualCassi."""

    def __init__(self, D, nu=0.1, lam=0.02, hidden_dim=None):
        super().__init__()
        self.D = D
        self.nu = nu
        self.lam = lam
        self.hidden_dim = hidden_dim if hidden_dim is not None else max(D // 4, 64)

        # Information potential: total density -> potential
        self.potential_net = nn.Sequential(
            nn.Linear(D, self.hidden_dim),
            nn.LayerNorm(self.hidden_dim),
            nn.GELU(),
            nn.Linear(self.hidden_dim, D),
        )

        # Velocity update: polarity + potential gradient + current velocity
        self.velocity_net = nn.Sequential(
            nn.Linear(D * 3, self.hidden_dim),
            nn.LayerNorm(self.hidden_dim),
            nn.GELU(),
            nn.Linear(self.hidden_dim, D),
        )

        # Yang dynamics: all state + drive -> dY
        self.yang_dynamics = nn.Sequential(
            nn.Linear(D * 5, self.hidden_dim),
            nn.LayerNorm(self.hidden_dim),
            nn.GELU(),
            nn.Linear(self.hidden_dim, D),
        )

        # Yin dynamics: all state + drive -> dN
        self.yin_dynamics = nn.Sequential(
            nn.Linear(D * 5, self.hidden_dim),
            nn.LayerNorm(self.hidden_dim),
            nn.GELU(),
            nn.Linear(self.hidden_dim, D),
        )

        # Explicit inductive-bias conversion mixer (optional learnable gain)
        self.conversion_gain = nn.Parameter(torch.tensor(1.0))

        # Persistent fluid state
        self.register_buffer('Y', torch.zeros(1, D))
        self.register_buffer('N', torch.zeros(1, D))
        self.register_buffer('u', torch.zeros(1, D))

    def _ensure(self, buf, shape):
        """Resize/zero buffer, preserving register_buffer when batch size unchanged."""
        if buf.shape[0] != shape[0]:
            return torch.zeros(*shape, device=buf.device, dtype=buf.dtype)
        buf.zero_()
        return buf

    @torch.no_grad()
    def reset_state(self, batch_size=1, device=None):
        """Reset fluid state for a new batch/sequence."""
        if device is None:
            device = self.Y.device
        self.Y = self._ensure(self.Y, (batch_size, self.D))
        self.N = self._ensure(self.N, (batch_size, self.D))
        self.u = self._ensure(self.u, (batch_size, self.D))

    def _match_batch(self, drive):
        B = drive.shape[0]
        if self.Y.shape[0] != B or self.Y.device != drive.device:
            self.reset_state(B, device=drive.device)

    def step(self, yang_drive, yin_drive, dt=1.0):
        """Advance the two-fluid workspace by one time step.

        Args:
            yang_drive: [B, D] external Yang input
            yin_drive:  [B, D] external Yin input
            dt:          time step size

        Returns:
            yang: [B, D] updated Yang workspace
            yin:  [B, D] updated Yin workspace
            qi_energy: [B, 1] Yang/Yin cooperation
        """
        # Detach persistent state to prevent backward-graph accumulation
        # across time steps. Without this, step N+1 tries to backward
        # through the graph built at step N, which has been freed.
        Y = self.Y.detach()
        N = self.N.detach()
        u = self.u.detach()

        # Match batch size
        self._match_batch(yang_drive)

        # Ensure drives match dtype
        yang_drive = yang_drive.to(Y.dtype)
        yin_drive = yin_drive.to(Y.dtype)

        # Structural two-fluid quantities
        rho = Y + N
        pi = Y - N
        phi = self.potential_net(rho)
        grad_phi = phi - rho

        # Velocity update: driven by polarity gradients, damped by viscosity
        vel_input = torch.cat([pi, grad_phi, u], dim=-1)
        du = self.velocity_net(vel_input) - self.nu * u
        self.u = u + dt * du

        # Conversion term: Yang <-> Yin exchange
        conversion = -self.lam * (Y - phi * N)

        # Learned Yang/Yin fluxes (advection + chemotaxis + external drive)
        yang_input = torch.cat([Y, N, u, grad_phi, yang_drive], dim=-1)
        yin_input = torch.cat([Y, N, u, grad_phi, yin_drive], dim=-1)
        dY_learned = torch.tanh(self.yang_dynamics(yang_input))
        dN_learned = torch.tanh(self.yin_dynamics(yin_input))

        # Update densities with bounded learned fluxes to prevent runaway growth
        self.Y = Y + dt * (dY_learned + self.conversion_gain * conversion)
        self.N = N + dt * (dN_learned - self.conversion_gain * conversion)

        # Layer-norm stabilization: keep Yin/Yang on comparable scales
        self.Y = F.layer_norm(self.Y, self.Y.shape[-1:])
        self.N = F.layer_norm(self.N, self.N.shape[-1:])

        # Qi energy: cooperation between Yin and Yang
        qi_energy = torch.sum(self.Y * self.N, dim=-1, keepdim=True)

        return self.Y, self.N, qi_energy
